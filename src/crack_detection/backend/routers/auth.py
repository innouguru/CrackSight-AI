"""Authentication endpoints (Clerk integration).

Provides sign-in URL generation, OAuth callback handling, and token
verification. Clerk owns registered-user sign-in, account creation,
password handling, Google OAuth, and its hosted authentication flow.
The FastAPI backend verifies Clerk-issued JWT tokens and provides a
token verification endpoint for the frontend.

Registered-user sign-in flows (email/password + Google) are handled by
Clerk's frontend SDK and hosted pages. This backend does not implement
custom password storage, password verification, or Google OAuth
credentials.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from crack_detection.backend.config import get_settings
from crack_detection.backend.middleware import _verify_clerk_jwt
from crack_detection.backend.schemas import SignInUrlResponse, TokenVerifyResponse

router = APIRouter()
_settings = get_settings()


@router.get("/sign-in-url", response_model=SignInUrlResponse, summary="Get Clerk sign-in URL")
async def sign_in_url() -> SignInUrlResponse:
    """Return the Clerk sign-in URL for the configured instance."""
    settings = get_settings()
    return SignInUrlResponse(
        sign_in_url=f"https://{settings.clerk_jwt_issuer.replace('https://', '')}/sign-in"
        if settings.clerk_jwt_issuer and "CHANGE_ME" not in settings.clerk_jwt_issuer
        else "https://clerk.accounts.com/sign-in"
    )


@router.get("/callback", summary="Clerk OAuth callback handler")
async def auth_callback(request: Request) -> dict:
    """Handle Clerk OAuth callback (Google, email/password, etc.).

    The actual callback processing is delegated to Clerk's frontend SDK.
    This endpoint exists for route completeness and can forward to the
    Clerk-hosted sign-in page.
    """
    return {
        "message": "Clerk OAuth callback endpoint",
        "note": "Clerk handles sign-in, account creation, password handling, "
        "and Google OAuth via its hosted pages and frontend SDK.",
    }


@router.post("/verify", response_model=TokenVerifyResponse, summary="Verify Clerk token")
async def verify_token(request: Request) -> TokenVerifyResponse:
    """Verify a Clerk JWT token from the Authorization header.

    Extracts the Bearer token, verifies it against Clerk's JWKS, and
    returns the authenticated user identity if valid.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return TokenVerifyResponse(valid=False, user_id=None, email=None)

    token = auth_header.split(" ", 1)[1]
    settings = get_settings()
    result = await _verify_clerk_jwt(token, settings)
    if result:
        user_id, email = result
        return TokenVerifyResponse(valid=True, user_id=user_id, email=email)

    return TokenVerifyResponse(valid=False, user_id=None, email=None)
