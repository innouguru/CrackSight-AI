"""Centralized exception handling for the FastAPI application.

Defines custom application exceptions and registers them with the
FastAPI app so all error responses follow a consistent format.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from crack_detection.backend.config import get_settings

_settings = get_settings()


class APIError(Exception):
    """Base application exception with structured error details."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "api_error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        action: Optional[str] = None,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.action = action
        self.retryable = retryable
        self.details = details or {}


class ValidationError(APIError):
    """Raised when input validation fails (HTTP 400)."""

    def __init__(
        self,
        message: str,
        *,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            error_code="validation_error",
            status_code=status.HTTP_400_BAD_REQUEST,
            action=action,
            retryable=False,
            details=details,
        )


class NotFoundError(APIError):
    """Raised when a requested resource does not exist (HTTP 404)."""

    def __init__(
        self,
        message: str,
        *,
        action: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            error_code="not_found",
            status_code=status.HTTP_404_NOT_FOUND,
            action=action,
            retryable=False,
        )


class ForbiddenError(APIError):
    """Raised when a user lacks permission for an operation (HTTP 403)."""

    def __init__(
        self,
        message: str,
        *,
        action: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            error_code="forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            action=action,
            retryable=False,
        )


class UnauthorizedError(APIError):
    """Raised when authentication is required or failed (HTTP 401)."""

    def __init__(
        self,
        message: str = "Authentication required",
        *,
        action: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            error_code="unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
            action=action,
            retryable=False,
        )


class ServiceUnavailableError(APIError):
    """Raised when an external dependency is unavailable (HTTP 503)."""

    def __init__(
        self,
        message: str,
        *,
        action: Optional[str] = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(
            message,
            error_code="service_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            action=action,
            retryable=retryable,
        )


def _error_response(exc: APIError) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "error": exc.error_code,
        "message": exc.message,
        "retryable": exc.retryable,
    }
    if exc.action:
        body["action"] = exc.action
    if exc.details:
        body["details"] = exc.details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app."""

    @app.exception_handler(APIError)
    async def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_error_response(exc))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_response(
                ValidationError(
                    "Request validation failed",
                    details={"errors": exc.errors()},
                )
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        if _settings.debug:
            import traceback

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "internal_error",
                    "message": str(exc),
                    "retryable": False,
                    "details": {"traceback": traceback.format_exc()},
                },
            )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred.",
                "retryable": False,
            },
        )
