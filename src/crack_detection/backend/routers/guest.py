"""Guest session endpoints.

Provides guest session creation, validation, and analysis-count
consumption. Guest sessions allow users to analyse photographs without
creating a registered account, subject to the product's guest limits:

* At most 3 photo analyses per guest session.
* Sessions expire after 24 hours.
* Guest results cannot be transferred into a registered account.
* Guests cannot save inspections or access registered-user history.

Session tokens are server-generated and unpredictable. Client-supplied
session IDs are never treated as proof of authorization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import Response
from PIL import Image as PILImage
from psycopg2.extras import RealDictCursor

from crack_detection.backend.database import (
    cleanup_expired_guest_sessions,
    create_guest_session,
    get_db_connection,
    increment_guest_analysis_count,
    validate_guest_session,
)
from crack_detection.backend.dependencies import get_r2_storage
from crack_detection.backend.inference_service import analyze_image
from crack_detection.backend.storage import R2Storage, StorageError
from crack_detection.backend.schemas import (
    GuestAnalysisConsumeResponse,
    GuestPhotographDownloadResponse,
    GuestPhotographUploadResponse,
    GuestSessionCreateResponse,
    GuestSessionValidateResponse,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Guest session lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=GuestSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a guest session",
)
async def create_guest_session_endpoint() -> GuestSessionCreateResponse:
    """Create a new guest session.

    Returns a session token that the client must send with subsequent
    requests via the ``X-Guest-Session-Token`` header. The session
    allows up to 3 photo analyses and expires after 24 hours.
    """
    session = create_guest_session()
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return GuestSessionCreateResponse(
        session_token=session["session_token"],
        session_id=session["id"],
        expires_at=expires_at,
        max_analyses=3,
        analyses_count=0,
    )


@router.get(
    "/validate",
    response_model=GuestSessionValidateResponse,
    summary="Validate a guest session",
)
async def validate_guest_session_endpoint(
    x_guest_session_token: Optional[str] = Header(
        None, alias="X-Guest-Session-Token"
    ),
) -> GuestSessionValidateResponse:
    """Validate a guest session token.

    Returns the session status including remaining analyses. Expired or
    invalid sessions are rejected.
    """
    if not x_guest_session_token:
        return GuestSessionValidateResponse(
            valid=False,
            session_id=None,
            analyses_count=0,
            max_analyses=3,
            analyses_remaining=0,
            expires_at=None,
        )

    session = validate_guest_session(x_guest_session_token)
    if not session:
        return GuestSessionValidateResponse(
            valid=False,
            session_id=None,
            analyses_count=0,
            max_analyses=3,
            analyses_remaining=0,
            expires_at=None,
        )

    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return GuestSessionValidateResponse(
        valid=True,
        session_id=session["id"],
        analyses_count=session["analyses_count"],
        max_analyses=3,
        analyses_remaining=max(0, 3 - session["analyses_count"]),
        expires_at=expires_at,
    )


@router.post(
    "/consume-analysis",
    response_model=GuestAnalysisConsumeResponse,
    summary="Consume one analysis from a guest session",
)
async def consume_guest_analysis(
    x_guest_session_token: Optional[str] = Header(
        None, alias="X-Guest-Session-Token"
    ),
) -> GuestAnalysisConsumeResponse:
    """Consume one analysis from a guest session.

    Atomically increments the analysis count. Returns ``consumed=True``
    if the analysis was allowed, or ``consumed=False`` if the session
    has reached its limit or is invalid/expired.
    """
    if not x_guest_session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Guest session token required",
        )

    session = validate_guest_session(x_guest_session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired guest session",
        )

    new_count = increment_guest_analysis_count(str(session["id"]), max_analyses=3)
    if new_count is None:
        # Limit reached
        return GuestAnalysisConsumeResponse(
            consumed=False,
            analyses_count=session["analyses_count"],
            max_analyses=3,
            analyses_remaining=0,
        )

    return GuestAnalysisConsumeResponse(
        consumed=True,
        analyses_count=new_count,
        max_analyses=3,
        analyses_remaining=max(0, 3 - new_count),
    )


@router.post(
    "/cleanup-expired",
    summary="Clean up expired guest sessions",
)
async def cleanup_expired_guest_sessions_endpoint() -> dict:
    """Deactivate all expired guest sessions.

    Safe to call periodically. Does not delete registered-user data.
    """
    count = cleanup_expired_guest_sessions()
    return {"deactivated": count}


# ---------------------------------------------------------------------------
# Guest photograph upload
# ---------------------------------------------------------------------------


def _ensure_guest_user(conn) -> str:
    """Ensure a ``guest`` user record exists in the users table.

    Returns the user id used for guest-owned records. This avoids foreign
    key violations when guest photographs reference a user_id that does
    not correspond to a Clerk-registered user.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (id, email, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            ("guest", "guest@cracksight.local", "guest"),
        )
        conn.commit()
    return "guest"


