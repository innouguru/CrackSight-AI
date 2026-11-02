"""Clerk authentication middleware.

Verifies Clerk JWT tokens on protected routes and attaches the authenticated
user identity to the request state. Public endpoints (health, auth sign-in
URL) are exempt from verification.
"""

from __future__ import annotations

import logging
from typing import Callable, Set

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED

logger = logging.getLogger(__name__)

# Paths that do not require authentication.
PUBLIC_PATHS: Set[str] = {
    "/",
    "/docs",
    "/openapi.json",
    "/health/live",
    "/health/ready",
    "/auth/sign-in-url",
    "/auth/callback",
}


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that verifies Clerk JWT tokens on protected routes."""

    def __init__(self, app: Callable) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Attach empty user state by default.
        request.state.user_id = None
        request.state.user_email = None
        request.state.is_authenticated = False
        request.state.is_guest = False

        # Determine if the path requires authentication.
        path = request.url.path
        is_public = path in PUBLIC_PATHS or any(
            path.startswith(p + "/") for p in PUBLIC_PATHS if p != "/"
        )

        # Check for Authorization header.
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            user_id, email = self._verify_clerk_token(token)
            if user_id:
                request.state.user_id = user_id
                request.state.user_email = email
                request.state.is_authenticated = True
                request.state.is_guest = False
            elif not is_public:
                return JSONResponse(
                    status_code=HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "unauthorized",
                        "message": "Invalid or expired Clerk token.",
                        "retryable": False,
                        "action": "Sign in again or provide a valid token.",
                    },
                )
        elif not is_public:
            # Guest access — allow with no user identity.
            request.state.is_guest = True

        return await call_next(request)

    @staticmethod
    def _verify_clerk_token(token: str) -> tuple:
        """Verify a Clerk JWT and return (user_id, email) or (None, None).

        Production verification should use Clerk's JWKS endpoint. For now,
        this is a skeleton that returns None; the full implementation is
        deferred to Milestone 3 (Authentication) per ROADMAP.md sequencing.
        """
        # TODO: Implement Clerk JWT verification using jose/jwt with Clerk JWKS.
        # This is intentionally a stub for Milestone 2 foundation.
        # Milestone 3 will complete Clerk integration (email/password + Google).
        return None, None
