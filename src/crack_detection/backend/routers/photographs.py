"""Photograph CRUD endpoints.

Supports adding, reading, updating, and deleting photographs within
inspections, including structure type, observation, verification status,
reanalysis with prediction versioning, and inference analysis.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional
from uuid import UUID, uuid4, NAMESPACE_DNS
import uuid

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, UploadFile, status
from PIL import Image as PILImage
from psycopg2.extras import Json, RealDictCursor

from crack_detection.backend.config import get_settings
from crack_detection.backend.dependencies import (
    get_current_user,
    get_db,
    get_r2_storage,
    require_authenticated_user,
    require_ownership,
)
from crack_detection.backend.inference_service import analyze_image
from crack_detection.backend.schemas import (
    PhotographCreate,
    PhotographResponse,
    PhotographUpdate,
    ReanalyseResponse,
    AnalysisResponse,
)
from crack_detection.backend.storage import R2Storage, StorageError
router = APIRouter()
logger = logging.getLogger(__name__)


def _cleanup_uploaded_keys(
    storage: R2Storage, uploaded_keys: list[str]
) -> None:
    """Attempt to delete each uploaded R2 key, logging failures without raising.

    This function is best-effort: a failure to delete an object does not
    mask the original exception that caused the cleanup, and a single
    failure does not prevent deletion of the remaining keys.
    """
    for key in uploaded_keys:
        try:
            storage.delete_file(key)
        except StorageError as exc:
            logger.warning(
                "Cleanup failed to delete R2 key %s: %s", key, exc
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "Unexpected error during R2 key cleanup %s: %s", key, exc
            )


def _persist_analysis(
    conn,
    storage: R2Storage,
    photo_id: UUID,
    original_image_key: str,
    idempotency_key: UUID,
) -> dict:
    """Run inference, upload prediction artifacts, persist the prediction
    version, and update the photograph record.

    All database work (version insert + photograph update) runs in a single
    transaction scoped to the request connection. The photograph row is locked
    with ``FOR UPDATE`` so that concurrent analyses of the same photograph are
    serialized and version numbers cannot collide.

    If database persistence fails after artifacts have been uploaded to R2,
    the newly uploaded objects are cleaned up so no orphaned artifacts remain
    and the photograph is not left pointing at missing files.

    Returns a dict with the persisted analysis details.
    """
    # --- Download original image from R2 ---
    try:
        image_bytes = storage.download_file(original_image_key)
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

    # --- Upload mask and overlay to R2, tracking keys for cleanup ---
    mask_key = f"inspections/{photo_id}/masks/{photo_id}_mask.png"
    overlay_key = f"inspections/{photo_id}/overlays/{photo_id}_overlay.png"

    uploaded_keys: list[str] = []
    try:
        storage.upload_file(
            mask_key,
            np.array(result["binary_mask"]).tobytes(),
            "image/png",
        )
        uploaded_keys.append(mask_key)
        storage.upload_file(
            overlay_key,
            np.array(result["overlay"]).tobytes(),
            "image/png",
        )
        uploaded_keys.append(overlay_key)
    except Exception as exc:  # pylint: disable=broad-except
        # Inference succeeded but storage failed. Do not consume allowance.
        # Attempt cleanup of any objects already uploaded.
        _cleanup_uploaded_keys(storage, uploaded_keys)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload analysis results to storage: {exc}",
        )

    # --- Persist prediction version + update photograph (one transaction) ---
    now = datetime.now(timezone.utc)
    measurements = result.get("pixel_measurements")
    measurements_json = Json(measurements) if measurements is not None else None

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Lock the photograph row to serialize version-number assignment
            # across concurrent analysis attempts for this photograph.
            cur.execute(
                "SELECT id FROM photographs WHERE id = %s FOR UPDATE",
                (photo_id,),
            )
            cur.fetchone()
            cur.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) AS max_ver
                FROM prediction_versions
                WHERE photograph_id = %s
                """,
                (photo_id,),
            )
            ver_row = cur.fetchone()
            next_version = (ver_row["max_ver"] or 0) + 1

            cur.execute(
                """
                INSERT INTO prediction_versions (
                    photograph_id, version_number, original_image_key,
                    probability_map_key, binary_mask_key, overlay_key,
                    model_version, prediction_timestamp, pixel_measurements,
                    idempotency_key
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    photo_id,
                    next_version,
                    original_image_key,
                    None,  # probability_map_key - not stored as a standalone object
                    mask_key,
                    overlay_key,
                    result["model_version"],
                    now,
                    measurements_json,
                    idempotency_key,
                ),
            )

            # Update the photograph to reflect the latest successful prediction.
            cur.execute(
                """
                UPDATE photographs
                SET prediction_mask_key = %s,
                    prediction_overlay_key = %s,
                    model_version = %s,
                    prediction_timestamp = %s,
                    pixel_measurements = %s
                WHERE id = %s
                """,
                (
                    mask_key,
                    overlay_key,
                    result["model_version"],
                    now,
                    measurements_json,
                    photo_id,
                ),
            )
        conn.commit()
    except Exception as exc:  # pylint: disable=broad-except
        # Database persistence failed after R2 uploads. Clean up the newly
        # uploaded artifacts so they are not orphaned and the photograph does
        # not reference missing files. Previous successful prediction versions
        # and their artifacts are untouched.
        _cleanup_uploaded_keys(storage, uploaded_keys)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist analysis results: {exc}",
        )

    return {
        "version_number": next_version,
        "prediction_mask_key": mask_key,
        "prediction_overlay_key": overlay_key,
        "original_image_key": original_image_key,
        "model_version": result["model_version"],
        "prediction_timestamp": now,
        "inference_duration_ms": result["inference_duration_ms"],
        "processing_status": result["processing_status"],
        "original_image_size": result.get("original_image_size", [256, 256]),
        "pixel_measurements": measurements,
    }


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


def _validate_uploaded_image(
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> str:
    """Validate the uploaded file's extension, size, and image content.

    Returns the normalized file extension. Validation inspects the actual
    bytes (extension, size limit, and PIL-decodable image content) rather
    than trusting only the filename or the client-supplied MIME type.
    """
    settings = get_settings()
    allowed_extensions = {
        ext.strip().lower() for ext in settings.allowed_image_extensions.split(",")
    }
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{ext or 'none'}'. "
                f"Allowed: {', '.join(sorted(allowed_extensions))}."
            ),
        )

    max_size = settings.max_upload_size_bytes
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File is larger than the {max_size // (1024 * 1024)} MB limit."
            ),
        )

    try:
        img = PILImage.open(BytesIO(file_bytes))
        img.verify()
        img = PILImage.open(BytesIO(file_bytes))
        img.convert("RGB")
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unreadable image file: {exc}",
        )
    return ext


async def _store_uploaded_photograph(
    request: Request,
    conn,
    storage: R2Storage,
    inspection_id: UUID,
    user_id: str,
    structure_type: str,
    file: UploadFile,
) -> PhotographResponse:
    """Store an uploaded photograph for an owned draft inspection.

    Enforces inspection existence, ownership, and draft eligibility;
    validates the structure type and image file; uploads the original
    image to private R2 storage; persists the photograph record in
    PostgreSQL; and cleans up the newly uploaded R2 object if database
    persistence fails. Prior photographs and prediction versions are
    never touched by this operation.
    """
    # --- Inspection: existence, ownership, draft eligibility ---
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT user_id, status FROM inspections WHERE id = %s",
            (inspection_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found"
        )
    require_ownership(request, row["user_id"])
    if row["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photographs can only be added to draft inspections",
        )

    # --- Structure type ---
    if structure_type not in {"wall", "beam", "column"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid structure type '{structure_type}'. "
                "Must be one of: wall, beam, column."
            ),
        )

    # --- File validation ---
    filename = file.filename or "upload"
    content_type = file.content_type or "application/octet-stream"
    file_bytes = await file.read()
    ext = _validate_uploaded_image(file_bytes, filename, content_type)

    # --- Upload original image to private R2 storage ---
    photograph_id = uuid4()
    original_key = f"inspections/{inspection_id}/originals/{photograph_id}.{ext}"

    try:
        storage.upload_file(original_key, file_bytes, content_type)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store uploaded image: {exc}",
        )

    # --- Persist photograph record; clean up the R2 object on DB failure ---
    try:
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
                    user_id,
                    structure_type,
                    None,
                    original_key,
                ),
            )
            row = cur.fetchone()
            conn.commit()
    except Exception:  # pylint: disable=broad-except
        # Database persistence failed after a successful R2 upload. Remove the
        # newly uploaded object so it is not orphaned and the photograph does
        # not reference a missing file. Prior photographs are untouched.
        try:
            storage.delete_file(original_key)
        except StorageError:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create photograph record.",
        )

    return PhotographResponse(**dict(row))


@router.post(
    "/{inspection_id}/upload",
    response_model=PhotographResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a photograph to an inspection",
)
async def upload_photograph(
    request: Request,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    storage=Depends(get_r2_storage),
    user=Depends(require_authenticated_user),
) -> PhotographResponse:
    """Upload a photograph to an owned draft inspection.

    Requires an authenticated registered user (guests and unauthenticated
    requests are rejected by ``require_authenticated_user``). The multipart
    body carries the image file (``file``) and the structure type
    (``structure_type``). The original image is stored in private R2 and the
    photograph record is associated with the authenticated user, the
    inspection, and the selected structure type. Completed inspections are
    not eligible.

    The form body is parsed via ``request.form()`` at request time rather
    than through FastAPI ``File``/``Form`` parameters so that this module
    stays importable where ``python-multipart`` is unavailable; production
    deployments install ``python-multipart`` so ``request.form()`` parses
    real multipart uploads.
    """
    form = await request.form()
    file = form.get("file")
    structure_type = form.get("structure_type")
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No photograph file was provided.",
        )
    if structure_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A structure type (wall, beam, column) is required.",
        )
    return await _store_uploaded_photograph(
        request,
        conn,
        storage,
        inspection_id,
        user["user_id"],
        structure_type,
        file,
    )


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
    storage=Depends(get_r2_storage),
    user=Depends(get_current_user),
) -> ReanalyseResponse:
    """Re-run analysis on a photograph, creating a new prediction version.

    The previous prediction version is preserved; the photograph record is
    updated to reflect the newest successful prediction. Requires registered
    user ownership (guests are rejected by ``require_ownership``).
    """
    # Get photograph and verify ownership
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

    # Reanalysis is a new intentional analysis: use a fresh idempotency key so
    # it never conflicts with (or reuses) an earlier key for this photograph.
    idempotency_key = uuid4()

    persisted = _persist_analysis(
        conn,
        storage,
        photo_id,
        row["original_image_key"],
        idempotency_key,
    )

    return ReanalyseResponse(
        photograph_id=photo_id,
        version_number=persisted["version_number"],
        model_version=persisted["model_version"],
        prediction_timestamp=persisted["prediction_timestamp"],
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

    Authenticates the user (Clerk JWT or guest session), verifies ownership
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

    # --- Guest session validation ---
    # Required before the idempotency key can be generated for guests (the key
    # is derived from the guest session id) and for the allowance check.
    session = None
    if is_guest:
        from crack_detection.backend.database import validate_guest_session

        guest_token = request.headers.get("X-Guest-Session-Token")
        if not guest_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Guest session token required",
            )
        session = validate_guest_session(guest_token)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired guest session",
            )

    # --- Idempotency key ---
    if is_guest:
        # Guest key is deterministic (session + photograph). A retry of the
        # same guest analysis regenerates the same key and is detected as a
        # repeat; a guest photograph is analysed once per session.
        idempotency_key = uuid.uuid5(
            NAMESPACE_DNS, f"cracksight:analyse:{session['id']}:{photo_id}"
        )
    else:
        # Registered users: an explicit Idempotency-Key header is honoured
        # when provided; otherwise a deterministic key based on the
        # authenticated user and photograph is used so that retries of the
        # same /analyse request are recognised and not duplicated even when
        # the client sends no header (the frontend does not send one). A new
        # intentional analysis of the same photograph (reanalysis) uses the
        # /reanalyse endpoint, which generates a fresh uuid4() key.
        idempotency_key_header = request.headers.get("Idempotency-Key")
        if idempotency_key_header:
            try:
                idempotency_key = UUID(idempotency_key_header)
            except (ValueError, AttributeError):
                idempotency_key = uuid.uuid5(
                    NAMESPACE_DNS,
                    f"cracksight:analyse:{user['user_id']}:{photo_id}",
                )
        else:
            idempotency_key = uuid.uuid5(
                NAMESPACE_DNS,
                f"cracksight:analyse:{user['user_id']}:{photo_id}",
            )

    # --- Idempotency check ---
    # An existing version with this key means the same analysis request was
    # already processed; return the stored result without re-running
    # inference or consuming allowance.
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, version_number, original_image_key, binary_mask_key,
                   overlay_key, model_version, prediction_timestamp,
                   pixel_measurements, inference_duration_ms,
                   processing_status
            FROM prediction_versions
            WHERE photograph_id = %s AND idempotency_key = %s
            """,
            (photo_id, idempotency_key),
        )
        existing = cur.fetchone()

    if existing:
        analyses_remaining = (
            max(0, 3 - session["analyses_count"]) if is_guest else None
        )
        return AnalysisResponse(
            photograph_id=photo_id,
            prediction_mask_key=existing["binary_mask_key"],
            prediction_overlay_key=existing["overlay_key"],
            original_image_key=existing["original_image_key"],
            model_version=existing["model_version"],
            prediction_timestamp=existing["prediction_timestamp"],
            inference_duration_ms=existing["inference_duration_ms"],
            processing_status=existing["processing_status"],
            original_image_size=existing.get("original_image_size", [256, 256]),
            pixel_measurements=existing["pixel_measurements"],
            analyses_remaining=analyses_remaining,
        )

    # --- Guest analysis limit check ---
    # Reserve the allowance before doing any work. The atomic conditional
    # UPDATE guarantees at most three successful reservations per session.
    # If the reserved analysis fails to persist, the reservation is
    # compensated (decremented) so a failed attempt never permanently
    # consumes allowance.
    new_count = None
    if is_guest:
        from crack_detection.backend.database import (
            decrement_guest_analysis_count,
            increment_guest_analysis_count,
        )

        new_count = increment_guest_analysis_count(
            session["id"], max_analyses=3
        )
        if new_count is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guest analysis limit reached (3 analyses per session)",
            )

    # --- Registered-user monthly analysis allowance ---
    # Reserve one monthly analysis slot for registered users. The atomic
    # conditional INSERT ... ON CONFLICT ... DO UPDATE guarantees that
    # concurrent requests cannot exceed the configured monthly limit.
    # If the reserved analysis fails to persist, the reservation is
    # compensated (decremented) so a failed attempt never permanently
    # consumes allowance.
    new_user_count = None
    if not is_guest:
        from crack_detection.backend.database import (
            decrement_user_analysis_count,
            increment_user_analysis_count,
            get_settings,
        )

        settings = get_settings()
        limit = settings.registered_monthly_analyses_limit
        new_user_count = increment_user_analysis_count(
            user_id=user["user_id"],
            max_analyses=limit,
        )
        if new_user_count is None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Registered user monthly analysis limit reached",
            )

    # --- Persist inference + artifacts (download, infer, upload, DB) ---
    try:
        persisted = _persist_analysis(
            conn,
            storage,
            photo_id,
            row["original_image_key"],
            idempotency_key,
        )
    except Exception:
        # Compensate the reserved allowance since the analysis did not
        # complete successfully. Best-effort: a failure to decrement is
        # logged but must not mask the original error.
        if not is_guest:
            try:
                decrement_user_analysis_count(user_id=user["user_id"])
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "Failed to compensate registered-user allowance for %s",
                    user["user_id"],
                )
        if is_guest:
            try:
                decrement_guest_analysis_count(session["id"])
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "Failed to compensate guest allowance for session %s",
                    session["id"],
                )
        raise

    # --- Build response ---
    analyses_remaining = max(0, 3 - new_count) if is_guest else None

    return AnalysisResponse(
        photograph_id=photo_id,
        prediction_mask_key=persisted["prediction_mask_key"],
        prediction_overlay_key=persisted["prediction_overlay_key"],
        original_image_key=persisted["original_image_key"],
        model_version=persisted["model_version"],
        prediction_timestamp=persisted["prediction_timestamp"],
        inference_duration_ms=persisted["inference_duration_ms"],
        processing_status=persisted["processing_status"],
        original_image_size=persisted["original_image_size"],
        pixel_measurements=persisted["pixel_measurements"],
        analyses_remaining=analyses_remaining,
    )