def _ensure_guest_inspection(conn, user_id: str) -> UUID:
    """Ensure a draft inspection exists for the guest user.

    Returns the inspection id. A single draft inspection is reused for
    all guest photographs in a session; guests cannot save inspections.
    """
    inspection_id = uuid4()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO inspections (id, user_id, title, status)
            VALUES (%s, %s, %s, 'draft')
            RETURNING id
            """,
            (inspection_id, user_id, "Guest analysis"),
        )
        conn.commit()
    return inspection_id


@router.post(
    "/photograph",
    response_model=GuestPhotographUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a photograph for guest analysis",
)
async def upload_guest_photograph(
    request: Request,
    x_guest_session_token: Optional[str] = Header(
        None, alias="X-Guest-Session-Token"
    ),
    file: UploadFile = File(...),
    structure_type: str = Form(...),
) -> GuestPhotographUploadResponse:
    """Upload a photograph for a guest session.

    Accepts multipart/form-data with a file and structure type. Validates
    the guest session, the file type and size, then stores the image in
    R2 and creates a photograph record. Returns the photograph id and
    remaining analysis allowance.

    The photograph is not analysed yet — the client must subsequently
    call ``POST /photos/{photo_id}/analyse`` to run crack segmentation.
    """
    # --- Validate guest session ---
    if not x_guest_session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Guest session token required",
        )

    session = validate_guest_session(x_guest_session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired guest session",
        )

    session_id = str(session["id"])
    analyses_remaining = max(0, 3 - session["analyses_count"])

    if analyses_remaining < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guest analysis limit reached (3 analyses per session)",
        )

    # --- Validate file type ---
    filename = file.filename or "upload"
    content_type = file.content_type or "application/octet-stream"
    allowed_extensions = {"jpg", "jpeg", "png", "webp"}
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed_extensions))}.",
        )

    # --- Read and validate file content ---
    file_bytes = await file.read()
    max_size = 10 * 1024 * 1024  # 10 MB
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is larger than the {max_size // (1024 * 1024)} MB limit.",
        )

    # Validate that the file is a readable image.
    try:
        img = PILImage.open(BytesIO(file_bytes))
        img.verify()
        img = PILImage.open(BytesIO(file_bytes))
        img.convert("RGB")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unreadable image file: {exc}",
        )

    # --- Validate structure type ---
    if structure_type not in {"wall", "beam", "column"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid structure type '{structure_type}'. Must be one of: wall, beam, column.",
        )

    # --- Ensure guest user and inspection exist ---
    user_id = "guest"

    # --- Upload to R2 ---
    storage = get_r2_storage()

    photograph_id = uuid4()
    original_key = f"guest/{session_id}/originals/{photograph_id}.{ext}"

    try:
        storage.upload_file(original_key, file_bytes, content_type)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store uploaded image: {exc}",
        )

    # --- Create photograph record in a single transaction ---
    try:
        with get_db_connection() as conn:
            # Ensure guest user exists.
            _ensure_guest_user(conn)

            # Ensure a draft inspection exists for the guest.
            inspection_id = _ensure_guest_inspection(conn, user_id)

            # Insert the photograph record.
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO photographs (
                        id, inspection_id, user_id, structure_type,
                        verification_status, original_image_key
                    )
                    VALUES (%s, %s, %s, %s, 'not_verified', %s)
                    RETURNING id, structure_type, original_image_key, created_at
                    """,
                    (
                        photograph_id,
                        inspection_id,
                        user_id,
                        structure_type,
                        original_key,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
    except Exception:
        # Clean up the uploaded object if we can't create the record.
        try:
            storage.delete_file(original_key)
        except StorageError:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create photograph record.",
        )

    return GuestPhotographUploadResponse(
        photograph_id=row["id"],
        session_id=session["id"],
        structure_type=row["structure_type"],
        original_image_key=row["original_image_key"],
        file_size=len(file_bytes),
        content_type=content_type,
        analyses_remaining=analyses_remaining,
    )


