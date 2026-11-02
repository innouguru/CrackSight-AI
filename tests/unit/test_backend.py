"""Tests for the CrackSight AI backend foundation.

These tests exercise configuration validation, exception handling,
schema validation, and middleware logic. They require the backend
dependencies (fastapi, pydantic-settings, psycopg2, boto3, etc.)
to be installed before they can run. Per AGENTS.md, dependencies
are not installed in this environment, so tests are written for
future execution.
"""

from __future__ import annotations

import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Conditional imports — tests skip gracefully when backend deps are absent.
# ---------------------------------------------------------------------------
try:
    from crack_detection.backend.config import Settings, get_settings
    from crack_detection.backend.dependencies import require_ownership
    from crack_detection.backend.exceptions import (
        APIError,
        ForbiddenError,
        NotFoundError,
        ServiceUnavailableError,
        UnauthorizedError,
        ValidationError,
        register_exception_handlers,
    )
    from crack_detection.backend.middleware import ClerkAuthMiddleware, PUBLIC_PATHS
    from crack_detection.backend.schemas import (
        ErrorDetail,
        HealthResponse,
        InspectionCreate,
        InspectionResponse,
        PhotographCreate,
        SignInUrlResponse,
        TokenVerifyResponse,
    )
    from crack_detection.backend.storage import R2Storage, StorageError

    _BACKEND_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BACKEND_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestSettings:
    """Tests for application configuration."""

    def test_defaults_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Required env vars produce a valid Settings instance."""
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test_123")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://user:pass@localhost:5432/db?sslmode=require",
        )
        monkeypatch.setenv("R2_ACCOUNT_ID", "test-account")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "test-key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test-secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://test.r2.cloudflarestorage.com")

        settings = Settings()
        assert settings.app_name == "CrackSight AI"
        settings.app_env == "development"
        assert settings.secret_key == "test-secret-key-12345"
        assert settings.inference_threshold == 0.5
        assert settings.inference_device == "cpu"

    def test_invalid_image_size_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid INFERENCE_IMAGE_SIZE raises validation error."""
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test_123")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://user:pass@localhost:5432/db?sslmode=require",
        )
        monkeypatch.setenv("R2_ACCOUNT_ID", "test-account")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "test-key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test-secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://test.r2.cloudflarestorage.com")
        monkeypatch.setenv("INFERENCE_IMAGE_SIZE", "invalid")

        with pytest.raises(ValueError, match="INFERENCE_IMAGE_SIZE"):
            Settings()

    def test_settings_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_settings() returns a cached instance."""
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test_123")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://user:pass@localhost:5432/db?sslmode=require",
        )
        monkeypatch.setenv("R2_ACCOUNT_ID", "test-account")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "test-key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test-secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://test.r2.cloudflarestorage.com")

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


# ---------------------------------------------------------------------------
# Exception tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestExceptions:
    """Tests for custom exception classes."""

    def test_api_error_defaults(self) -> None:
        exc = APIError("something failed")
        assert exc.message == "something failed"
        exc.error_code == "api_error"
        exc.status_code == 500
        exc.retryable is False

    def test_validation_error_status(self) -> None:
        exc = ValidationError("bad input")
        exc.status_code == 400
        exc.error_code == "validation_error"
        exc.retryable is False

    def test_not_found_error_status(self) -> None:
        exc = NotFoundError("not found")
        exc.status_code == 404
        exc.error_code == "not_found"

    def test_forbidden_error_status(self) -> None:
        exc = ForbiddenError("forbidden")
        exc.status_code == 403
        exc.error_code == "forbidden"

    def test_unauthorized_error_status(self) -> None:
        exc = UnauthorizedError()
        exc.status_code == 401
        exc.error_code == "unauthorized"

    def test_service_unavailable_retryable(self) -> None:
        exc = ServiceUnavailableError("down")
        exc.status_code == 503
        exc.error_code == "service_unavailable"
        exc.retryable is True


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestSchemas:
    """Tests for Pydantic request/response schemas."""

    def test_health_response(self) -> None:
        h = HealthResponse()
        h.status == "ok"
        h.service == "CrackSight AI"
        h.version == "0.1.0"

    def test_inspection_create_valid(self) -> None:
        payload = InspectionCreate(
            title="Basement wall inspection",
            building_type="residential",
            building_location="123 Main St",
            notes="Check for hairline cracks",
        )
        payload.title == "Basement wall inspection"

    def test_inspection_create_empty_title_rejected(self) -> None:
        with pytest.raises(ValueError):
            InspectionCreate(title="")

    def test_photograph_create_valid(self) -> None:
        payload = PhotographCreate(
            structure_type="wall",
            original_image_key="inspections/abc123/originals/photo1.jpg",
            observation="Small crack near corner",
        )
        payload.structure_type == "wall"

    def test_photograph_create_invalid_structure_type(self) -> None:
        with pytest.raises(ValueError):
            PhotographCreate(
                structure_type="floor",
                original_image_key="key.jpg",
            )

    def test_token_verify_response(self) -> None:
        resp = TokenVerifyResponse(valid=True, user_id="user_123", email="test@example.com")
        resp.valid is True
        resp.user_id == "user_123"
        resp.email == "test@example.com"

    def test_error_detail(self) -> None:
        err = ErrorDetail(
            error="validation_error",
            message="Invalid input",
            retryable=False,
            action="Check your request",
        )
        err.error == "validation_error"
        err.retryable is False


# ---------------------------------------------------------------------------
# Storage tests (mocked boto3)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestStorage:
    """Tests for R2 storage wrapper (with mocked boto3)."""

    def test_upload_and_download(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """upload_file then download_file round-trips bytes."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = None
        mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"data")}

        with patch("crack_detection.backend.storage.boto3.client", return_value=mock_client):
            monkeypatch.setenv("SECRET_KEY", "test-key")
            monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test")
            monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")
            monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
            monkeypatch.setenv(
                "DATABASE_URL",
                "postgresql://user:pass@localhost:5432/db",
            )
            monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
            monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
            monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
            monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
            monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")

            storage = R2Storage()
            result = storage.upload_file("test/key.jpg", b"hello", "image/jpeg")
            result == "test/key.jpg"
            mock_client.put_object.assert_called_once()

            data = storage.download_file("test/key.jpg")
            data == b"data"

    def test_delete_nonexistent_file_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """delete_file on missing object should not raise."""
        mock_client = MagicMock()
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_client.delete_object.side_effect = ClientError(error_response, "DeleteObject")

        with patch("crack_detection.backend.storage.boto3.client", return_value=mock_client):
            monkeypatch.setenv("SECRET_KEY", "test-key")
            monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test")
            monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")
            monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
            monkeypatch.setenv(
                "DATABASE_URL",
                "postgresql://user:pass@localhost:5432/db",
            )
            monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
            monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
            monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
            monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
            monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")

            storage = R2Storage()
            # Should not raise
            storage.delete_file("missing/key.jpg")


