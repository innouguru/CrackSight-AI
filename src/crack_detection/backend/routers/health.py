"""Health check endpoints.

Provides liveness and readiness probes. Health checks never expose
credentials, environment variables, internal paths, or sensitive
infrastructure details.
"""

from __future__ import annotations

from fastapi import APIRouter

from crack_detection.backend.config import get_settings

router = APIRouter()


@router.get("/live", response_model=dict, summary="Liveness probe")
async def liveness() -> dict:
    """Return whether the application process is alive.

    Does not check external dependencies (database, storage, inference).
    """
    settings = get_settings()
    return {
        "status": "alive",
        "service": settings.app_name,
        "version": "0.1.0",
    }


@router.get("/ready", response_model=dict, summary="Readiness probe")
async def readiness() -> dict:
    """Return whether the application is ready to serve requests.

    Checks configured dependencies without exposing sensitive details.
    Unknown/unconfigured services are reported as ``not_configured``,
    never as healthy.
    """
    settings = get_settings()
    checks: dict = {
        "database": "not_configured",
        "storage": "not_configured",
        "inference_service": "not_configured",
    }
    all_ready = True

    # Database — check if URL is configured (placeholder, not a real connection)
    if settings.database_url and "CHANGE_ME" not in settings.database_url:
        checks["database"] = "configured"
    else:
        all_ready = False

    # Storage — check if R2 is configured
    if settings.r2_bucket_name and "CHANGE_ME" not in settings.r2_bucket_name:
        checks["storage"] = "configured"
    else:
        all_ready = False

    # Inference service — check if URL is configured
    if settings.inference_service_url and "localhost" in settings.inference_service_url:
        checks["inference_service"] = "local"
    elif settings.inference_service_url and "CHANGE_ME" not in settings.inference_service_url:
        checks["inference_service"] = "configured"
    else:
        all_ready = False

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
        "service": settings.app_name,
        "version": "0.1.0",
    }