# ---------------------------------------------------------------------------
# Guest result download
# ---------------------------------------------------------------------------


def _download_guest_result(
    photo_id: UUID,
    file_type: str,
    x_guest_session_token: Optional[str],
) -> Response:
    """Serve a guest result file from R2 after verifying session ownership."""
    # --- Validate guest session ---
    if not x_guest_session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Guest session token required",
        )

    session = validate_guest_session(x_guest_session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired guest session",
        )

    # --- Verify photograph ownership ---
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.original_image_key, p.prediction_mask_key,
                       p.prediction_overlay_key, p.user_id
                FROM photographs p
                WHERE p.id = %s
                """,
                (photo_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photograph not found",
        )

    # Guests can only access their own photographs (user_id = "guest").
    if row["user_id"] != "guest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this photograph.",
        )

    # --- Select the correct R2 key ---
    key_map = {
        "original": row["original_image_key"],
        "mask": row["prediction_mask_key"],
        "overlay": row["prediction_overlay_key"],
    }
    key = key_map.get(file_type)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Result type '{file_type}' is not available.",
        )

    # --- Download from R2 ---
    storage = get_r2_storage()
    try:
        data = storage.download_file(key)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve result: {exc}",
        )

    content_type_map = {
        "original": "image/jpeg",
        "mask": "image/png",
        "overlay": "image/png",
    }

    return Response(
        content=data,
        media_type=content_type_map.get(file_type, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{photo_id}_{file_type}"',
        },
    )


@router.get(
    "/photograph/{photo_id}/original",
    summary="Download the original uploaded photograph",
)
async def download_guest_original(
    photo_id: UUID,
    x_guest_session_token: Optional[str] = Header(
        None, alias="X-Guest-Session-Token"
    ),
) -> Response:
    """Download the original photograph for a guest photograph.

    Verifies guest-session ownership before serving the object from R2.
    Returns the image bytes with the original content type.
    """
    return _download_guest_result(photo_id, "original", x_guest_session_token)


@router.get(
    "/photograph/{photo_id}/mask",
    summary="Download the predicted crack mask",
)
async def download_guest_mask(
    photo_id: UUID,
    x_guest_session_token: Optional[str] = Header(
        None, alias="X-Guest-Session-Token"
    ),
) -> Response:
    """Download the predicted crack mask for a guest photograph."""
    return _download_guest_result(photo_id, "mask", x_guest_session_token)


@router.get(
    "/photograph/{photo_id}/overlay",
    summary="Download the original photograph with crack overlay",
)
async def download_guest_overlay(
    photo_id: UUID,
    x_guest_session_token: Optional[str] = Header(
        None, alias="X-Guest-Session-Token"
    ),
) -> Response:
    """Download the overlay (original + mask) for a guest photograph."""
    return _download_guest_result(photo_id, "overlay", x_guest_session_token)
