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
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from crack_detection.backend.database import (
    cleanup_expired_guest_sessions,
    create_guest_session,
    increment_guest_analysis_count,
    validate_guest_session,
)
from crack_detection.backend.dependencies import increment_analysis_count
from crack_detection.backend.schemas import (
    GuestAnalysisConsumeResponse,
    GuestSessionCreateResponse,
    GuestSessionValidateResponse,
)

router = APIRouter()


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
    if expires_at.tzinfo is None:
        from datetime import timezone as _tz

        expires_at = expires_at.replace(tzinfo=_tz.utc)

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

    new_count = increment_analysis_count(str(session["id"]), max_analyses=3)
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
