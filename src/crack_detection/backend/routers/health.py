"""Health check endpoints.

Provides liveness and readiness probes. Health checks never expose
credentials, environment variables, internal paths, or sensitive
infrastructure details.
"""

from __future__ import annotations

from fastapi import APIRouter

from crack_detection.backend.config import get_settings

router = APIRouter()
_settings = get_settings()


@router.get("/live", response_model=dict, summary="Liveness probe")
async def liveness() -> dict:
    """Return whether the application process is alive.

    Does not check external dependencies (database, storage, inference).
    """
    return {
        "status": "alive",
        "service": _settings.app_name,
        "version": "0.1.0",
    }


@router.get("/ready", response_model=dict, summary="Readiness probe")
async def readiness() -> dict:
    """Return whether the application is ready to serve requests.

    Checks configured dependencies without exposing sensitive details.
    Unknown/unconfigured services are reported as ``not_configured``,
    never as healthy.
    """
    checks: dict = {
        "database": "not_configured",
        "storage": "not_configured",
        "inference_service": "not_configured",
    }
    all_ready = True

    # Database — check if URL is configured (placeholder, not a real connection)
    if _settings.database_url and "CHANGE_ME" not in _settings.database_url:
        checks["database"] = "configured"
    else:
        all_ready = False

    # Storage — check if R2 is configured
    if _settings.r2_bucket_name and "CHANGE_ME" not in _settings.r2_bucket_name:
        checks["storage"] = "configured"
    else:
        all_ready = False

    # Inference service — check if URL is configured
    if _settings.inference_service_url and "localhost" in _settings.inference_service_url:
        checks["inference_service"] = "local"
    elif _settings.inference_service_url and "CHANGE_ME" not in _settings.inference_service_url:
        checks["inference_service"] = "configured"
    else:
        all_ready = False

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
        "service": _settings.app_name,
        "version": "0.1.0",
    }
