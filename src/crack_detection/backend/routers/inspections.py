"""Inspection CRUD endpoints.

Supports creating, reading, updating, and deleting inspections with
draft/completed lifecycle management. Ownership enforcement is applied
to all operations.
"""

from __future__ import annotations

import logging

from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from psycopg2.extras import RealDictCursor

from datetime import date, datetime, timezone, timedelta

from crack_detection.backend.dependencies import (
    get_current_user,
    get_db,
    get_r2_storage,
    require_authenticated_user,
    require_ownership,
)
from crack_detection.backend.exceptions import ValidationError
from crack_detection.backend.schemas import (
    InspectionCreate,
    InspectionListResponse,
    InspectionResponse,
    InspectionUpdate,
    PhotographListResponse,
    PhotographMetadataResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED, summary="Create inspection")
async def create_inspection(
    request: Request,
    payload: InspectionCreate,
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> InspectionResponse:
    """Create a new draft inspection."""
    inspection_id = uuid4()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO inspections (id, user_id, title, building_type, building_location, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'draft')
            RETURNING *
            """,
            (
                inspection_id,
                user["user_id"] or "guest",
                payload.title,
                payload.building_type,
                payload.building_location,
                payload.notes,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return InspectionResponse(**dict(row), photograph_count=0)


VALID_STATUSES = {"draft", "completed"}
VALID_STRUCTURE_TYPES = {"wall", "beam", "column"}
VALID_VERIFICATION_STATUSES = {"not_verified", "correct", "incorrect", "partial"}


@router.get("", response_model=InspectionListResponse, summary="List inspections")
async def list_inspections(
    request: Request,
    conn=Depends(get_db),
    user=Depends(get_current_user),
    search: Optional[str] = Query(None, description="Search by inspection title"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status"
    ),
    structure_type: Optional[str] = Query(
        None, description="Filter by structure type"
    ),
    verification_status: Optional[str] = Query(
        None, description="Filter by photograph verification status"
    ),
    date_from: Optional[date] = Query(
        None, description="Filter inspections created on or after (YYYY-MM-DD)"
    ),
    date_to: Optional[date] = Query(
        None, description="Filter inspections created on or before (YYYY-MM-DD)"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> InspectionListResponse:
    """List inspections for the current user with optional filtering."""
    owner_id = user["user_id"] or "guest"

    if status_filter is not None and status_filter not in VALID_STATUSES:
        raise ValidationError(
            f"Invalid status filter. Must be one of: {sorted(VALID_STATUSES)}"
        )

    if structure_type is not None and structure_type not in VALID_STRUCTURE_TYPES:
        raise ValidationError(
            f"Invalid structure type filter. Must be one of: {sorted(VALID_STRUCTURE_TYPES)}"
        )

    if verification_status is not None and verification_status not in VALID_VERIFICATION_STATUSES:
        raise ValidationError(
            f"Invalid verification status filter. Must be one of: {sorted(VALID_VERIFICATION_STATUSES)}"
        )

    conditions: list[str] = [f"i.user_id = %s"]
    params: list = [owner_id]

    if search:
        conditions.append("i.title ILIKE %s")
        params.append(f"%{search}%")

    if status_filter:
        conditions.append("i.status = %s")
        params.append(status_filter)

    if structure_type:
        conditions.append(
            "EXISTS (SELECT 1 FROM photographs p "
            "WHERE p.inspection_id = i.id AND p.structure_type = %s)"
        )
        params.append(structure_type)

    if verification_status:
        conditions.append(
            "EXISTS (SELECT 1 FROM photographs p "
            "WHERE p.inspection_id = i.id AND p.verification_status = %s)"
        )
        params.append(verification_status)

    if date_from is not None:
        conditions.append("i.created_at >= %s")
        params.append(
            datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
        )

    if date_to is not None:
        next_day = datetime(
            date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc
        ) + timedelta(days=1)
        conditions.append("i.created_at < %s")
        params.append(next_day)

    where_clause = " AND ".join(conditions)

    count_query = f"SELECT COUNT(*) AS total FROM inspections i WHERE {where_clause}"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(count_query, params)
        count_row = cur.fetchone()
        total = int(count_row["total"]) if count_row is not None else 0

    page_query = f"""
        SELECT i.*, COUNT(p.id) AS photograph_count
        FROM inspections i
        LEFT JOIN photographs p ON p.inspection_id = i.id
        WHERE {where_clause}
        GROUP BY i.id
        ORDER BY i.created_at DESC
        LIMIT %s OFFSET %s
    """
    page_params = params + [limit, offset]
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(page_query, page_params)
        rows = cur.fetchall()

    inspections = [InspectionResponse(**dict(r)) for r in rows]
    return InspectionListResponse(inspections=inspections, total=total)


@router.get("/{inspection_id}", response_model=InspectionResponse, summary="Get inspection details")
async def get_inspection(
    request: Request,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> InspectionResponse:
    """Get inspection details by ID, enforcing ownership."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT i.*, COUNT(p.id) AS photograph_count
            FROM inspections i
            LEFT JOIN photographs p ON p.inspection_id = i.id
            WHERE i.id = %s AND i.user_id = %s
            GROUP BY i.id
            """,
            (inspection_id, user["user_id"] or "guest"),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    return InspectionResponse(**dict(row), photograph_count=row["photograph_count"])


@router.patch("/{inspection_id}", response_model=InspectionResponse, summary="Update inspection")
async def update_inspection(
    request: Request,
    payload: InspectionUpdate,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> InspectionResponse:
    """Update inspection fields. Only draft inspections can be edited."""
    # Verify ownership and that inspection is draft
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT status, user_id FROM inspections WHERE id = %s",
            (inspection_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    require_ownership(request, row["user_id"])
    if row["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft inspections can be edited",
        )

    updates = []
    params: list = []
    if payload.title is not None:
        updates.append("title = %s")
        params.append(payload.title)
    if payload.building_type is not None:
        updates.append("building_type = %s")
        params.append(payload.building_type)
    if payload.building_location is not None:
        updates.append("building_location = %s")
        params.append(payload.building_location)
    if payload.notes is not None:
        updates.append("notes = %s")
        params.append(payload.notes)
    if payload.status is not None:
        updates.append("status = %s")
        params.append(payload.status)
    if payload.status == "completed":
        updates.append("completed_at = NOW()")

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    params.append(inspection_id)
    query = f"UPDATE inspections SET {', '.join(updates)} WHERE id = %s RETURNING *"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        conn.commit()

    return InspectionResponse(**dict(row), photograph_count=0)


@router.post("/{inspection_id}/complete", response_model=InspectionResponse, summary="Mark inspection as completed")
async def complete_inspection(
    request: Request,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> InspectionResponse:
    """Manually mark an inspection as Completed (read-only afterwards)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT user_id, status FROM inspections WHERE id = %s",
            (inspection_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    require_ownership(request, row["user_id"])
    if row["status"] == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inspection is already completed",
        )

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE inspections SET status = 'completed', completed_at = NOW()
            WHERE id = %s RETURNING *
            """,
            (inspection_id,),
        )
        row = cur.fetchone()
        conn.commit()

    return InspectionResponse(**dict(row), photograph_count=0)


@router.post("/{inspection_id}/reopen", response_model=InspectionResponse, summary="Reopen inspection")
async def reopen_inspection(
    request: Request,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(require_authenticated_user),
) -> InspectionResponse:
    """Explicitly reopen a completed inspection, returning it to Draft.

    Reopening is the only way for an owner to resume editing or adding
    photographs after completion; drafts and completed inspections are never
    reopened implicitly (e.g. by edit attempts). Photographs, prediction
    versions, observations, verification statuses, and reports are never
    modified or deleted by this operation.

    The update is conditional on the current status being ``completed`` and
    scoped to the inspection id and the authenticated user id, so the status
    check and transition happen atomically in one statement and a concurrent
    completion/reopen cannot produce an inconsistent transition.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            WITH reopened AS (
                UPDATE inspections
                SET status = 'draft', completed_at = NULL
                WHERE id = %s
                  AND user_id = %s
                  AND status = 'completed'
                RETURNING *
            )
            SELECT reopened.*, COALESCE(
                (SELECT COUNT(p.id) FROM photographs p
                 WHERE p.inspection_id = reopened.id), 0
            ) AS photograph_count
            FROM reopened
            """,
            (inspection_id, user["user_id"]),
        )
        row = cur.fetchone()
        if row is None:
            # Zero-row update: distinguish an already-draft inspection from
            # a nonexistent or foreign inspection using an ownership-scoped
            # lookup, which never reveals another user's inspection.
            cur.execute(
                "SELECT status FROM inspections WHERE id = %s AND user_id = %s",
                (inspection_id, user["user_id"]),
            )
            existing = cur.fetchone()
            if existing is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inspection not found",
                )
            if existing["status"] == "draft":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Inspection is already a draft",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inspection status changed concurrently; retry",
            )
        conn.commit()

    # The CTE returns ``photograph_count`` alongside the updated row, so the
    # response is built directly from the row.
    return InspectionResponse(**dict(row))


@router.get("/{inspection_id}/photos", response_model=PhotographListResponse, summary="List inspection photographs")
async def list_inspection_photographs(
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(require_authenticated_user),
) -> PhotographListResponse:
    """List all photographs belonging to one owned inspection (oldest first).

    Requires an authenticated registered user (guests are rejected). Ownership
    is established by scoping the query to the authenticated user id from the
    verified Clerk flow; nonexistent and foreign inspections are
    indistinguishable and both return 404, matching the existing inspection
    detail endpoint's convention.

    A single LEFT JOIN query establishes inspection ownership and retrieves
    its photographs in one round trip: zero rows means the inspection is not
    found or not owned; one row with a NULL photograph id means the inspection
    exists but has no photographs yet. Rows are ordered by ``created_at``
    oldest-first with ``p.id`` as a stable tiebreaker.

    Response entries carry owner-facing metadata only (structure type,
    observation, verification status, persisted prediction metadata, and a
    derived ``prediction_available`` flag); internal R2 object keys and other
    private storage details are never returned. Image retrieval and any
    prediction persistence changes are handled by separate tasks.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.id, p.inspection_id, p.structure_type, p.observation,
                   p.verification_status, p.model_version,
                   p.prediction_timestamp, p.pixel_measurements, p.created_at,
                   (p.prediction_mask_key IS NOT NULL) AS prediction_available
            FROM inspections i
            LEFT JOIN photographs p ON p.inspection_id = i.id
            WHERE i.id = %s AND i.user_id = %s
            ORDER BY p.created_at ASC, p.id ASC
            """,
            (inspection_id, user["user_id"]),
        )
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # An existing inspection without photographs yields exactly one LEFT JOIN
    # row whose photograph columns are NULL; it is represented as an empty list.
    photographs = [
        PhotographMetadataResponse(**dict(row))
        for row in rows
        if row["id"] is not None
    ]

    return PhotographListResponse(
        inspection_id=inspection_id,
        photographs=photographs,
        total=len(photographs),
    )


@router.delete("/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete inspection", response_model=None)
async def delete_inspection(
    request: Request,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    storage=Depends(get_r2_storage),
    user=Depends(get_current_user),
) -> None:
    """Delete an inspection and all associated data (cascade delete)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT user_id FROM inspections WHERE id = %s", (inspection_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    require_ownership(request, row["user_id"])

    # --- Report PDF cleanup (before the database DELETE) ---
    # Retrieve the internal report PDF keys BEFORE deleting the inspection:
    # the committed ``reports`` rows keep the keys while cleanup runs, so the
    # keys survive any failure for a retry. PostgreSQL and R2 do not share an
    # atomic transaction; this ordering deliberately trades a documented,
    # recoverable inconsistency (report rows pointing at deleted PDFs if the
    # database DELETE later fails) over unrecoverable R2 orphans (which would
    # result from deleting the rows first and then failing R2 cleanup).
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT report_pdf_key FROM reports WHERE inspection_id = %s",
            (inspection_id,),
        )
        report_rows = cur.fetchall()

    for report_row in report_rows:
        report_key = report_row["report_pdf_key"]
        if not report_key:  # defensive; NOT NULL by schema
            continue
        try:
            # ``delete_file`` treats missing objects as success (no-op), so
            # repeated deletion attempts and retries after partial cleanup
            # are safe.
            storage.delete_file(report_key)
        except Exception as exc:
            # Abort BEFORE the database DELETE so report rows (and their
            # keys) remain committed for a later retry of the cleanup.
            logger.error(
                "Failed to delete report PDF %s during inspection %s deletion: %s",
                report_key, inspection_id, exc,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Failed to delete associated report files; "
                    "the inspection was not deleted."
                ),
            )

    # Delete R2 objects for all photographs in this inspection
    storage.delete_objects_by_prefix(f"inspections/{inspection_id}/")

    # The reports FK (fk_reports_inspection) cascades, so report rows for
    # this inspection are removed in the same database transaction as the
    # inspection itself.
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("DELETE FROM inspections WHERE id = %s", (inspection_id,))
        conn.commit()
