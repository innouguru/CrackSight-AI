"""Shared FastAPI dependencies.

Provides dependency functions for database connections, object storage,
and current user identity that can be injected into route handlers.
"""

from __future__ import annotations

from typing import Generator, Optional

from fastapi import Depends, HTTPException, Request, status

from crack_detection.backend.database import DatabaseError, get_db_connection
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

    Raises 401 if no authenticated user is present. Guest requests return
    a guest identity with ``is_guest=True``.
    """
    if getattr(request.state, "is_authenticated", False):
        return {
            "user_id": request.state.user_id,
            "email": request.state.user_email,
            "is_guest": False,
            "is_authenticated": True,
        }
    if getattr(request.state, "is_guest", False):
        return {
            "user_id": None,
            "email": None,
            "is_guest": True,
            "is_authenticated": False,
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
