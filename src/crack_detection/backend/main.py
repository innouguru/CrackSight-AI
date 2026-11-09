"""FastAPI application entry point.

Creates and configures the FastAPI application, registers routers,
middleware, and exception handlers. This is the module referenced by
``uvicorn main:app`` for local development.
"""

from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crack_detection.backend.config import get_settings
from crack_detection.backend.exceptions import register_exception_handlers
from crack_detection.backend.inference_service import (
    reset_pipeline_for_testing,
    get_pipeline,
    analyze_image,
)
from crack_detection.backend.middleware import ClerkAuthMiddleware
from crack_detection.backend.routers import (
    auth_router,
    guest_router,
    health_router,
    inspections_router,
    photographs_router,
    reports_router,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Global pipeline instance — loaded once at application startup.
# ------------------------------------------------------------------

_pipeline_loaded_at: Optional[float] = None


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    # Fresh settings per build: environment-driven configuration (CORS
    # origins, debug, title) must reflect the environment active when this
    # app is created, not a module-import snapshot.
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="AI-assisted building inspection backend for crack detection.",
        version="0.1.0",
        debug=settings.debug,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # ------------------------------------------------- authentication middleware
    # Registered BEFORE CORS. Starlette executes the most-recently added
    # middleware first, so this ordering makes CORSMiddleware the outermost
    # layer: browser OPTIONS preflights are answered by CORS without any
    # Clerk JWT, while non-preflight requests still pass through Clerk
    # authentication, and CORS headers (including an allowed explicit
    # origin) are appended even to authentication error responses.
    app.add_middleware(ClerkAuthMiddleware)

    # ------------------------------------------------------------------ CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------ exception handlers
    register_exception_handlers(app)

    # ------------------------------------------------------------------ routers
    app.include_router(health_router, tags=["health"])
    app.include_router(auth_router, prefix="/auth", tags=["authentication"])
    app.include_router(guest_router, prefix="/guest/session", tags=["guest"])
    app.include_router(
        inspections_router, prefix="/inspections", tags=["inspections"]
    )
    app.include_router(
        photographs_router, prefix="/photos", tags=["photographs"]
    )
    app.include_router(reports_router, prefix="/reports", tags=["reports"])

    # ------------------------------------------------------------------ startup
    app.add_event_handler("startup", _startup_event)

    # ------------------------------------------------------------------ root
    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        """Root endpoint returning basic service information."""
        return {
            "service": settings.app_name,
            "version": "0.1.0",
            "status": "operational",
            "docs": "/docs" if settings.debug else "disabled",
        }

    return app


async def _startup_event() -> None:
    """Load the inference pipeline once when the application starts.

    Registered by ``create_app`` via ``app.add_event_handler`` so that no
    module-level code dereferences ``app`` before the factory has created it.
    """
    global _pipeline_loaded_at

    from crack_detection.backend import inference_service

    inference_service.reset_pipeline_for_testing()

    start = __import__("time").time()
    try:
        inference_service._load_pipeline()  # type: ignore[attr-defined]
        _pipeline_loaded_at = __import__("time").time() - start
        logger.info("Inference pipeline loaded at startup")
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Inference pipeline failed to load at startup: %s", exc)
        _pipeline_loaded_at = None


# Module-level application instance exposing ``crack_detection.backend.main:app``
# as the Uvicorn entry point.
app = create_app()
