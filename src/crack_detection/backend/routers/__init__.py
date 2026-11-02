"""API router package."""

from fastapi import APIRouter

from crack_detection.backend.routers.auth import router as auth_router
from crack_detection.backend.routers.guest import router as guest_router
from crack_detection.backend.routers.health import router as health_router
from crack_detection.backend.routers.inspections import router as inspections_router
from crack_detection.backend.routers.photographs import router as photographs_router
from crack_detection.backend.routers.reports import router as reports_router

__all__ = [
    "guest_router",
    "health_router",
    "auth_router",
    "inspections_router",
    "photographs_router",
    "reports_router",
]