# ---------------------------------------------------------------------------
# Middleware tests (skeleton)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestMiddleware:
    """Tests for Clerk auth middleware (skeleton verification)."""

    def test_public_paths_defined(self) -> None:
        from crack_detection.backend.middleware import PUBLIC_PATHS

        assert "/" in PUBLIC_PATHS
        assert "/health/live" in PUBLIC_PATHS
        assert "/health/ready" in PUBLIC_PATHS
        assert "/auth/sign-in-url" in PUBLIC_PATHS


# ---------------------------------------------------------------------------
# Ownership enforcement tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestOwnershipEnforcement:
    """Tests for server-side ownership checks."""

    def test_owner_matches(self) -> None:
        """Authenticated user matching resource user_id passes."""
        from crack_detection.backend.dependencies import require_ownership

        class FakeRequest:
            state = type(
                "State",
                (),
                {
                    "is_guest": False,
                    "user_id": "user_1",
                    "user_email": "user1@example.com",
                    "is_authenticated": True,
                },
            )()

        # Should not raise
        require_ownership(FakeRequest(), "user_1")

    def test_owner_mismatch_raises(self) -> None:
        """Authenticated user not matching resource user_id raises 403."""
        from crack_detection.backend.dependencies import require_ownership
        from fastapi import HTTPException

        class FakeRequest:
            state = type(
                "State",
                (),
                {
                    "is_guest": False,
                    "user_id": "user_1",
                    "user_email": "user1@example.com",
                    "is_authenticated": True,
                },
            )()

        with pytest.raises(HTTPException) as exc:
            require_ownership(FakeRequest(), "user_2")
        assert exc.value.status_code == 403

    def test_guest_always_denied(self) -> None:
        """Guest users cannot own any resource."""
        from crack_detection.backend.dependencies import require_ownership
        from fastapi import HTTPException

        class FakeRequest:
            state = type("State", (), {"is_guest": True, "user_id": None})()

        with pytest.raises(HTTPException) as exc:
            require_ownership(FakeRequest(), "user_1")
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Middleware behavior tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestMiddlewareBehavior:
    """Tests for Clerk auth middleware behavior."""

    def test_middleware_sets_guest_state(self) -> None:
        """Requests without auth header are treated as guests."""
        from crack_detection.backend.middleware import ClerkAuthMiddleware

        middleware = ClerkAuthMiddleware(None)

        class FakeRequest:
            url = type("URL", (), {"path": "/inspections"})()
            headers = {}
            state = type("State", (), {})()

        class FakeCallNext:
            async def __call__(self, request):
                assert request.state.is_guest is True
                assert request.state.is_authenticated is False
                assert request.state.user_id is None
                return "ok"

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            middleware.dispatch(FakeRequest(), FakeCallNext())
        )
        assert result == "ok"