# ---------------------------------------------------------------------------
# Registered-user image download
# ---------------------------------------------------------------------------

_SUPPORTED_IMAGE_TYPES = {"original", "mask", "overlay"}

_CONTENT_TYPE_MAP = {
    "original": "image/jpeg",
    "mask": "image/png",
    "overlay": "image/png",
}


def _download_registered_image(
    photo_id: UUID,
    image_type: str,
    user_id: str,
    conn,
    storage: R2Storage,
) -> Response:
    """Serve a registered-user photograph image from R2.

    Authentication is enforced by the ``require_authenticated_user`` dependency
    before this function runs, so unauthenticated requests and guest principals
    never reach it. Ownership is verified with a single ownership-scoped query
    before any private storage access, so a user can never download another
    user's images and storage is never contacted for nonexistent, foreign, or
    unavailable artifacts.
    """
    if image_type not in _SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image type '{image_type}'. "
                f"Supported: {', '.join(sorted(_SUPPORTED_IMAGE_TYPES))}."
            ),
        )

    # One ownership-scoped query establishes both existence and ownership.
    # Nonexistent and foreign photographs are indistinguishable (404), so no
    # ownership information about another user's photographs is disclosed.
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.original_image_key, p.prediction_mask_key,
                   p.prediction_overlay_key
            FROM photographs p
            JOIN inspections i ON p.inspection_id = i.id
            WHERE p.id = %s AND i.user_id = %s
            """,
            (photo_id, user_id),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photograph not found",
        )

    key_map = {
        "original": row["original_image_key"],
        "mask": row["prediction_mask_key"],
        "overlay": row["prediction_overlay_key"],
    }
    image_key = key_map[image_type]

    if not image_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Result type '{image_type}' is not available for this photograph.",
        )

    # --- Download from private storage ---
    try:
        data = storage.download_file(image_key)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve image: {exc}",
        )

    return Response(
        content=data,
        media_type=_CONTENT_TYPE_MAP.get(image_type, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{photo_id}_{image_type}"',
        },
    )


@router.get(
    "/{photo_id}/download/{image_type}",
    summary="Download a photograph image (original, mask, or overlay)",
)
async def download_photograph_image(
    request: Request,
    photo_id: UUID = Path(...),
    image_type: str = Path(...),
    conn=Depends(get_db),
    storage=Depends(get_r2_storage),
    user=Depends(require_authenticated_user),
) -> Response:
    """Download the original photograph, prediction mask, or prediction
    overlay for a registered-user photograph.

    Requires an authenticated registered user (guests and unauthenticated
    requests are rejected). Verifies that the photograph exists and belongs to
    the authenticated user's inspection before accessing private storage.
    Only image types that have been generated or uploaded are downloadable.
    """
    return _download_registered_image(
        photo_id, image_type, user["user_id"], conn, storage
    )