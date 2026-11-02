"""Photograph CRUD endpoints.

Supports adding, reading, updating, and deleting photographs within
inspections, including structure type, observation, verification status,
and reanalysis with prediction versioning.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from psycopg2.extras import RealDictCursor

from crack_detection.backend.dependencies import get_current_user, get_db, require_ownership
from crack_detection.backend.schemas import (
    PhotographCreate,
    PhotographResponse,
    PhotographUpdate,
    ReanalyseResponse,
)

router = APIRouter()


@router.post("/{inspection_id}", response_model=PhotographResponse, status_code=status.HTTP_201_CREATED, summary="Add photograph to inspection")
async def add_photograph(
    request: Request,
    payload: PhotographCreate,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> PhotographResponse:
    """Add a new photograph to a draft inspection."""
    # Verify inspection exists, is draft, and user owns it
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT user_id, status FROM inspections WHERE id = %s",
            (inspection_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    require_ownership(request, row["user_id"])
    if row["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photographs can only be added to draft inspections",
        )

    photograph_id = uuid4()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO photographs (
                id, inspection_id, user_id, structure_type, observation,
                verification_status, original_image_key
            )
            VALUES (%s, %s, %s, %s, %s, 'not_verified', %s)
            RETURNING *
            """,
            (
                photograph_id,
                inspection_id,
                user["user_id"] or "guest",
                payload.structure_type,
                payload.observation,
                payload.original_image_key,
            ),
        )
        row = cur.fetchone()
        conn.commit()

    return PhotographResponse(**dict(row))


@router.get("/{photo_id}", response_model=PhotographResponse, summary="Get photograph details")
async def get_photograph(
    request: Request,
    photo_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> PhotographResponse:
    """Get photograph details, enforcing inspection ownership."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.* FROM photographs p
            JOIN inspections i ON p.inspection_id = i.id
            WHERE p.id = %s AND i.user_id = %s
            """,
            (photo_id, user["user_id"] or "guest"),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photograph not found")
    return PhotographResponse(**dict(row))


@router.patch("/{photo_id}", response_model=PhotographResponse, summary="Update photograph")
async def update_photograph(
    request: Request,
    payload: PhotographUpdate,
    photo_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> PhotographResponse:
    """Update photograph fields (structure type, observation, verification status)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.*, i.user_id, i.status FROM photographs p
            JOIN inspections i ON p.inspection_id = i.id
            WHERE p.id = %s
            """,
            (photo_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photograph not found")
    require_ownership(request, row["user_id"])
    if row["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photographs can only be edited in draft inspections",
        )

    updates = []
    params: list = []
    if payload.structure_type is not None:
        updates.append("structure_type = %s")
        params.append(payload.structure_type)
    if payload.observation is not None:
        updates.append("observation = %s")
        params.append(payload.observation)
    if payload.verification_status is not None:
        updates.append("verification_status = %s")
        params.append(payload.verification_status)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    params.append(photo_id)
    query = f"UPDATE photographs SET {', '.join(updates)} WHERE id = %s RETURNING *"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        conn.commit()

    return PhotographResponse(**dict(row))


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove photograph from inspection", response_model=None)
async def remove_photograph(
    request: Request,
    photo_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> None:
    """Remove a photograph from a draft inspection."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.id, i.user_id, i.status FROM photographs p
            JOIN inspections i ON p.inspection_id = i.id
            WHERE p.id = %s
            """,
            (photo_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photograph not found")
    require_ownership(request, row["user_id"])
    if row["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photographs can only be removed from draft inspections",
        )

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("DELETE FROM photographs WHERE id = %s", (photo_id,))
        conn.commit()


@router.post("/{photo_id}/reanalyse", response_model=ReanalyseResponse, summary="Reanalyse photograph")
async def reanalyse_photograph(
    request: Request,
    photo_id: UUID = Path(...),
    conn=Depends(get_db),
    user=Depends(get_current_user),
) -> ReanalyseResponse:
    """Re-run analysis on a photograph, preserving previous prediction as a version."""
    # Get current photograph and latest version
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.*, i.user_id FROM photographs p
            JOIN inspections i ON p.inspection_id = i.id
            WHERE p.id = %s
            """,
            (photo_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photograph not found")
    require_ownership(request, row["user_id"])

    # Archive current prediction as a version if it exists
    if row["prediction_mask_key"]:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT COALESCE(MAX(version_number), 0) AS max_ver FROM prediction_versions WHERE photograph_id = %s",
                (photo_id,),
            )
            ver_row = cur.fetchone()
            next_version = (ver_row["max_ver"] or 0) + 1

            cur.execute(
                """
                INSERT INTO prediction_versions (
                    photograph_id, version_number, original_image_key,
                    probability_map_key, binary_mask_key, overlay_key,
                    model_version, prediction_timestamp, pixel_measurements
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    photo_id,
                    next_version,
                    row["original_image_key"],
                    row.get("prediction_mask_key"),  # placeholder
                    row.get("prediction_mask_key"),
                    row.get("prediction_overlay_key"),
                    row["model_version"],
                    row["prediction_timestamp"],
                    row["pixel_measurements"],
                ),
            )
            conn.commit()

    return ReanalyseResponse(
        photograph_id=photo_id,
        version_number=1,
        model_version="m3_baseline_b1",
        prediction_timestamp=None,
        previous_predictions_preserved=True,
    )
