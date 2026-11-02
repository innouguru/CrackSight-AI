"""Shared FastAPI dependencies.

Provides dependency functions for database connections, object storage,
and current user identity that can be injected into route handlers.
"""

from __future__ import annotations

from typing import Generator, Optional

from fastapi import Depends, HTTPException, Request, status

from crack_detection.backend.database import (
    DatabaseError,
    create_guest_session,
    deactivate_guest_session,
    get_db_connection,
    increment_guest_analysis_count,
    validate_guest_session,
)
from crack_detection.backend.storage import R2Storage, get_storage


def get_db() -> Generator:
    """Yield a PostgreSQL connection and ensure it is closed after use."""
    with get_db_connection() as conn:
        yield conn


def get_r2_storage() -> R2Storage:
    """Return a configured R2 storage client."""
    return get_storage()


def get_current_user(request: Request) -> dict:
    """Return the current user identity from request state.

    Returns one of three principal types:

    * Registered user: ``is_authenticated=True, is_guest=False`` with
      ``user_id`` set from the verified Clerk JWT subject.
    * Guest user: ``is_authenticated=False, is_guest=True`` with
      ``guest_session_id`` set from the validated guest session token.
    * Unauthenticated: raises 401.

    Raises 401 if no authenticated user or valid guest session is present.
    """
    if getattr(request.state, "is_authenticated", False):
        return {
            "user_id": request.state.user_id,
            "email": request.state.user_email,
            "is_guest": False,
            "is_authenticated": True,
            "guest_session_id": None,
        }
    if getattr(request.state, "is_guest", False):
        return {
            "user_id": None,
            "email": None,
            "is_guest": True,
            "is_authenticated": False,
            "guest_session_id": request.state.guest_session_id,
        }
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def require_authenticated_user(request: Request) -> dict:
    """Return the current user, requiring authentication (not guest)."""
    user = get_current_user(request)
    if user["is_guest"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registered user authentication required",
        )
    return user


def require_guest_session(request: Request) -> dict:
    """Return the current user identity, requiring a guest session.

    Raises 401 if no guest session is present. Registered users are not
    guests and will be rejected by this dependency.
    """
    user = get_current_user(request)
    if not user["is_guest"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest session required",
        )
    return user


def require_ownership(
    request: Request, resource_user_id: Optional[str]
) -> None:
    """Verify that the current user owns the given resource.

    Raises 403 if the user does not own the resource. Guest users cannot
    own resources.
    """
    user = get_current_user(request)
    if user["is_guest"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest users cannot access this resource",
        )
    if user["user_id"] != resource_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this resource",
        )


def increment_analysis_count(session_id: str, max_analyses: int = 3) -> Optional[int]:
    """Atomically increment a guest session's analysis count.

    Returns the new count if successful, or ``None`` if the session has
    already reached the limit. Uses an atomic conditional UPDATE so
    concurrent requests cannot exceed the allowance.
    """
    return increment_guest_analysis_count(session_id, max_analyses)