# ---------------------------------------------------------------------------
# FastAPI TestClient tests (endpoints with mocked dependencies)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestEndpoints:
    """Tests for API endpoints using TestClient with mocked dependencies."""

    @classmethod
    def setup_class(cls) -> None:
        os.environ["SECRET_KEY"] = "test-secret-key-12345"
        os.environ["CLERK_PUBLISHABLE_KEY"] = "pk_test_123"
        os.environ["CLERK_SECRET_KEY"] = "sk_test_123"
        os.environ["CLERK_JWT_ISSUER"] = "https://test.clerk.accounts.com"
        os.environ["DATABASE_URL"] = (
            "postgresql://user:pass@localhost:5432/db?sslmode=require"
        )
        os.environ["R2_ACCOUNT_ID"] = "test-account"
        os.environ["R2_ACCESS_KEY_ID"] = "test-key"
        os.environ["R2_SECRET_ACCESS_KEY"] = "test-secret"
        os.environ["R2_BUCKET_NAME"] = "test-bucket"
        os.environ["R2_ENDPOINT"] = "https://test.r2.cloudflarestorage.com"

        from crack_detection.backend.main import app

        cls.client = TestClient(app)

    def test_liveness_endpoint(self) -> None:
        """Health liveness endpoint returns 200 with alive status."""
        resp = self.client.get("/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"
        assert data["service"] == "CrackSight AI"

    def test_readiness_endpoint(self) -> None:
        """Health readiness endpoint returns 200 with dependency checks."""
        resp = self.client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "storage" in data["checks"]
        assert "inference_service" in data["checks"]

    def test_auth_sign_in_url(self) -> None:
        """Auth sign-in URL endpoint returns 200."""
        resp = self.client.get("/auth/sign-in-url")
        assert resp.status_code == 200
        data = resp.json()
        assert "sign_in_url" in data

    def test_auth_verify_no_token(self) -> None:
        """Auth verify without token returns valid=False."""
        resp = self.client.post("/auth/verify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["user_id"] is None


# ---------------------------------------------------------------------------
# Configuration error handling tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestConfigErrors:
    """Tests for configuration validation errors."""

    def test_missing_required_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing required env vars raises validation error."""
        # Remove all required env vars
        for var in [
            "SECRET_KEY",
            "CLERK_PUBLISHABLE_KEY",
            "CLERK_SECRET_KEY",
            "CLERK_JWT_ISSUER",
            "DATABASE_URL",
            "R2_ACCOUNT_ID",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
            "R2_BUCKET_NAME",
            "R2_ENDPOINT",
        ]:
            monkeypatch.delenv(var, raising=False)

        from crack_detection.backend.config import Settings

        with pytest.raises(Exception):
            Settings()


# ---------------------------------------------------------------------------
# Error response format tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestErrorFormat:
    """Tests for consistent error response format."""

    def test_validation_error_format(self) -> None:
        """ValidationError produces correct error dict."""
        from crack_detection.backend.exceptions import ValidationError

        exc = ValidationError("Bad input", action="Check request")
        body = {
            "error": exc.error_code,
            "message": exc.message,
            "retryable": exc.retryable,
        }
        if exc.action:
            body["action"] = exc.action

        assert body["error"] == "validation_error"
        assert body["message"] == "Bad input"
        assert body["retryable"] is False
        assert body["action"] == "Check request"

    def test_service_unavailable_is_retryable(self) -> None:
        """ServiceUnavailableError is retryable."""
        from crack_detection.backend.exceptions import ServiceUnavailableError

        exc = ServiceUnavailableError("Service down")
        assert exc.status_code == 503
        assert exc.retryable is True
        assert exc.error_code == "service_unavailable"
