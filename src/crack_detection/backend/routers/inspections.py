"""Inspection CRUD endpoints.

Supports creating, reading, updating, and deleting inspections with
draft/completed lifecycle management. Ownership enforcement is applied
to all operations.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from psycopg2.extras import RealDictCursor

from crack_detection.backend.dependencies import (
    get_current_user,
    get_db,
    require_authenticated_user,
    require_ownership,
)
from crack_detection.backend.schemas import (
    InspectionCreate,
    InspectionListResponse,
    InspectionResponse,
    InspectionUpdate,
)

router = APIRouter()


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


@router.get("", response_model=InspectionListResponse, summary="List inspections")
async def list_inspections(
    request: Request,
    conn=Depends(get_db),
    user=Depends(get_current_user),
    search: Optional[str] = Query(None, description="Search by inspection title"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    structure_type: Optional[str] = Query(None, description="Filter by structure type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> InspectionListResponse:
    """List inspections for the current user with optional filtering."""
    query = """
        SELECT i.*, COUNT(p.id) AS photograph_count
        FROM inspections i
        LEFT JOIN photographs p ON p.inspection_id = i.id
        WHERE i.user_id = %s
    """
    params: list = [user["user_id"] or "guest"]

    if search:
        query += " AND i.title ILIKE %s"
        params.append(f"%{search}%")
    if status_filter:
        query += " AND i.status = %s"
        params.append(status_filter)

    query += " GROUP BY i.id ORDER BY i.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    inspections = [InspectionResponse(**dict(r)) for r in rows]
    return InspectionListResponse(inspections=inspections, total=len(inspections))


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


@router.delete("/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete inspection")
async def delete_inspection(
    request: Request,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> None:
    """Delete an inspection and all associated data (cascade delete)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT user_id FROM inspections WHERE id = %s", (inspection_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    require_ownership(request, row["user_id"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("DELETE FROM inspections WHERE id = %s", (inspection_id,))
        conn.commit()
