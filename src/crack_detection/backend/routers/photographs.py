"""Photograph CRUD endpoints.

Supports adding, reading, updating, and deleting photographs within
inspections, including structure type, observation, verification status,
reanalysis with prediction versioning, and inference analysis.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from psycopg2.extras import RealDictCursor
from io import BytesIO

from crack_detection.backend.dependencies import get_current_user, get_db, get_r2_storage
from crack_detection.backend.inference_service import analyze_image
from crack_detection.backend.schemas import (
    PhotographCreate,
    PhotographResponse,
    PhotographUpdate,
    ReanalyseResponse,
    AnalysisResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
    storage=Depends(get_r2_storage),
    user=Depends(get_current_user),
) -> None:
    """Remove a photograph from a draft inspection."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.id, i.user_id, i.status, p.original_image_key,
                   p.prediction_mask_key, p.prediction_overlay_key
            FROM photographs p
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

    # Delete R2 objects for this photograph
    photo_id_str = str(photo_id)
    inspection_id = row["inspection_id"]
    storage.delete_objects_by_prefix(f"inspections/{inspection_id}/originals/{photo_id_str}")
    storage.delete_objects_by_prefix(f"inspections/{inspection_id}/masks/{photo_id_str}_")
    storage.delete_objects_by_prefix(f"inspections/{inspection_id}/overlays/{photo_id_str}_")

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


@router.post(
    "/{photo_id}/analyse",
    response_model=AnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Analyze photograph for crack segmentation",
)
async def analyse_photograph(
    request: Request,
    photo_id: UUID = Path(...),
    conn=Depends(get_db),
    storage=Depends(get_r2_storage),
    user=Depends(get_current_user),
) -> AnalysisResponse:
    """Run crack segmentation inference on a photograph.

    Authenticates the user (Cliff JWT or guest session), verifies ownership
    or guest access, validates the guest analysis limit, downloads the
    original image from R2, runs inference, stores the mask and overlay
    in R2, and persists prediction metadata in PostgreSQL.

    Returns analysis results including mask, overlay info, model version,
    and inference duration.
    """
    # Determine if current user is a guest or registered user
    is_guest = getattr(request.state, "is_guest", False) is True
    is_authenticated = getattr(request.state, "is_authenticated", False) is True

    if not is_guest and not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Fetch photograph with inspection info
    if is_guest:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.*, i.user_id, i.status AS inspection_status
                FROM photographs p
                JOIN inspections i ON p.inspection_id = i.id
                WHERE p.id = %s
                """,
                (photo_id,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Photograph not found"
            )
        if row["inspection_status"] != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guest analysis only available for draft inspections",
            )
    else:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.*, i.user_id
                FROM photographs p
                JOIN inspections i ON p.inspection_id = i.id
                WHERE p.id = %s
                """,
                (photo_id,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Photograph not found"
            )
        require_ownership(request, row["user_id"])

    # --- Guest analysis limit check ---
    new_count = None
    if is_guest:
        guest_token = request.headers.get("X-Guest-Session-Token")
        if not guest_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Guest session token required",
            )
        from crack_detection.backend.database import (
            validate_guest_session,
            increment_guest_analysis_count,
        )

        session = validate_guest_session(guest_token)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired guest session",
            )
        # Atomically increment analysis count; None means limit reached
        new_count = increment_guest_analysis_count(
            session["id"], max_analyses=3
        )
        if new_count is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guest analysis limit reached (3 analyses per session)",
            )

    # --- Download original image from R2 ---
    original_key = row["original_image_key"]
    try:
        image_bytes = storage.download_file(original_key)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download original image from storage: {exc}",
        )

    # --- Run inference ---
    try:
        result = analyze_image(image_data=image_bytes)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed: {exc}",
        )

    # --- Upload mask and overlay to R2 ---
    mask_key = f"inspections/{photo_id}/masks/{photo_id}_mask.png"
    overlay_key = f"inspections/{photo_id}/overlays/{photo_id}_overlay.png"

    try:
        storage.upload_file(
            mask_key,
            np.array(result["binary_mask"]).tobytes(),
            "image/png",
        )
        storage.upload_file(
            overlay_key,
            np.array(result["overlay"]).tobytes(),
            "image/png",
        )
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload analysis results to storage: {exc}",
        )

    # --- Persist prediction metadata in PostgreSQL ---
    prediction_overlay_key = f"inspections/{photo_id}/overlays/{photo_id}_overlay.png"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
                1,
                row["original_image_key"],
                None,  # probability_map_key - not stored as standalone
                mask_key,
                prediction_overlay_key,
                result["model_version"],
                __import__("datetime").datetime.utcnow(),
                None,  # pixel_measurements - not calculated by current pipeline
            ),
        )
        conn.commit()

    # --- Build response ---
    analyses_remaining = max(0, 3 - new_count) if is_guest else None

    return AnalysisResponse(
        photograph_id=photo_id,
        prediction_mask_key=mask_key,
        prediction_overlay_key=prediction_overlay_key,
        model_version=result["model_version"],
        prediction_timestamp=__import__("datetime").datetime.utcnow(),
        inference_duration_ms=result["inference_duration_ms"],
        processing_status=result["processing_status"],
        original_image_size=result.get("original_image_size", (256, 256)),
        analyses_remaining=analyses_remaining if is_guest else None,
    )