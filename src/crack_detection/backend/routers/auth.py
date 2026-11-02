"""Authentication endpoints (Clerk integration).

Provides sign-in URL generation, OAuth callback handling, and token
verification. Full Clerk integration (email/password + Google) is
completed in Milestone 3; this milestone establishes the endpoint
structure and token verification middleware skeleton.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from crack_detection.backend.config import get_settings
from crack_detection.backend.schemas import SignInUrlResponse, TokenVerifyResponse

router = APIRouter()
_settings = get_settings()


@router.get("/sign-in-url", response_model=SignInUrlResponse, summary="Get Clerk sign-in URL")
async def sign_in_url() -> SignInUrlResponse:
    """Return the Clerk sign-in URL for the configured instance."""
    return SignInUrlResponse(
        sign_in_url=f"https://{_settings.clerk_jwt_issuer.replace('https://', '')}/sign-in"
        if _settings.clerk_jwt_issuer and "CHANGE_ME" not in _settings.clerk_jwt_issuer
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
        "note": "Full Clerk integration completed in Milestone 3.",
    }


@router.post("/verify", response_model=TokenVerifyResponse, summary="Verify Clerk token")
async def verify_token(request: Request) -> TokenVerifyResponse:
    """Verify a Clerk JWT token from the request state.

    Returns the authenticated user identity if a valid token was provided
    via the middleware.
    """
    user_id = getattr(request.state, "user_id", None)
    email = getattr(request.state, "user_email", None)
    is_authenticated = getattr(request.state, "is_authenticated", False)

    return TokenVerifyResponse(
        valid=is_authenticated,
        user_id=user_id,
        email=email,
    )
