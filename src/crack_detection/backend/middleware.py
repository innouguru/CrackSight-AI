"""Clerk authentication middleware.

Verifies Clerk JWT tokens on protected routes and attaches the authenticated
user identity to the request state. Public endpoints (health, auth sign-in
URL) are exempt from verification.

Guest sessions are tracked separately via the ``X-Guest-Session-Token``
header and are distinct from Clerk-authenticated registered users.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional, Set, Tuple

import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED

from crack_detection.backend.config import get_settings
from crack_detection.backend.dependencies import validate_guest_session

logger = logging.getLogger(__name__)

# Paths that do not require authentication.
PUBLIC_PATHS: Set[str] = {
    "/",
    "/docs",
    "/openapi.json",
    "/live",
    "/ready",
    "/auth/sign-in-url",
    "/auth/callback",
    "/auth/verify",
    "/guest/session",
}

# Header name for guest session tokens.
GUEST_SESSION_HEADER = "X-Guest-Session-Token"

# JWKS cache: issuer -> (expires_at, keys_dict)
_JWKS_CACHE: dict[str, Tuple[float, list]] = {}
_JWKS_CACHE_TTL_SECONDS = 3600  # 1 hour


def _jwks_cache_get(issuer: str) -> Optional[list]:
    """Return cached JWKS keys for the issuer if not expired."""
    entry = _JWKS_CACHE.get(issuer)
    if entry is None:
        return None
    expires_at, keys = entry
    if time.time() > expires_at:
        return None
    return keys


def _jwks_cache_set(issuer: str, keys: list) -> None:
    """Cache JWKS keys for the issuer with TTL."""
    _JWKS_CACHE[issuer] = (time.time() + _JWKS_CACHE_TTL_SECONDS, keys)


async def _fetch_jwks(jwks_url: str) -> list:
    """Fetch Clerk JWKS keys from the given URL with a reasonable timeout."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        return resp.json().get("keys", [])


async def _verify_clerk_jwt(token: str, settings) -> Optional[Tuple[str, Optional[str]]]:
    """Verify a Clerk JWT and return (user_id, email) or (None, None).

    Uses Clerk's JWKS endpoint to verify the signature, validates issuer,
    and expiration. Fails closed on any error. Never treats an unverified
    JWT payload as an authenticated identity.
    """
    if not token:
        return None

    issuer = settings.clerk_jwt_issuer
    jwks_url = settings.clerk_jwks_url

    if not issuer or not jwks_url:
        logger.warning("Clerk issuer or JWKS URL not configured")
        return None

    try:
        # Decode without verification first to get the key ID (kid).
        unverified = jwt.get_unverified_header(token)
        kid = unverified.get("kid")
        if not kid:
            logger.warning("JWT missing kid header")
            return None

        # Fetch and cache JWKS keys.
        keys = _jwks_cache_get(issuer)
        if keys is None:
            keys = await _fetch_jwks(jwks_url)
            _jwks_cache_set(issuer, keys)

        # Find the matching public key.
        public_key = None
        for key in keys:
            if key.get("kid") == kid:
                public_key = key
                break

        if public_key is None:
            logger.warning("No matching JWKS key for kid=%s", kid)
            return None

        # Verify the JWT signature and claims using python-jose.
        # python-jose accepts a JWKS key dict directly as the key parameter.
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": False,
            },
        )

        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id:
            logger.warning("JWT missing subject claim")
            return None

        return user_id, email

    except Exception as exc:  # noqa: BLE001 — fail closed on any JWT error
        logger.warning("Clerk JWT verification failed: %s", exc)
        return None


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that verifies Clerk JWT tokens and guest session tokens.

    Clerk-registered users are authenticated via Bearer JWT verification.
    Guest sessions are authenticated via the ``X-Guest-Session-Token`` header.
    The two principal types are mutually exclusive and isolated.
    """

    def __init__(self, app: Callable) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Attach empty user state by default.
        request.state.user_id = None
        request.state.user_email = None
        request.state.is_authenticated = False
        request.state.is_guest = False
        request.state.guest_session_id = None

        # Determine if the path requires authentication.
        path = request.url.path
        is_public = path in PUBLIC_PATHS or any(
            path.startswith(p + "/") for p in PUBLIC_PATHS if p != "/"
        )

        # Check for Clerk Bearer token (registered user).
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            settings = get_settings()
            result = await _verify_clerk_jwt(token, settings)
            if result:
                user_id, email = result
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
            # Check for guest session token.
            guest_token = request.headers.get(GUEST_SESSION_HEADER)
            if guest_token:
                session = await validate_guest_session(guest_token)
                if session:
                    request.state.is_guest = True
                    request.state.guest_session_id = session["id"]
                elif not is_public:
                    return JSONResponse(
                        status_code=HTTP_401_UNAUTHORIZED,
                        content={
                            "error": "unauthorized",
                            "message": "Invalid or expired guest session.",
                            "retryable": False,
                            "action": "Create a new guest session.",
                        },
                    )
            elif not is_public:
                # No auth header and no guest session token on protected route.
                return JSONResponse(
                    status_code=HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "unauthorized",
                        "message": "Authentication required.",
                        "retryable": False,
                        "action": "Sign in or create a guest session.",
                    },
                )

        return await call_next(request)
