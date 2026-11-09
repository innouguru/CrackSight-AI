"""Tests for the CrackSight AI backend foundation.

These tests exercise configuration validation, exception handling,
schema validation, middleware logic, and API endpoints. They require
the backend dependencies (fastapi, pydantic-settings, psycopg2,
boto3, etc.) to be installed before they can run.
"""

from __future__ import annotations

import os
import json
import numpy as np
import contextlib
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Conditional imports -- tests skip gracefully when backend deps are absent.
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
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://test.r2.cloudflarestorage.com")

        settings = Settings()
        assert settings.app_name == "CrackSight AI"
        assert settings.app_env == "development"
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
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
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
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://test.r2.cloudflarestorage.com")

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def _base_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set all required env vars except DATABASE_URL."""
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test_123")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://test.r2.cloudflarestorage.com")

    def test_database_url_missing_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing DATABASE_URL fails closed with a validation error."""
        self._base_env(monkeypatch)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValueError, match="DATABASE_URL"):
            Settings()

    def test_database_url_without_sslmode_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DATABASE_URL without sslmode=require fails with a clear error."""
        self._base_env(monkeypatch)
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@localhost:5432/db"
        )
        with pytest.raises(ValueError, match="sslmode=require"):
            Settings()

    def test_database_url_with_sslmode_require_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DATABASE_URL with sslmode=require is accepted."""
        self._base_env(monkeypatch)
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://user:pass@localhost:5432/db?sslmode=require",
        )
        settings = Settings()
        assert "sslmode=require" in settings.database_url

    def test_r2_endpoint_without_https_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R2_ENDPOINT without https:// fails with a clear error."""
        self._base_env(monkeypatch)
        monkeypatch.setenv("R2_ENDPOINT", "http://test.r2.cloudflarestorage.com")
        with pytest.raises(ValueError, match="HTTPS URL"):
            Settings()

    def test_r2_endpoint_with_https_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R2_ENDPOINT with https:// is accepted."""
        self._base_env(monkeypatch)
        monkeypatch.setenv(
            "R2_ENDPOINT", "https://acc123.r2.cloudflarestorage.com"
        )
        settings = Settings()
        assert settings.r2_endpoint == "https://acc123.r2.cloudflarestorage.com"

    def test_r2_bucket_name_empty_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty R2_BUCKET_NAME fails with a clear error."""
        self._base_env(monkeypatch)
        monkeypatch.setenv("R2_BUCKET_NAME", "")
        with pytest.raises(ValueError, match="must not be empty"):
            Settings()

    def test_clerk_jwt_issuer_without_https_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLERK_JWT_ISSUER without https:// fails with a clear error."""
        self._base_env(monkeypatch)
        monkeypatch.setenv("CLERK_JWT_ISSUER", "http://test.clerk.accounts.com")
        with pytest.raises(ValueError, match="HTTPS URL"):
            Settings()

    def test_clerk_jwt_issuer_with_https_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLERK_JWT_ISSUER with https:// is accepted."""
        self._base_env(monkeypatch)
        monkeypatch.setenv(
            "CLERK_JWT_ISSUER", "https://test.clerk.accounts.com"
        )
        settings = Settings()
        assert settings.clerk_jwt_issuer == "https://test.clerk.accounts.com"


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestHealthEndpoints:
    """Tests for the /live and /ready health endpoints.

    These tests exercise the real middleware stack via TestClient. They do not
    require Neon, R2, Clerk, or any external service: /live performs no
    dependency checks, and /ready only inspects configured environment
    variables (it never opens a connection).
    """

    def _build_app(
        self, monkeypatch: pytest.MonkeyPatch, *, env: dict[str, str] | None = None
    ):
        """Build a fresh TestClient under isolated env with settings cache cleared."""
        from crack_detection.backend.config import get_settings
        from crack_detection.backend.main import create_app

        get_settings.cache_clear()
        if env:
            for key, value in env.items():
                monkeypatch.setenv(key, value)
        return TestClient(create_app())

    def test_live_returns_200_and_alive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /live returns HTTP 200 with status 'alive' and no auth required."""
        client = self._build_app(monkeypatch)
        resp = client.get("/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"
        assert data["service"] == "CrackSight AI"
        assert data["version"] == "0.1.0"

    def test_ready_returns_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /ready returns HTTP 200 (status may be 'ready' or 'not_ready'
        depending on configured env vars; both are valid responses)."""
        client = self._build_app(monkeypatch)
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        assert data["service"] == "CrackSight AI"

    def test_ready_configured_when_env_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When DATABASE_URL and R2 env vars are set (not CHANGE_ME), /ready
        reports those checks as 'configured'."""
        client = self._build_app(
            monkeypatch,
            env={
                "DATABASE_URL": "postgresql://user:pass@host:5432/db?sslmode=require",
                "R2_BUCKET_NAME": "my-bucket",
                "R2_ENDPOINT": "https://acc.r2.cloudflarestorage.com",
                "INFERENCE_SERVICE_URL": "http://localhost:8001",
            },
        )
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["checks"]["database"] == "configured"
        assert data["checks"]["storage"] == "configured"

    def test_ready_not_configured_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When DATABASE_URL/R2 are unset or CHANGE_ME, /ready reports
        'not_configured' rather than healthy."""
        client = self._build_app(
            monkeypatch,
            env={
                "DATABASE_URL": "postgresql://CHANGE_ME:CHANGE_ME@CHANGE_ME.neon.tech:5432/CHANGE_ME?sslmode=require",
                "R2_BUCKET_NAME": "CHANGE_ME",
                "R2_ENDPOINT": "https://CHANGE_ME.r2.cloudflarestorage.com",
            },
        )
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["checks"]["database"] == "not_configured"
        assert data["checks"]["storage"] == "not_configured"

    def test_health_endpoints_require_no_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unauthenticated requests to /live and /ready succeed (no Clerk JWT
        or guest session token required)."""
        client = self._build_app(monkeypatch)
        live_resp = client.get("/live")
        ready_resp = client.get("/ready")
        assert live_resp.status_code == 200
        assert ready_resp.status_code == 200

    def test_ready_includes_all_check_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET /ready always reports database, storage, and inference_service
        check keys regardless of their configured state."""
        client = self._build_app(monkeypatch)
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["checks"].keys()) == {
            "database",
            "storage",
            "inference_service",
        }


# ---------------------------------------------------------------------------
# Exception tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestExceptions:
    """Tests for custom exception classes."""

    def test_api_error_defaults(self) -> None:
        exc = APIError("something failed")
        assert exc.message == "something failed"
        assert exc.error_code == "api_error"
        assert exc.status_code == 500
        assert exc.retryable is False

    def test_validation_error_status(self) -> None:
        exc = ValidationError("bad input")
        assert exc.status_code == 400
        assert exc.error_code == "validation_error"
        assert exc.retryable is False

    def test_not_found_error_status(self) -> None:
        exc = NotFoundError("not found")
        assert exc.status_code == 404
        assert exc.error_code == "not_found"

    def test_forbidden_error_status(self) -> None:
        exc = ForbiddenError("forbidden")
        assert exc.status_code == 403
        assert exc.error_code == "forbidden"

    def test_unauthorized_error_status(self) -> None:
        exc = UnauthorizedError()
        assert exc.status_code == 401
        assert exc.error_code == "unauthorized"

    def test_service_unavailable_retryable(self) -> None:
        exc = ServiceUnavailableError("down")
        assert exc.status_code == 503
        assert exc.error_code == "service_unavailable"
        assert exc.retryable is True


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestSchemas:
    """Tests for Pydantic request/response schemas."""

    def test_health_response(self) -> None:
        h = HealthResponse()
        assert h.status == "ok"
        assert h.service == "CrackSight AI"
        assert h.version == "0.1.0"

    def test_inspection_create_valid(self) -> None:
        payload = InspectionCreate(
            title="Basement wall inspection",
            building_type="residential",
            building_location="123 Main St",
            notes="Check for hairline cracks",
        )
        assert payload.title == "Basement wall inspection"

    def test_inspection_create_empty_title_rejected(self) -> None:
        with pytest.raises(ValueError):
            InspectionCreate(title="")

    def test_photograph_create_valid(self) -> None:
        payload = PhotographCreate(
            structure_type="wall",
            original_image_key="inspections/abc123/originals/photo1.jpg",
            observation="Small crack near corner",
        )
        assert payload.structure_type == "wall"

    def test_photograph_create_invalid_structure_type(self) -> None:
        with pytest.raises(ValueError):
            PhotographCreate(
                structure_type="floor",
                original_image_key="key.jpg",
            )

    def test_token_verify_response(self) -> None:
        resp = TokenVerifyResponse(valid=True, user_id="user_123", email="test@example.com")
        assert resp.valid is True
        assert resp.user_id == "user_123"
        assert resp.email == "test@example.com"

    def test_error_detail(self) -> None:
        err = ErrorDetail(
            error="validation_error",
            message="Invalid input",
            retryable=False,
            action="Check your request",
        )
        assert err.error == "validation_error"
        assert err.message == "Invalid input"
        assert err.retryable is False
        assert err.action == "Check your request"


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
                "DATABASE_URL", "postgresql://user:pass@localhost:5432/db"
            )
            monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
            monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
            monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
            monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
            monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")

            storage = R2Storage()
            result = storage.upload_file("test/key.jpg", b"hello", "image/jpeg")
            assert result == "test/key.jpg"
            mock_client.put_object.assert_called_once()

            data = storage.download_file("test/key.jpg")
            assert data == b"data"

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
                "DATABASE_URL", "postgresql://user:pass@localhost:5432/db"
            )
            monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
            monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
            monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
            monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
            monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")

            storage = R2Storage()
            storage.delete_file("missing/key.jpg")


# ---------------------------------------------------------------------------
# Clerk JWT verification tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestClerkJWTVerification:
    """Tests for Clerk JWT verification using generated test keys."""

    @classmethod
    def setup_class(cls) -> None:
        """Generate an RSA key pair for JWT signing tests."""
        from cryptography.hazmat.primitives.asymmetric import rsa

        cls._private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        cls._public_key = cls._private_key.public_key()

    def _make_jwt(self, overrides: dict | None = None) -> str:
        """Create a signed JWT with optional claim overrides."""
        import time
        from jose import jwt as jose_jwt
        from cryptography.hazmat.primitives import serialization

        now = int(time.time())
        payload = {
            "sub": "user_123",
            "email": "test@example.com",
            "iss": "https://test.clerk.accounts.com",
            "iat": now,
            "exp": now + 3600,
        }
        if overrides:
            payload.update(overrides)
        private_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return jose_jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": "test-key-1"})

    def _make_jwks(self) -> list:
        """Create a JWKS keys list from the test public key."""
        import base64
        from cryptography.hazmat.primitives.asymmetric import rsa

        public_numbers = self._public_key.public_numbers()
        n = public_numbers.n
        e = public_numbers.e

        def int_to_b64uint(i: int) -> str:
            byte_length = (i.bit_length() + 7) // 8
            bytes_val = i.to_bytes(byte_length, "big")
            return base64.urlsafe_b64encode(bytes_val).rstrip(b"=").decode("ascii")

        return [
            {
                "kty": "RSA",
                "kid": "test-key-1",
                "use": "sig",
                "alg": "RS256",
                "n": int_to_b64uint(n),
                "e": int_to_b64uint(e),
            }
        ]

    def test_valid_jwt_verified(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid JWT signed by the test key is verified."""
        from crack_detection.backend.config import Settings
        from crack_detection.backend.middleware import _verify_clerk_jwt

        monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test_123")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv(
            "CLERK_JWKS_URL", "https://test.clerk.accounts.com/.well-known/jwks.json"
        )
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@localhost:5432/db"
        )
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")

        settings = Settings()
        token = self._make_jwt()
        jwks_keys = self._make_jwks()

        async def test() -> None:
            with patch(
                "crack_detection.backend.middleware._fetch_jwks",
                return_value=jwks_keys,
            ):
                result = await _verify_clerk_jwt(token, settings)
            assert result is not None
            user_id, email = result
            assert user_id == "user_123"
            assert email == "test@example.com"

        import asyncio

        asyncio.get_event_loop().run_until_complete(test())

    def test_invalid_signature_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A JWT signed with a different key is rejected."""
        from cryptography.hazmat.primitives.asymmetric import rsa
        from jose import jwt as jose_jwt
        from cryptography.hazmat.primitives import serialization

        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        import time

        now = int(time.time())
        payload = {
            "sub": "user_123",
            "iss": "https://test.clerk.accounts.com",
            "iat": now,
            "exp": now + 3600,
        }
        other_pem = other_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        token = jose_jwt.encode(payload, other_pem, algorithm="RS256")

        from crack_detection.backend.config import Settings
        from crack_detection.backend.middleware import _verify_clerk_jwt

        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv(
            "CLERK_JWKS_URL", "https://test.clerk.accounts.com/.well-known/jwks.json"
        )
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@localhost:5432/db"
        )
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")

        settings = Settings()
        jwks_keys = self._make_jwks()

        async def test() -> None:
            with patch(
                "crack_detection.backend.middleware._fetch_jwks",
                return_value=jwks_keys,
            ):
                result = await _verify_clerk_jwt(token, settings)
            assert result is None

        import asyncio

        asyncio.get_event_loop().run_until_complete(test())

    def test_expired_jwt_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An expired JWT is rejected."""
        import time
        from jose import jwt as jose_jwt

        now = int(time.time())
        payload = {
            "sub": "user_123",
            "iss": "https://test.clerk.accounts.com",
            "iat": now - 7200,
            "exp": now - 3600,
        }
        token = jose_jwt.encode(payload, self._private_key, algorithm="RS256")

        from crack_detection.backend.config import Settings
        from crack_detection.backend.middleware import _verify_clerk_jwt

        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv(
            "CLERK_JWKS_URL", "https://test.clerk.accounts.com/.well-known/jwks.json"
        )
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@localhost:5432/db"
        )
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")

        settings = Settings()
        jwks_keys = self._make_jwks()

        async def test() -> None:
            with patch(
                "crack_detection.backend.middleware._fetch_jwks",
                return_value=jwks_keys,
            ):
                result = await _verify_clerk_jwt(token, settings)
            assert result is None

        import asyncio

        asyncio.get_event_loop().run_until_complete(test())

    def test_invalid_issuer_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A JWT with a different issuer is rejected."""
        import time
        from jose import jwt as jose_jwt

        now = int(time.time())
        payload = {
            "sub": "user_123",
            "iss": "https://other.clerk.accounts.com",
            "iat": now,
            "exp": now + 3600,
        }
        token = jose_jwt.encode(payload, self._private_key, algorithm="RS256")

        from crack_detection.backend.config import Settings
        from crack_detection.backend.middleware import _verify_clerk_jwt

        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv(
            "CLERK_JWKS_URL", "https://test.clerk.accounts.com/.well-known/jwks.json"
        )
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@localhost:5432/db"
        )
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")

        settings = Settings()
        jwks_keys = self._make_jwks()

        async def test() -> None:
            with patch(
                "crack_detection.backend.middleware._fetch_jwks",
                return_value=jwks_keys,
            ):
                result = await _verify_clerk_jwt(token, settings)
            assert result is None

        import asyncio

        asyncio.get_event_loop().run_until_complete(test())

    def test_missing_kid_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A JWT without a kid header is rejected."""
        import base64
        import json
        import time
        from jose import jwt as jose_jwt
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        now = int(time.time())
        payload = {
            "sub": "user_123",
            "iss": "https://test.clerk.accounts.com",
            "iat": now,
            "exp": now + 3600,
        }
        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).rstrip(b"=").decode("ascii")
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).rstrip(b"=").decode("ascii")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature = self._private_key.sign(
            signing_input,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
        token = f"{header_b64}.{payload_b64}.{sig_b64}"

        from crack_detection.backend.config import Settings
        from crack_detection.backend.middleware import _verify_clerk_jwt

        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv(
            "CLERK_JWKS_URL", "https://test.clerk.accounts.com/.well-known/jwks.json"
        )
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@localhost:5432/db"
        )
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")

        settings = Settings()
        jwks_keys = self._make_jwks()

        async def test() -> None:
            with patch(
                "crack_detection.backend.middleware._fetch_jwks",
                return_value=jwks_keys,
            ):
                result = await _verify_clerk_jwt(token, settings)
            assert result is None

        import asyncio

        asyncio.get_event_loop().run_until_complete(test())


def _use_fresh_settings(
    monkeypatch: pytest.MonkeyPatch, updates: dict | None = None
) -> "contextlib.AbstractContextManager":
    """Point the cached ``get_settings`` at freshly patched env values for the
    current test, then invalidate the cache afterwards so later tests
    re-read their own environment. Yields no value."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        from crack_detection.backend.config import get_settings

        for name, value in (updates or {}).items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        try:
            yield
        finally:
            get_settings.cache_clear()

    return _ctx()


# ---------------------------------------------------------------------------
# Authentication endpoint tests (TestClient)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestAuthEndpoints:
    """Behavioural tests for the real /auth endpoints.

    JWKS retrieval and the database layer are mocked (external boundaries
    only); the real endpoint logic, middleware, and JWT verification run.
    /auth/verify performs JWT verification only — it does NOT synchronise
    local users (that is exclusively get_current_user's role, tested
    separately). /auth/callback is a route-completeness placeholder that
    delegates sign-in to Clerk's hosted pages.
    """

    _ISSUER = "https://test.clerk.accounts.com"
    _KID = "test-key-1"

    @classmethod
    def setup_class(cls) -> None:
        os.environ["SECRET_KEY"] = "test-secret-key-12345"
        os.environ["CLERK_PUBLISHABLE_KEY"] = "pk_test_123"
        os.environ["CLERK_SECRET_KEY"] = "sk_test_123"
        os.environ["CLERK_JWT_ISSUER"] = cls._ISSUER
        os.environ["CLERK_JWKS_URL"] = (
            "https://test.clerk.accounts.com/.well-known/jwks.json"
        )
        os.environ["DATABASE_URL"] = (
            "postgresql://user:pass@localhost:5432/db?sslmode=require"
        )
        os.environ["R2_ACCOUNT_ID"] = "test-account"
        os.environ["R2_ACCESS_KEY_ID"] = "test-key"
        os.environ["R2_SECRET_ACCESS_KEY"] = "test-secret"
        os.environ["R2_BUCKET_NAME"] = "test-bucket"
        os.environ["R2_ENDPOINT"] = "https://test.r2.cloudflarestorage.com"

        from cryptography.hazmat.primitives.asymmetric import rsa

        cls._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        from crack_detection.backend.main import app

        cls.client = TestClient(app)

    @classmethod
    def teardown_class(cls) -> None:
        from crack_detection.backend.middleware import _JWKS_CACHE

        _JWKS_CACHE.clear()
        from crack_detection.backend.config import get_settings

        get_settings.cache_clear()

    @classmethod
    def _make_jwt(cls, overrides: dict | None = None, key=None, kid: str = "test-key-1") -> str:
        """Sign a JWT with the provided (default: class) RSA key."""
        import time
        from jose import jwt as jose_jwt

        now = int(time.time())
        payload = {
            "sub": "user_123",
            "email": "test@example.com",
            "iss": cls._ISSUER,
            "iat": now,
            "exp": now + 3600,
        }
        if overrides:
            payload.update(overrides)
        return jose_jwt.encode(payload, key or cls._private_key, algorithm="RS256", headers={"kid": kid})

    @classmethod
    def _jwks_for(cls, key, kid: str) -> list:
        """Build a JWKS keys list from the given public key."""
        import base64

        public_numbers = key.public_key().public_numbers()

        def int_to_b64uint(value: int) -> str:
            byte_length = (value.bit_length() + 7) // 8
            bytes_val = value.to_bytes(byte_length, "big")
            return base64.urlsafe_b64encode(bytes_val).rstrip(b"=").decode("ascii")

        return [
            {
                "kty": "RSA",
                "kid": kid,
                "use": "sig",
                "alg": "RS256",
                "n": int_to_b64uint(public_numbers.n),
                "e": int_to_b64uint(public_numbers.e),
            }
        ]

    @classmethod
    def _seed_jwks_cache(cls, keys: list) -> None:
        """Seed the middleware JWKS cache directly (cache is a module global)."""
        from crack_detection.backend import middleware

        middleware._JWKS_CACHE[cls._ISSUER] = (
            __import__("time").time() + 3600,
            keys,
        )

    @staticmethod
    def _db_scope():
        """Context manager proving /auth endpoints perform no database work:
        enters mocks for the DB connection factory and the user
        synchronisation dependency, yielding both mocks for not-called
        assertions."""
        import contextlib
        from contextlib import ExitStack
        from unittest.mock import patch

        @contextlib.contextmanager
        def _scope():
            with ExitStack() as stack:
                db_conn = stack.enter_context(
                    patch("crack_detection.backend.database.get_db_connection")
                )
                ensure_user = stack.enter_context(
                    patch("crack_detection.backend.dependencies.ensure_registered_user")
                )
                yield db_conn, ensure_user

        return _scope()

    # --------------------------------------------------------------- /auth/verify

    def test_verify_valid_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A correctly signed, current token is verified and its identity
        returned; no fetch beyond JWKS, no database access."""
        from unittest.mock import patch

        from crack_detection.backend import middleware
        from crack_detection.backend.config import get_settings

        with _use_fresh_settings(monkeypatch), self._db_scope() as (
            db_conn,
            ensure_user,
        ):
            middleware._JWKS_CACHE.clear()
            with patch.object(
                middleware, "_fetch_jwks", return_value=self._jwks_for(self._private_key, self._KID)
            ) as mock_fetch:
                resp = self.client.post(
                    "/auth/verify",
                    headers={"Authorization": f"Bearer {self._make_jwt()}"},
                )

            assert resp.status_code == 200
            assert set(resp.json().keys()) == {"valid", "user_id", "email"}
            data = resp.json()
            assert data["valid"] is True
            assert data["user_id"] == "user_123"
            assert data["email"] == "test@example.com"
            mock_fetch.assert_called_once_with(get_settings().clerk_jwks_url)
            db_conn.assert_not_called()
            ensure_user.assert_not_called()

    def test_verify_rejects_missing_and_malformed_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Absence of or malformed Bearer credentials fail closed with
        valid=false and no verification, no JWKS fetch, no DB access."""
        from unittest.mock import patch

        from crack_detection.backend import middleware

        cases = [
            {},
            {"Authorization": "Basic dXNlcjpwYXNz"},
            {"Authorization": "Bearer"},
            {"Authorization": "Bearer "},
        ]
        with _use_fresh_settings(monkeypatch), self._db_scope() as (
            db_conn,
            ensure_user,
        ):
            middleware._JWKS_CACHE.clear()
            with patch.object(middleware, "_fetch_jwks") as mock_fetch:
                for headers in cases:
                    resp = self.client.post("/auth/verify", headers=headers)
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["valid"] is False
                    assert data["user_id"] is None
                    assert data["email"] is None
                assert mock_fetch.call_count == 0
            db_conn.assert_not_called()
            ensure_user.assert_not_called()

    def test_verify_rejects_invalid_signature(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A token signed by a foreign key with a matching kid fails
        signature verification: valid=false, JWKS cache hit (no fetch)."""
        import time as time_module
        from cryptography.hazmat.primitives.asymmetric import rsa
        from unittest.mock import patch

        from crack_detection.backend import middleware

        foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = self._make_jwt(
            overrides={"exp": int(time_module.time()) + 3600},
            key=foreign_key,
            kid=self._KID,
        )
        with _use_fresh_settings(monkeypatch), self._db_scope() as (
            db_conn,
            ensure_user,
        ):
            middleware._JWKS_CACHE.clear()
            # Seed the cache through the middleware's own setter.
            from crack_detection.backend.middleware import _jwks_cache_set

            _jwks_cache_set(self._ISSUER, self._jwks_for(self._private_key, self._KID))
            with patch.object(middleware, "_fetch_jwks") as mock_fetch:
                resp = self.client.post(
                    "/auth/verify", headers={"Authorization": f"Bearer {token}"}
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is False
            assert data["user_id"] is None
            assert data["email"] is None
            assert mock_fetch.call_count == 0
            db_conn.assert_not_called()
            ensure_user.assert_not_called()

    def test_verify_rejects_expired_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An expired token is rejected: valid=false, no user identity."""
        import time as time_module
        from unittest.mock import patch

        from crack_detection.backend import middleware

        token = self._make_jwt(
            overrides={
                "iat": int(time_module.time()) - 7200,
                "exp": int(time_module.time()) - 3600,
            }
        )
        with _use_fresh_settings(monkeypatch), self._db_scope() as (
            db_conn,
            ensure_user,
        ):
            middleware._JWKS_CACHE.clear()
            self._seed_jwks_cache(self._jwks_for(self._private_key, self._KID))
            resp = self.client.post(
                "/auth/verify", headers={"Authorization": f"Bearer {token}"}
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is False
            assert data["user_id"] is None
            assert data["email"] is None
            db_conn.assert_not_called()
            ensure_user.assert_not_called()

    def test_verify_rejects_issuer_mismatch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A token from a different issuer is rejected (iss verified)."""
        from unittest.mock import patch

        from crack_detection.backend import middleware

        token = self._make_jwt(overrides={"iss": "https://other.clerk.accounts.com"})
        with _use_fresh_settings(monkeypatch), self._db_scope() as (
            db_conn,
            ensure_user,
        ):
            middleware._JWKS_CACHE.clear()
            self._seed_jwks_cache(self._jwks_for(self._private_key, self._KID))
            resp = self.client.post(
                "/auth/verify", headers={"Authorization": f"Bearer {token}"}
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is False
            assert data["user_id"] is None
            assert data["email"] is None
            db_conn.assert_not_called()
            ensure_user.assert_not_called()

    def test_verify_rejects_unknown_kid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A token whose kid has no JWKS counterpart is rejected."""
        from unittest.mock import patch

        from crack_detection.backend import middleware

        token = self._make_jwt(kid="ghost-kid")
        with _use_fresh_settings(monkeypatch), self._db_scope() as (
            db_conn,
            ensure_user,
        ):
            middleware._JWKS_CACHE.clear()
            self._seed_jwks_cache(self._jwks_for(self._private_key, self._KID))
            resp = self.client.post(
                "/auth/verify", headers={"Authorization": f"Bearer {token}"}
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is False
            assert data["user_id"] is None
            assert data["email"] is None
            db_conn.assert_not_called()
            ensure_user.assert_not_called()

    def test_verify_jwks_retrieval_failure_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When JWKS retrieval fails, verification fails closed with a
        structured valid=false identity response."""
        import httpx
        from unittest.mock import patch

        from crack_detection.backend import middleware

        with _use_fresh_settings(monkeypatch), self._db_scope() as (
            db_conn,
            ensure_user,
        ):
            middleware._JWKS_CACHE.clear()
            with patch.object(
                middleware,
                "_fetch_jwks",
                side_effect=httpx.ReadError("jwks unavailable"),
            ) as mock_fetch:
                resp = self.client.post(
                    "/auth/verify", headers={"Authorization": f"Bearer {self._make_jwt()}"}
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is False
            assert data["user_id"] is None
            assert data["email"] is None
            # Both the middleware and the endpoint verify the Bearer token
            # independently; each fails closed when JWKS retrieval fails.
            assert mock_fetch.call_count == 2
            db_conn.assert_not_called()
            ensure_user.assert_not_called()

    def test_verify_unconfigured_clerk_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without issuer/JWKS configuration no verification, fetch, or DB
        work happens and the identity is reported invalid."""
        from unittest.mock import patch

        from crack_detection.backend import middleware

        updates = {"CLERK_JWT_ISSUER": "", "CLERK_JWKS_URL": ""}
        with _use_fresh_settings(monkeypatch, updates), self._db_scope() as (
            db_conn,
            ensure_user,
        ):
            middleware._JWKS_CACHE.clear()
            with patch.object(middleware, "_fetch_jwks") as mock_fetch:
                resp = self.client.post(
                    "/auth/verify", headers={"Authorization": f"Bearer {self._make_jwt()}"}
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is False
            assert data["user_id"] is None
            assert data["email"] is None
            assert mock_fetch.call_count == 0
            db_conn.assert_not_called()
            ensure_user.assert_not_called()

    # --------------------------------------------------------------- /auth/sign-in-url

    def test_sign_in_url_derived_from_issuer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The sign-in URL is derived from the configured Clerk issuer."""
        resp = self.client.get("/auth/sign-in-url")

        assert resp.status_code == 200
        assert set(resp.json().keys()) == {"sign_in_url"}
        assert resp.json()["sign_in_url"] == f"{self._ISSUER}/sign-in"

    def test_sign_in_url_fallback_without_usable_issuer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Placeholder (CHANGE_ME) or empty issuer configurations fall back
        to the generic sign-in URL."""
        from unittest.mock import patch

        with _use_fresh_settings(
            monkeypatch, {"CLERK_JWT_ISSUER": "https://CHANGE_ME.clerk.accounts.com"}
        ):
            resp = self.client.get("/auth/sign-in-url")
            assert resp.status_code == 200
            assert resp.json()["sign_in_url"] == "https://clerk.accounts.com/sign-in"

        with _use_fresh_settings(monkeypatch, {"CLERK_JWT_ISSUER": ""}):
            resp = self.client.get("/auth/sign-in-url")
            assert resp.status_code == 200
            assert resp.json()["sign_in_url"] == "https://clerk.accounts.com/sign-in"

    # --------------------------------------------------------------- /auth/callback

    def test_callback_is_documented_placeholder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The callback is a route-completeness placeholder: it performs no
        OAuth/token processing and leaves all sign-in handling to Clerk."""
        with self._db_scope() as (db_conn, ensure_user):
            resp = self.client.get("/auth/callback")

        assert resp.status_code == 200
        assert set(resp.json().keys()) == {"message", "note"}
        assert resp.json()["note"] == (
            "Clerk handles sign-in, account creation, password handling, "
            "and Google OAuth via its hosted pages and frontend SDK."
        )
        assert "Location" not in resp.headers
        db_conn.assert_not_called()
        ensure_user.assert_not_called()

    def test_callback_ignores_query_parameters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Callback query parameters (code/state) are not processed; the
        response is identical to the bare placeholder."""
        resp = self.client.get(
            "/auth/callback", params={"code": "abc123", "state": "xyz"}
        )

        assert resp.status_code == 200
        assert resp.json() == self.client.get("/auth/callback").json()
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestGuestSession:
    """Genuine behavioural tests for the guest-session database helpers.

    Only the database boundary is mocked (``get_db_connection`` or
    ``psycopg2.connect``); the real guest-session implementation — token
    generation, validation, expired-session deactivation, and atomic
    allowance enforcement — is the code under test.
    """

    def test_create_guest_session_inserts_and_returns_row(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A new session is inserted with a generated token and 24h expiry;
        the persisted row is returned and the transaction is committed."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        created_at = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)
        row = {
            "id": "11111111-2222-3333-4444-555555555555",
            "session_token": "token-persisted-by-database",
            "created_at": created_at,
            "expires_at": created_at + timedelta(hours=24),
            "analyses_count": 0,
            "is_active": True,
        }
        conn = _SeqConn(fetchone_results=[row])
        before = datetime.now(timezone.utc)

        with patch.object(database, "get_db_connection", return_value=conn):
            session = database.create_guest_session(expiration_hours=24)

        assert session == row
        sql, params = conn.cursor_obj.executed[0]
        assert "INSERT INTO guest_sessions" in sql
        assert "session_token, expires_at, analyses_count, is_active" in sql
        assert "VALUES (%s, %s, 0, TRUE)" in sql
        assert "RETURNING id, session_token, created_at, expires_at" in sql
        assert "analyses_count, is_active" in sql
        token_param, expires_param = params
        # The token is generated by the real secrets module: url-safe, 43 chars.
        assert isinstance(token_param, str) and len(token_param) == 43
        delta = expires_param - before
        assert abs(delta.total_seconds() - 24 * 3600) < 15
        assert conn.committed is True

    def test_validate_guest_session_returns_active_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An active, non-expired session is returned with its stored data,
        and the read-only lookup commits nothing."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        row = {
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "session_token": "tok-valid",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=2),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "analyses_count": 2,
            "is_active": True,
        }
        conn = _SeqConn(fetchone_results=[row])

        with patch.object(database, "get_db_connection", return_value=conn):
            session = database.validate_guest_session("tok-valid")

        assert session == row
        sql, params = conn.cursor_obj.executed[0]
        assert "SELECT id, session_token, created_at, expires_at" in sql
        assert "WHERE session_token = %s AND is_active = TRUE" in sql
        assert params == ("tok-valid",)
        assert conn.committed is False

    def test_validate_guest_session_expired_rejected_and_deactivated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An expired session is rejected and deactivated as a side effect."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        row = {
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "session_token": "tok-expired",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=25),
            "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "analyses_count": 1,
            "is_active": True,
        }
        conn = _SeqConn(fetchone_results=[row])

        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.validate_guest_session("tok-expired")

        assert result is None
        assert len(conn.cursor_obj.executed) == 2
        deactivate_sql, deactivate_params = conn.cursor_obj.executed[1]
        assert "UPDATE guest_sessions SET is_active = FALSE WHERE id = %s" in deactivate_sql
        assert deactivate_params == ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",)
        assert conn.committed is True

    def test_validate_guest_session_treats_naive_expiry_as_utc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A naive (tz-less) expiry timestamp is interpreted as UTC."""
        from datetime import datetime, timedelta
        from unittest.mock import patch

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        row = {
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "session_token": "tok-naive",
            "created_at": datetime.utcnow() - timedelta(hours=2),
            "expires_at": datetime.utcnow() + timedelta(hours=1),
            "analyses_count": 1,
            "is_active": True,
        }
        conn = _SeqConn(fetchone_results=[row])

        with patch.object(database, "get_db_connection", return_value=conn):
            session = database.validate_guest_session("tok-naive")

        assert session == row
        assert conn.committed is False

    def test_validate_guest_session_unknown_token_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unknown token returns None without any write."""
        from unittest.mock import patch

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        conn = _SeqConn(fetchone_results=[])

        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.validate_guest_session("no-such-token")

        assert result is None
        assert len(conn.cursor_obj.executed) == 1
        assert conn.committed is False

    def test_increment_analysis_count_atomic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A within-limit increment returns the new count from the atomic
        conditional UPDATE (active + under limit + unexpired guard)."""
        from unittest.mock import patch

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        conn = _SeqConn(fetchone_results=[(2,)])

        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.increment_guest_analysis_count(
                "session-id", max_analyses=3
            )

        assert result == 2
        sql, params = conn.cursor_obj.executed[0]
        assert "UPDATE guest_sessions" in sql
        assert "SET analyses_count = analyses_count + 1" in sql
        assert "WHERE id = %s" in sql
        assert "AND is_active = TRUE" in sql
        assert "AND analyses_count < %s" in sql
        assert "AND expires_at > NOW()" in sql
        assert "RETURNING analyses_count" in sql
        assert params == ("session-id", 3)
        assert conn.committed is True

    def test_increment_analysis_count_at_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A session at its limit (no UPDATE row) gets no increment."""
        from unittest.mock import patch

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        conn = _SeqConn(fetchone_results=[])

        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.increment_guest_analysis_count(
                "session-id", max_analyses=3
            )

        assert result is None
        assert conn.committed is True

    def test_create_guest_session_expiration_falls_back_to_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A falsy expiration hours value falls back to the configured
        default (24 hours)."""
        from datetime import datetime, timezone
        from unittest.mock import patch

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        row = {
            "id": "11111111-2222-3333-4444-555555555555",
            "session_token": "token-persisted-by-database",
            "created_at": "2026-11-08T12:00:00+00:00",
            "expires_at": "2026-11-09T12:00:00+00:00",
            "analyses_count": 0,
            "is_active": True,
        }
        conn = _SeqConn(fetchone_results=[row])
        before = datetime.now(timezone.utc)

        with patch.object(database, "get_db_connection", return_value=conn):
            session = database.create_guest_session(expiration_hours=0)

        assert session == row
        _, expires_param = conn.cursor_obj.executed[0][1]
        delta = expires_param - before
        assert abs(delta.total_seconds() - 24 * 3600) < 15

    def test_guest_session_db_connect_failure_wrapped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing psycopg2 connection surfaces as DatabaseError."""
        from unittest.mock import patch

        from psycopg2 import OperationalError

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        with patch.object(
            database.psycopg2,
            "connect",
            side_effect=OperationalError("connection refused"),
        ):
            with pytest.raises(database.DatabaseError, match="connection refused"):
                database.create_guest_session()

    def test_guest_session_statement_failure_rolls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing guest-session statement rolls back via the real
        connection context manager, closes the connection, and wraps the
        error in DatabaseError; nothing is committed."""

        class _FailingCursor:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params=None):
                raise OperationalError("constraint violated")

        class _FailingConn:
            def __init__(self) -> None:
                self.rolled_back = False
                self.closed = False
                self.committed = False

            def cursor(self, *args, **kwargs):
                return _FailingCursor()

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

            def close(self):
                self.closed = True

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        from unittest.mock import patch

        from psycopg2 import OperationalError

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        conn = _FailingConn()
        with patch.object(database.psycopg2, "connect", return_value=conn):
            with pytest.raises(database.DatabaseError, match="constraint violated"):
                database.increment_guest_analysis_count("session-id", max_analyses=3)

        assert conn.rolled_back is True
        assert conn.closed is True
        assert conn.committed is False

    def test_db_connection_context_closes_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With the real connection scaffold running (psycopg2.connect
        patched), a successful guest-session workload is committed and the
        connection is closed by the scaffold afterwards."""
        from unittest.mock import patch

        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        row = {
            "id": "11111111-2222-3333-4444-555555555555",
            "session_token": "token-persisted-by-database",
            "created_at": "2026-11-08T12:00:00+00:00",
            "expires_at": "2026-11-09T12:00:00+00:00",
            "analyses_count": 0,
            "is_active": True,
        }
        conn = _SeqConn(fetchone_results=[row])
        with patch.object(database.psycopg2, "connect", return_value=conn):
            session = database.create_guest_session(expiration_hours=24)

        assert session == row
        assert conn.committed is True
        assert conn.closed is True


# ---------------------------------------------------------------------------
# Guest session router tests (TestClient)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestGuestSessionRouter:
    """Tests for guest session API endpoints."""

    @classmethod
    def setup_class(cls) -> None:
        os.environ["SECRET_KEY"] = "test-secret-key-12345"
        os.environ["CLERK_PUBLISHABLE_KEY"] = "pk_test_123"
        os.environ["CLERK_SECRET_KEY"] = "sk_test_123"
        os.environ["CLERK_JWT_ISSUER"] = "https://test.clerk.accounts.com"
        os.environ["CLERK_JWKS_URL"] = (
            "https://test.clerk.accounts.com/.well-known/jwks.json"
        )
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

    def test_create_guest_session(self) -> None:
        """Creating a guest session returns a token."""
        from unittest.mock import patch
        from datetime import datetime, timezone
        import uuid

        with patch(
            "crack_detection.backend.routers.guest.create_guest_session"
        ) as mock_create:
            mock_create.return_value = {
                "id": str(uuid.uuid4()),
                "session_token": "guest-token-abc",
                "created_at": "2026-01-01T00:00:00+00:00",
                "expires_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
                "analyses_count": 0,
                "is_active": True,
            }
            resp = self.client.post("/guest/session")
            assert resp.status_code == 201
            data = resp.json()
            assert data["session_token"] == "guest-token-abc"
            assert data["analyses_count"] == 0
            assert data["max_analyses"] == 3

    def test_validate_endpoint_reports_active_session(self) -> None:
        """A valid token returns the session state and remaining allowance."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        with patch(
            "crack_detection.backend.routers.guest.validate_guest_session"
        ) as mock_validate:
            mock_validate.return_value = {
                "id": "22222222-3333-4444-5555-666666666666",
                "session_token": "tok",
                "created_at": "2026-11-08T10:00:00+00:00",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                "analyses_count": 2,
                "is_active": True,
            }
            resp = self.client.get(
                "/guest/session/validate",
                headers={"X-Guest-Session-Token": "tok"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["session_id"] == "22222222-3333-4444-5555-666666666666"
        assert data["analyses_count"] == 2
        assert data["max_analyses"] == 3
        assert data["analyses_remaining"] == 1
        assert resp.json() is not None
        mock_validate.assert_called_once_with("tok")

    def test_validate_endpoint_missing_and_invalid_tokens(self) -> None:
        """A missing header or an unknown/expired token reports valid=False;
        a missing header never reaches the database layer."""
        from unittest.mock import patch

        with patch(
            "crack_detection.backend.routers.guest.validate_guest_session"
        ) as mock_validate:
            resp = self.client.get("/guest/session/validate")

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["session_id"] is None
        assert data["analyses_remaining"] == 0
        mock_validate.assert_not_called()

        with patch(
            "crack_detection.backend.routers.guest.validate_guest_session",
            return_value=None,
        ) as mock_validate:
            resp = self.client.get(
                "/guest/session/validate",
                headers={"X-Guest-Session-Token": "bad-or-expired"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        mock_validate.assert_called_once_with("bad-or-expired")

    def test_consume_endpoint_consumes_analysis_within_allowance(self) -> None:
        """A valid session can consume an analysis and gets a remaining count."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        with patch(
            "crack_detection.backend.routers.guest.validate_guest_session"
        ) as mock_validate, patch(
            "crack_detection.backend.routers.guest.increment_guest_analysis_count"
        ) as mock_increment:
            mock_validate.return_value = {
                "id": "33333333-4444-5555-6666-777777777777",
                "session_token": "tok",
                "created_at": "2026-11-08T10:00:00+00:00",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                "analyses_count": 1,
                "is_active": True,
            }
            mock_increment.return_value = 2

            resp = self.client.post(
                "/guest/session/consume-analysis",
                headers={"X-Guest-Session-Token": "tok"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["consumed"] is True
        assert data["analyses_count"] == 2
        assert data["max_analyses"] == 3
        assert data["analyses_remaining"] == 1
        mock_increment.assert_called_once_with(
            "33333333-4444-5555-6666-777777777777", max_analyses=3
        )

    def test_consume_endpoint_reports_limit_reached(self) -> None:
        """When the atomic increment returns None the endpoint reports
        consumed=False with zero remaining allowance."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        with patch(
            "crack_detection.backend.routers.guest.validate_guest_session"
        ) as mock_validate, patch(
            "crack_detection.backend.routers.guest.increment_guest_analysis_count"
        ) as mock_increment:
            mock_validate.return_value = {
                "id": "33333333-4444-5555-6666-777777777777",
                "session_token": "tok",
                "created_at": "2026-11-08T10:00:00+00:00",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                "analyses_count": 3,
                "is_active": True,
            }
            mock_increment.return_value = None

            resp = self.client.post(
                "/guest/session/consume-analysis",
                headers={"X-Guest-Session-Token": "tok"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["consumed"] is False
        assert data["analyses_count"] == 3
        assert data["analyses_remaining"] == 0

    def test_consume_endpoint_requires_session_token(self) -> None:
        """A missing guest session token is rejected with 401 before any
        database access."""
        from unittest.mock import patch

        with patch(
            "crack_detection.backend.routers.guest.validate_guest_session"
        ) as mock_validate:
            resp = self.client.post("/guest/session/consume-analysis")

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Guest session token required"
        mock_validate.assert_not_called()


# ---------------------------------------------------------------------------
# Registered-user identity synchronisation
# ---------------------------------------------------------------------------

class _FakeCursor:
    """In-memory cursor capturing the executed SQL and parameters.

    ``fetchone_result`` controls what ``fetchone()`` returns, allowing
    simulation of a successful read (for example, confirming an existing
    user record) versus an empty result.
    """

    def __init__(self, fetchone_result: Any = None) -> None:
        self.executed: tuple | None = None
        self._fetchone_result = fetchone_result

    def execute(self, sql: str, params=None) -> None:
        self.executed = (sql, params)

    def fetchone(self):
        return self._fetchone_result

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


class _FakeConn:
    """In-memory connection supporting the context-manager protocol."""

    def __init__(self, fetchone_result: Any = None) -> None:
        self.cursor_obj = _FakeCursor(fetchone_result)
        self.committed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


class _StdEnv:
    """Standard dummy environment required by ``get_settings``."""

    @staticmethod
    def apply(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test")
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")
        monkeypatch.setenv("CLERK_JWT_ISSUER", "https://test.clerk.accounts.com")
        monkeypatch.setenv(
            "CLERK_JWKS_URL", "https://test.clerk.accounts.com/.well-known/jwks.json"
        )
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@localhost:5432/db?sslmode=require"
        )
        monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET_NAME", "bucket")
        monkeypatch.setenv("R2_ENDPOINT", "https://endpoint")


def _load_inspections_router():
    """Load the real inspections router module directly from its file.

    Bypasses the ``routers`` package ``__init__``, which imports the guest
    router (multipart upload routes) and therefore requires the optional
    ``python-multipart`` dependency reported missing in this environment.
    The router code under test is real and unmodified.
    """
    import importlib.util
    from pathlib import Path

    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "crack_detection"
        / "backend"
        / "routers"
        / "inspections.py"
    )
    spec = importlib.util.spec_from_file_location(
        "inspections_router_under_test", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestApplicationFactory:
    """Tests for create_app() and the module-level Uvicorn entry point."""

    _ENV = {
        "SECRET_KEY": "test-secret-key-12345",
        "CLERK_PUBLISHABLE_KEY": "pk_test_123",
        "CLERK_SECRET_KEY": "sk_test_123",
        "CLERK_JWT_ISSUER": "https://test.clerk.accounts.com",
        "CLERK_JWKS_URL": "https://test.clerk.accounts.com/.well-known/jwks.json",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db?sslmode=require",
        "R2_ACCOUNT_ID": "acc",
        "R2_ACCESS_KEY_ID": "key",
        "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET_NAME": "bucket",
        "R2_ENDPOINT": "https://test.r2.cloudflarestorage.com",
    }

    def _set_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self._ENV.items():
            monkeypatch.setenv(key, value)

    def test_create_app_returns_fastapi_with_expected_wiring(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_app() builds a valid app with startup handler and routes."""
        self._set_env(monkeypatch)

        from fastapi import FastAPI

        from crack_detection.backend import main
        from crack_detection.backend.middleware import ClerkAuthMiddleware

        application = main.create_app()

        assert isinstance(application, FastAPI)
        assert application.title == "CrackSight AI"
        assert [f.__name__ for f in application.router.on_startup] == [
            "_startup_event"
        ]
        assert any(
            getattr(m, "cls", None) is ClerkAuthMiddleware
            for m in application.user_middleware
        )
        route_paths = {getattr(r, "path", None) for r in application.routes}
        assert "/" in route_paths
        assert "/guest/session" in route_paths
        assert "/reports/generate/{inspection_id}" in route_paths

    def test_module_level_app_importable_and_wired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``crack_detection.backend.main.app`` imports and is fully built."""
        self._set_env(monkeypatch)

        import crack_detection.backend.main as main_module
        from fastapi import FastAPI

        assert isinstance(main_module.app, FastAPI)
        assert main_module.app.title == "CrackSight AI"
        assert [f.__name__ for f in main_module.app.router.on_startup] == [
            "_startup_event"
        ]
        fresh_app = main_module.create_app()
        assert isinstance(fresh_app, FastAPI)
        assert fresh_app is not main_module.app

    def test_module_app_root_endpoint_responds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The module-level app serves the root endpoint without lifespan."""
        self._set_env(monkeypatch)

        import crack_detection.backend.main as main_module
        from fastapi.testclient import TestClient

        client = TestClient(main_module.app)
        resp = client.get("/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["service"] == "CrackSight AI"
        assert body["status"] == "operational"
        assert body["version"] == "0.1.0"


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestCorsAndPreflight:
    """Tests for environment-driven CORS configuration and OPTIONS preflight
    behaviour through the real middleware stack.

    Each test builds a *fresh* application via ``create_app()`` under its own
    environment (``ALLOWED_ORIGINS`` / ``DEBUG``) and clears the cached
    ``get_settings`` before and after, mirroring the _use_fresh_settings
    convention. Middleware behaviour is exercised through TestClient against
    the real CORSMiddleware + ClerkAuthMiddleware stack, never inspected as
    bare configuration values.
    """

    _ENV = {
        "SECRET_KEY": "test-secret-key-12345",
        "CLERK_PUBLISHABLE_KEY": "pk_test_123",
        "CLERK_SECRET_KEY": "sk_test_123",
        "CLERK_JWT_ISSUER": "https://test.clerk.accounts.com",
        "CLERK_JWKS_URL": "https://test.clerk.accounts.com/.well-known/jwks.json",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db?sslmode=require",
        "R2_ACCOUNT_ID": "acc",
        "R2_ACCESS_KEY_ID": "key",
        "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET_NAME": "bucket",
        "R2_ENDPOINT": "https://test.r2.cloudflarestorage.com",
    }

    def _build_app(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        debug: str = "false",
        origins: str | None = None,
    ):
        # Environment first: ``crack_detection.backend.main`` must not be
        # imported before it (routers/auth.py builds Settings at module
        # import time), and the cached get_settings must reflect this
        # test's environment while create_app() runs.
        for key, value in self._ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("DEBUG", debug)
        if origins is not None:
            monkeypatch.setenv("ALLOWED_ORIGINS", origins)
        else:
            monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

        from fastapi.testclient import TestClient

        from crack_detection.backend import main
        from crack_detection.backend.config import get_settings

        get_settings.cache_clear()
        try:
            application = main.create_app()
        finally:
            get_settings.cache_clear()
        return TestClient(application, raise_server_exceptions=False)

    @staticmethod
    def _preflight_headers(origin: str) -> dict:
        return {
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        }

    # ------------------------------------------------------------ middleware order

    def test_cors_middleware_is_outermost(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CORSMiddleware runs first (Starlette: last added = outermost).

        Regression guard for the deployment-audit fix: ClerkAuthMiddleware
        must not be able to answer preflights or auth failures before CORS
        headers can be attached.
        """
        from fastapi.middleware.cors import CORSMiddleware

        from crack_detection.backend.middleware import ClerkAuthMiddleware

        client = self._build_app(monkeypatch, origins="https://app.example.com")

        classes = [m.cls for m in client.app.user_middleware]
        assert classes[0] is CORSMiddleware
        assert classes[1] is ClerkAuthMiddleware

    # ------------------------------------------------------------ deployment-like config (DEBUG=false)

    def test_preflight_from_allowed_origin_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A valid preflight from an allowed origin is answered 200 by CORS
        without any Clerk JWT and without reaching ClerkAuthMiddleware."""
        client = self._build_app(monkeypatch, origins="https://app.example.com")

        resp = client.options(
            "/inspections", headers=self._preflight_headers("https://app.example.com")
        )

        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == "https://app.example.com"

    def test_preflight_exposes_methods_headers_and_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Preflight advertises allowed methods, mirrored request headers and
        credentials support (required for Bearer-token requests)."""
        client = self._build_app(monkeypatch, origins="https://app.example.com")

        resp = client.options(
            "/inspections",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization, content-type",
            },
        )

        assert resp.status_code == 200
        methods = resp.headers["access-control-allow-methods"].upper()
        assert "GET" in methods and "POST" in methods and "DELETE" in methods
        mirrored = resp.headers["access-control-allow-headers"].lower()
        assert "authorization" in mirrored
        assert "content-type" in mirrored
        assert resp.headers.get("access-control-allow-credentials") == "true"

    def test_preflight_from_unconfigured_origin_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An origin outside the allowlist receives no CORS permission."""
        client = self._build_app(monkeypatch, origins="https://app.example.com")

        resp = client.options(
            "/inspections", headers=self._preflight_headers("https://evil.example.com")
        )

        assert resp.status_code == 400
        assert "access-control-allow-origin" not in resp.headers
        assert "Origin" in resp.headers.get("vary", "")

    def test_protected_request_without_token_rejected_from_allowed_origin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-OPTIONS protected request without a JWT is still rejected
        (authentication is NOT bypassed by the middleware reordering), and
        the authentication error response carries CORS headers so the browser
        front-end can read it."""
        client = self._build_app(monkeypatch, origins="https://app.example.com")

        resp = client.get(
            "/inspections", headers={"Origin": "https://app.example.com"}
        )

        assert resp.status_code == 401
        assert resp.json()["error"] == "unauthorized"
        assert resp.headers["access-control-allow-origin"] == "https://app.example.com"
        assert resp.headers.get("access-control-allow-credentials") == "true"

    def test_protected_request_from_unconfigured_origin_has_no_cors_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CORS does not grant allowance to origins outside the list."""
        client = self._build_app(monkeypatch, origins="https://app.example.com")

        resp = client.get("/inspections", headers={"Origin": "https://evil.example.com"})

        assert resp.status_code == 401
        assert "access-control-allow-origin" not in resp.headers

    def test_production_allows_only_configured_origins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With DEBUG=false only explicitly configured origins are permitted
        (no local-dev fallback, no wildcard)."""
        client = self._build_app(
            monkeypatch,
            debug="false",
            origins="https://app.example.com,https://extra.example.com",
        )

        allowed = client.options(
            "/inspections", headers=self._preflight_headers("https://extra.example.com")
        )
        denied = client.options(
            "/inspections", headers=self._preflight_headers("http://localhost:5173")
        )

        assert allowed.status_code == 200
        assert (
            allowed.headers["access-control-allow-origin"]
            == "https://extra.example.com"
        )
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers

    def test_production_without_origins_blocks_all_cross_origin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DEBUG=false with no ALLOWED_ORIGINS grants no cross-origin access
        (fail closed), while same-origin-style requests without Origin
        headers still work."""
        client = self._build_app(monkeypatch, debug="false")

        denied = client.options(
            "/inspections", headers=self._preflight_headers("https://app.example.com")
        )
        direct = client.get("/live")

        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers
        assert direct.status_code == 200

    def test_public_guest_preflight_succeeds_for_allowed_origin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Preflights to public paths are answered with CORS headers via the
        outermost CORS layer."""
        client = self._build_app(monkeypatch, origins="https://app.example.com")

        resp = client.options(
            "/guest/session",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-guest-session-token, content-type",
            },
        )

        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == "https://app.example.com"

    # ------------------------------------------------------------ local development config (DEBUG=true)

    def test_debug_default_allows_local_dev_origins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DEBUG=true with no ALLOWED_ORIGINS permits the Vite dev-server
        origins for local development."""
        client = self._build_app(monkeypatch, debug="true")

        resp = client.options(
            "/inspections", headers=self._preflight_headers("http://localhost:5173")
        )

        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"

    def test_debug_with_explicit_origins_honours_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit ALLOWED_ORIGINS wins over the debug fallback."""
        client = self._build_app(monkeypatch, debug="true", origins="https://app.example.com")

        allowed = client.options(
            "/inspections", headers=self._preflight_headers("https://app.example.com")
        )
        denied = client.options(
            "/inspections", headers=self._preflight_headers("http://localhost:5173")
        )

        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers

    # ------------------------------------------------------------ settings parsing unit coverage

    def test_allowed_origins_normalised_without_wildcards(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Comma-separated origins are trimmed, de-duplicated, trailing
        slashes removed and wildcard entries stripped (production must never
        receive "*")."""
        from crack_detection.backend.config import get_settings

        self._build_app(
            monkeypatch,
            debug="false",
            origins=(
                " https://a.example.com/ , https://b.example.com, "
                "https://a.example.com , *"
            ),
        )
        settings = get_settings()
        assert settings.allowed_origins == "https://a.example.com,https://b.example.com"
        assert settings.cors_allowed_origins == [
            "https://a.example.com",
            "https://b.example.com",
        ]
        assert "*" not in settings.cors_allowed_origins

    def test_wildcard_only_configuration_collapses_to_no_origins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A wildcard-only configuration collapses to no allowed origins."""
        from crack_detection.backend.config import get_settings

        self._build_app(monkeypatch, debug="false", origins="* , *")
        settings = get_settings()
        assert settings.cors_allowed_origins == []
        assert settings.allowed_origins == ""


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestEnsureRegisteredUser:
    """Tests for database.ensure_registered_user (Clerk -> local users sync)."""

    def test_inserts_new_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A new authenticated Clerk user is inserted into the users table."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)
        conn = _FakeConn()
        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.ensure_registered_user("clerk_user_123", "alice@example.com")

        assert result is True
        assert conn.committed is True
        sql, params = conn.cursor_obj.executed
        assert "INSERT INTO users (id, email, role)" in sql
        assert "ON CONFLICT (id) DO NOTHING" in sql
        assert params == ("clerk_user_123", "alice@example.com")

    def test_existing_user_not_duplicated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Re-synchronising an existing user uses ON CONFLICT DO NOTHING (no duplicate)."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)
        conn = _FakeConn()
        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.ensure_registered_user("clerk_user_123", "alice@example.com")

        assert result is True
        sql, _ = conn.cursor_obj.executed
        # Idempotent upsert: never an INSERT that could duplicate on repeat calls.
        assert "ON CONFLICT (id) DO NOTHING" in sql
        assert "UPDATE" not in sql.upper()

    def test_existing_role_and_data_preserved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Synchronisation never overwrites an existing record (DO NOTHING)."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)
        conn = _FakeConn()
        with patch.object(database, "get_db_connection", return_value=conn):
            database.ensure_registered_user("clerk_user_123", "alice@example.com")

        sql, _ = conn.cursor_obj.executed
        assert "ON CONFLICT (id) DO NOTHING" in sql
        assert "UPDATE" not in sql.upper()

    def test_missing_email_no_invented_or_invalid_record(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing email claim never writes: the email is NOT NULL and no
        email may be invented. The caller only performs a read-only
        existence check; no INSERT/UPDATE is ever issued."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)
        conn = _FakeConn()
        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.ensure_registered_user("clerk_user_123", None)

        assert result is False
        sql, params = conn.cursor_obj.executed
        assert "SELECT 1 FROM users" in sql
        assert params == ("clerk_user_123",)
        assert "INSERT" not in sql.upper()
        assert "UPDATE" not in sql.upper()
        assert conn.committed is False  # read-only: nothing committed

    def test_missing_email_existing_record_confirmed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without an email claim, an already-synchronised user is confirmed
        by a read-only SELECT (no record is overwritten or created)."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)
        conn = _FakeConn(fetchone_result=(1,))
        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.ensure_registered_user("clerk_user_123", None)

        assert result is True
        sql, _ = conn.cursor_obj.executed
        assert "SELECT 1 FROM users" in sql
        assert "INSERT" not in sql.upper()
        assert "UPDATE" not in sql.upper()
        assert conn.committed is False  # confirmation only, nothing written

    def test_missing_email_no_record_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without an email claim and with no local record, synchronisation
        fails closed: no invalid user row is created."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)
        conn = _FakeConn(fetchone_result=None)
        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.ensure_registered_user("clerk_user_123", None)

        assert result is False
        sql, _ = conn.cursor_obj.executed
        assert "INSERT" not in sql.upper()
        assert "UPDATE" not in sql.upper()
        assert conn.committed is False

    def test_missing_sub_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing Clerk user id is rejected before any database write."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)
        conn = _FakeConn()
        with patch.object(database, "get_db_connection", return_value=conn):
            result = database.ensure_registered_user(None, "alice@example.com")

        assert result is False
        assert conn.cursor_obj.executed is None

    def test_database_failure_fails_safely(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A database failure propagates rather than allowing inconsistent state."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        def _boom():
            raise database.DatabaseError("connection refused")

        with patch.object(database, "get_db_connection", side_effect=_boom):
            with pytest.raises(database.DatabaseError):
                database.ensure_registered_user("clerk_user_123", "alice@example.com")


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestGetCurrentUserSync:
    """Tests that get_current_user synchronises authenticated Clerk users."""

    def test_authenticated_user_is_synchronised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_current_user calls ensure_registered_user with Clerk sub and email."""
        from crack_detection.backend import dependencies

        synced: dict = {}

        def fake_ensure(user_id: str, email: str | None = None) -> bool:
            synced["args"] = (user_id, email)
            return True

        with patch.object(dependencies, "ensure_registered_user", side_effect=fake_ensure):
            request = SimpleNamespace(
                state=SimpleNamespace(
                    is_authenticated=True,
                    user_id="clerk_user_123",
                    user_email="alice@example.com",
                )
            )
            user = dependencies.get_current_user(request)

        assert synced["args"] == ("clerk_user_123", "alice@example.com")
        assert user["user_id"] == "clerk_user_123"
        assert user["email"] == "alice@example.com"
        assert user["is_authenticated"] is True
        assert user["is_guest"] is False
        assert user["guest_session_id"] is None

    def test_guest_user_not_synchronised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guest users are not passed to ensure_registered_user."""
        from crack_detection.backend import dependencies

        called: list = []

        def fake_ensure(user_id: str, email: str | None = None) -> bool:
            called.append((user_id, email))
            return True

        with patch.object(dependencies, "ensure_registered_user", side_effect=fake_ensure):
            request = SimpleNamespace(
                state=SimpleNamespace(
                    is_authenticated=False,
                    is_guest=True,
                    user_id=None,
                    user_email=None,
                    guest_session_id="sess_1",
                )
            )
            user = dependencies.get_current_user(request)

        assert called == []
        assert user["is_guest"] is True

    def test_unauthenticated_user_raises_401(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unauthenticated request is rejected with 401."""
        from crack_detection.backend import dependencies
        from fastapi import HTTPException

        request = SimpleNamespace(state=SimpleNamespace())
        with pytest.raises(HTTPException) as exc:
            dependencies.get_current_user(request)
        assert exc.value.status_code == 401

    def test_sync_failure_rejects_authenticated_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail closed: no authenticated identity is returned when local user
        synchronisation fails (e.g. missing email and no existing record)."""
        from crack_detection.backend import dependencies
        from crack_detection.backend.exceptions import UnauthorizedError

        with patch.object(dependencies, "ensure_registered_user", return_value=False):
            request = SimpleNamespace(
                state=SimpleNamespace(
                    is_authenticated=True,
                    user_id="clerk_user_123",
                    user_email=None,
                )
            )
            with pytest.raises(UnauthorizedError) as exc:
                dependencies.get_current_user(request)

        assert exc.value.status_code == 401
        assert exc.value.error_code == "unauthorized"

    def test_database_sync_failure_returns_503(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A database synchronisation failure yields a structured 503."""
        from crack_detection.backend import database, dependencies
        from crack_detection.backend.exceptions import ServiceUnavailableError

        def _boom(*args, **kwargs):
            raise database.DatabaseError("connection refused")

        with patch.object(dependencies, "ensure_registered_user", side_effect=_boom):
            request = SimpleNamespace(
                state=SimpleNamespace(
                    is_authenticated=True,
                    user_id="clerk_user_123",
                    user_email="alice@example.com",
                )
            )
            with pytest.raises(ServiceUnavailableError) as exc:
                dependencies.get_current_user(request)

        assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# Inspection creation blocked when registered-user synchronisation fails
# ---------------------------------------------------------------------------
class _SimulateVerifiedClerkMiddleware:
    """Pure ASGI middleware simulating the state a verified Clerk JWT
    produces (distinct from ``request.state`` ownership of the real
    middleware). Avoids ``BaseHTTPMiddleware`` portal threads so the
    fail-closed exception path is exercised in-process safely.

    ``user_id``/``user_email`` are configurable so ownership tests can
    act as a different authenticated user."""

    def __init__(
        self,
        app,
        user_id: str = "clerk_user_123",
        user_email: str = "alice@example.com",
    ) -> None:
        self.app = app
        self.user_id = user_id
        self.user_email = user_email

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            state = scope.setdefault("state", {})
            state["is_authenticated"] = True
            state["is_guest"] = False
            state["user_id"] = self.user_id
            state["user_email"] = self.user_email
            state["guest_session_id"] = None
        await self.app(scope, receive, send)


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestInspectionCreationBlockedOnSyncFailure:
    """End-to-end guard: inspection INSERT must never run without a
    synchronised local user record (foreign-key protection)."""

    def test_inspection_creation_blocked_when_sync_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from crack_detection.backend import dependencies as deps
        from crack_detection.backend.exceptions import register_exception_handlers

        _StdEnv.apply(monkeypatch)
        inspections_router = _load_inspections_router()

        app = FastAPI()
        app.add_middleware(_SimulateVerifiedClerkMiddleware)
        register_exception_handlers(app)
        app.include_router(inspections_router.router, prefix="/inspections")

        conn = MagicMock()
        conn.cursor.side_effect = AssertionError(
            "Inspection INSERT must not run without synchronised user"
        )
        app.dependency_overrides[deps.get_db] = lambda: conn

        with patch.object(deps, "ensure_registered_user", return_value=False):
            with TestClient(app) as client:
                resp = client.post(
                    "/inspections",
                    json={"title": "Facade survey"},
                )

        assert resp.status_code == 401, resp.text
        body = resp.json()
        assert body["error"] == "unauthorized"
        assert conn.cursor.called is False  # route body never reached

    def test_inspection_creation_allowed_when_sync_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same path succeeds once synchronisation returns True."""
        from unittest.mock import MagicMock, patch

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from crack_detection.backend import dependencies as deps
        from crack_detection.backend.exceptions import register_exception_handlers

        _StdEnv.apply(monkeypatch)
        inspections_router = _load_inspections_router()

        app = FastAPI()
        app.add_middleware(_SimulateVerifiedClerkMiddleware)
        register_exception_handlers(app)
        app.include_router(inspections_router.router, prefix="/inspections")

        row = {
            "id": "3f1d2b4e-0000-4000-8000-000000000001",
            "user_id": "clerk_user_123",
            "title": "Facade survey",
            "building_type": None,
            "building_location": None,
            "notes": None,
            "status": "draft",
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
        }

        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = row
        conn = MagicMock()
        conn.cursor.return_value = cursor
        app.dependency_overrides[deps.get_db] = lambda: conn

        with patch.object(deps, "ensure_registered_user", return_value=True):
            with TestClient(app) as client:
                resp = client.post("/inspections", json={"title": "Facade survey"})

        assert resp.status_code == 201, resp.text
        assert resp.json()["user_id"] == "clerk_user_123"


# ---------------------------------------------------------------------------
# Inspection reopen endpoint (POST /inspections/{id}/reopen)
# ---------------------------------------------------------------------------

class _SeqCursor:
    """In-memory cursor recording executed SQL and returning a queued
    sequence of ``fetchone()`` results (one per execute in call order)
    and, when provided, a fixed result set for ``fetchall()``."""

    def __init__(
        self,
        fetchone_results: list = None,
        fetchall_results: list = None,
        count_fetchone_results: list = None,
        count_fetchall_results: list = None,
    ) -> None:
        self.fetchone_results = list(fetchone_results or [])
        self.fetchall_results = list(fetchall_results if fetchall_results is not None else [])
        # Separate result queues for the COUNT(*) query used by listing endpoints
        # (returns {"total": N}). When provided they are consumed first by
        # ``fetchone()``; the main queues are used by the data query.
        self.count_fetchone_results = (
            list(count_fetchone_results or []) if count_fetchone_results is not None else []
        )
        self.count_fetchall_results = (
            list(count_fetchall_results or []) if count_fetchall_results is not None else []
        )
        self.executed: list = []

    def execute(self, sql: str, params=None) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        # Consume the dedicated COUNT result set first so listing endpoints
        # can distinguish the count row from data rows.
        if self.count_fetchone_results:
            return self.count_fetchone_results.pop(0)
        if self.fetchone_results:
            return self.fetchone_results.pop(0)
        return None

    def fetchall(self):
        return list(self.fetchall_results)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


class _SeqConn:
    """In-memory connection yielding a ``_SeqCursor``."""

    def __init__(
        self,
        fetchone_results: list = None,
        fetchall_results: list = None,
        count_fetchone_results: list = None,
        count_fetchall_results: list = None,
    ) -> None:
        self.cursor_obj = _SeqCursor(
            fetchone_results,
            fetchall_results,
            count_fetchone_results,
            count_fetchall_results,
        )
        self.committed = False
        self.closed = False

    def cursor(self, *args, **kwargs):
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _reopen_app(
    monkeypatch: pytest.MonkeyPatch,
    conn,
    *,
    user_id: str = "clerk_user_123",
    with_auth_middleware: bool = True,
):
    """Build a minimal app exposing only the real inspections router with a
    mocked DB connection (no production PostgreSQL is contacted). Shared by
    the Task 1.2 reopen tests and the Task 1.3 photo-listing tests."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crack_detection.backend import database
    from crack_detection.backend import dependencies as deps
    from crack_detection.backend.exceptions import register_exception_handlers

    _StdEnv.apply(monkeypatch)
    inspections_router = _load_inspections_router()

    # Identity synchronisation is verified separately by Task 1.1 tests;
    # stub it here so the reopen tests never open a real DB connection.
    monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

    # Hard guard: no unit test in this suite may open a real DB connection.
    monkeypatch.setattr(
        database, "get_db_connection",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("Unit tests must not open a real DB connection")
        ),
    )

    app = FastAPI()
    if with_auth_middleware:
        app.add_middleware(
            _SimulateVerifiedClerkMiddleware, user_id=user_id
        )
    register_exception_handlers(app)
    app.include_router(inspections_router.router, prefix="/inspections")
    app.dependency_overrides[deps.get_db] = lambda: conn
    return app


def _reopened_row() -> dict:
    """A post-reopen inspection row: draft status, ``completed_at`` cleared."""
    return {
        "id": "3f1d2b4e-0000-4000-8000-000000000002",
        "user_id": "clerk_user_123",
        "title": "Facade survey",
        "building_type": None,
        "building_location": None,
        "notes": "Hairline crack above window",
        "status": "draft",
        "created_at": datetime.now(timezone.utc),
        "completed_at": None,
        "photograph_count": 2,
    }


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestInspectionReopen:
    """Tests for POST /inspections/{id}/reopen."""

    def test_owner_reopens_completed_inspection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The owner can transition their completed inspection back to
        Draft; the returned row reflects the reopened state."""
        from fastapi.testclient import TestClient

        row = _reopened_row()
        conn = _SeqConn([row])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.post(f"/inspections/{row['id']}/reopen")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "draft"
        assert body["completed_at"] is None
        assert body["photograph_count"] == 2
        assert body["user_id"] == row["user_id"]

    def test_reopen_uses_conditional_status_transition(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The update is a single conditional statement scoped to the
        inspection id, the authenticated owner, and status 'completed'."""
        from fastapi.testclient import TestClient

        row = _reopened_row()
        conn = _SeqConn([row])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            client.post(f"/inspections/{row['id']}/reopen")

        assert len(conn.cursor_obj.executed) == 1
        sql, params = conn.cursor_obj.executed[0]
        assert "UPDATE inspections" in sql
        assert "status = 'draft'" in sql
        assert "completed_at = NULL" in sql
        assert "status = 'completed'" in sql  # conditional transition
        # Owner-scoped; inspection id is parsed as UUID by FastAPI routing.
        assert str(params[0]) == row["id"]
        assert params[1] == "clerk_user_123"
        assert conn.committed is True

    def test_reopen_preserves_photographs_and_predictions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reopening issues no DELETE or INSERT; photographs, prediction
        versions, observations, and reports remain unchanged."""
        from fastapi.testclient import TestClient

        row = _reopened_row()
        conn = _SeqConn([row])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.post(f"/inspections/{row['id']}/reopen")

        assert resp.status_code == 200
        for sql, _ in conn.cursor_obj.executed:
            assert "DELETE" not in sql.upper()
            assert "INSERT INTO" not in sql.upper()
            assert "UPDATE photographs" not in sql.upper()
            assert "UPDATE prediction_versions" not in sql.upper()
            assert "UPDATE reports" not in sql.upper()

    def test_reopen_already_draft_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reopening a draft inspection is rejected as an invalid
        transition."""
        from fastapi.testclient import TestClient

        row = _reopened_row()
        conn = _SeqConn([None, {"status": "draft"}])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.post(f"/inspections/{row['id']}/reopen")

        assert resp.status_code == 400, resp.text
        assert "draft" in resp.json()["detail"].lower()
        assert conn.committed is False  # no transition was applied

    def test_reopen_nonexistent_inspection_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reopening a nonexistent inspection returns 404."""
        from fastapi.testclient import TestClient

        inspect_id = "3f1d2b4e-0000-4000-8000-000000000009"
        conn = _SeqConn([None, None])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.post(f"/inspections/{inspect_id}/reopen")

        assert resp.status_code == 404, resp.text
        assert conn.committed is False

    def test_reopen_by_other_user_rejected_without_disclosure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A different authenticated user cannot reopen someone else's
        inspection and receives an opaque 404 instead of a 403."""
        from fastapi.testclient import TestClient

        row = _reopened_row()
        conn = _SeqConn([None, None])
        app = _reopen_app(
            monkeypatch, conn, user_id="clerk_other_user"
        )

        with TestClient(app) as client:
            resp = client.post(f"/inspections/{row['id']}/reopen")

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Inspection not found"
        assert conn.committed is False
        # The scoped lookup used the authenticated identity, not a
        # client-supplied owner id.
        _, followup_params = conn.cursor_obj.executed[1]
        assert str(followup_params[0]) == row["id"]
        assert followup_params[1] == "clerk_other_user"

    def test_reopen_unauthenticated_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unauthenticated requests cannot reopen inspections."""
        from fastapi.testclient import TestClient

        row = _reopened_row()
        conn = _SeqConn([None, None])
        app = _reopen_app(monkeypatch, conn, with_auth_middleware=False)

        with TestClient(app) as client:
            resp = client.post(f"/inspections/{row['id']}/reopen")

        assert resp.status_code == 401, resp.text
        assert conn.cursor_obj.executed == []  # no database access

    def test_reopen_guest_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guest principals cannot use the reopen endpoint; the real
        ``require_authenticated_user`` dependency rejects them."""
        from fastapi.testclient import TestClient

        row = _reopened_row()
        conn = _SeqConn([None, None])
        app = _reopen_app(monkeypatch, conn, with_auth_middleware=False)

        class _SimulateGuestMiddleware:
            """Pure ASGI middleware simulating a valid guest session state."""

            def __init__(self, app) -> None:
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    state = scope.setdefault("state", {})
                    state["is_authenticated"] = False
                    state["is_guest"] = True
                    state["user_id"] = None
                    state["user_email"] = None
                    state["guest_session_id"] = "sess_1"
                await self.app(scope, receive, send)

        _ = _SimulateGuestMiddleware  # named guard for readability
        app.add_middleware(_SimulateGuestMiddleware)

        with TestClient(app) as client:
            resp = client.post(f"/inspections/{row['id']}/reopen")

        assert resp.status_code == 403, resp.text
        assert conn.cursor_obj.executed == []

    def test_reopen_database_failure_handled_safely(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A database failure during reopen surfaces the structured
        internal-error response and no partial transition is committed."""
        from fastapi.testclient import TestClient

        from crack_detection.backend import database

        row = _reopened_row()
        conn = _SeqConn()

        def _boom(sql, params=None):
            raise database.DatabaseError("connection lost")

        conn.cursor_obj.execute = _boom
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(f"/inspections/{row['id']}/reopen")

        assert resp.status_code == 500, resp.text
        assert resp.json()["error"] == "internal_error"
        assert conn.committed is False


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestForeignOwnershipStandardisation:
    """Foreign-resource ownership checks return an opaque 404 (no existence
    disclosure), matching the download/reopen/listing convention. These tests
    cover endpoints that previously returned 403 via ``require_ownership``
    and now go through the shared helper's ownership-scoped 404 path."""

    def test_update_inspection_foreign_ownership_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Updating another user's inspection returns 404, not 403."""
        from fastapi.testclient import TestClient

        row = _reopened_row()  # owned by clerk_user_123
        conn = _SeqConn([row, row])  # SELECT then UPDATE

        app = _reopen_app(
            monkeypatch, conn, user_id="clerk_other_user"
        )

        with TestClient(app) as client:
            resp = client.patch(
                f"/inspections/{row['id']}",
                json={"title": "Tampered title"},
            )

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Resource not found"
        assert conn.committed is False

    def test_delete_inspection_foreign_ownership_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deleting another user's inspection returns 404, not 403."""
        from fastapi.testclient import TestClient

        row = _reopened_row()  # owned by clerk_user_123
        conn = _SeqConn([row])

        app = _reopen_app(
            monkeypatch, conn, user_id="clerk_other_user"
        )

        with TestClient(app) as client:
            resp = client.delete(f"/inspections/{row['id']}")

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Resource not found"
        assert conn.committed is False


# ---------------------------------------------------------------------------
# Inspection photograph listing endpoint (GET /inspections/{id}/photos)
# ---------------------------------------------------------------------------

_INSPECTION_ID = "3f1d2b4e-0000-4000-8000-000000000003"


def _photo_row(
    index: int,
    *,
    structure_type: str = "wall",
    observation: str = "Hairline crack above window",
    verification_status: str = "not_verified",
    model_version: str = "m3_baseline_b1",
    prediction_timestamp: Any = None,
    pixel_measurements: Any = None,
) -> dict:
    """A photograph row as the listing query returns it (no storage keys)."""
    created = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(
        minutes=index
    )
    if prediction_timestamp is None and model_version is not None:
        prediction_timestamp = created + timedelta(hours=1)
    if pixel_measurements is None and model_version is not None:
        pixel_measurements = {
            "crack_pixel_count": 1000 + index,
            "crack_percentage": 1.5 + index / 10,
        }
    return {
        "id": f"00000000-0000-4000-8000-00000000000{index + 1}",
        "inspection_id": _INSPECTION_ID,
        "structure_type": structure_type,
        "observation": observation,
        "verification_status": verification_status,
        "model_version": model_version,
        "prediction_timestamp": prediction_timestamp,
        "pixel_measurements": pixel_measurements,
        "created_at": created,
        "prediction_available": True,
    }


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestInspectionPhotos:
    """Tests for GET /inspections/{id}/photos (owner-scoped listing)."""

    def test_owner_retrieves_all_photographs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The owner retrieves all photographs of their inspection."""
        from fastapi.testclient import TestClient

        rows = [_photo_row(0), _photo_row(1)]
        conn = _SeqConn(fetchall_results=rows)
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["inspection_id"] == _INSPECTION_ID
        assert body["total"] == 2
        assert len(body["photographs"]) == 2

    def test_multiple_photographs_returned_correctly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each listed photograph carries the owner-facing metadata."""
        from fastapi.testclient import TestClient

        rows = [
            _photo_row(0),
            _photo_row(1, structure_type="beam"),
            _photo_row(2, structure_type="column"),
        ]
        conn = _SeqConn(fetchall_results=rows)
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 200
        photos = resp.json()["photographs"]
        assert [p["structure_type"] for p in photos] == ["wall", "beam", "column"]
        for expected, actual in zip(rows, photos):
            assert actual["id"] == expected["id"]
            assert actual["inspection_id"] == _INSPECTION_ID
            assert actual["observation"] == expected["observation"]
            assert actual["verification_status"] == expected["verification_status"]
            assert actual["created_at"] is not None

    def test_empty_inspection_returns_empty_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An existing inspection without photographs returns an empty list
        (a single LEFT JOIN row with a NULL photograph id), not 404."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchall_results=[{"id": None}])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["photographs"] == []
        assert body["total"] == 0

    def test_photographs_are_ordered_oldest_first(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ordering is created_at oldest-first with a stable tiebreaker."""
        from fastapi.testclient import TestClient

        rows = [_photo_row(0), _photo_row(1), _photo_row(2)]
        conn = _SeqConn(fetchall_results=rows)
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()["photographs"]]
        assert ids == [rows[0]["id"], rows[1]["id"], rows[2]["id"]]
        sql, _ = conn.cursor_obj.executed[0]
        assert "ORDER BY p.created_at ASC, p.id ASC" in sql

    def test_owner_scoped_single_round_trip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One parameterised LEFT JOIN query establishes inspection
        ownership and retrieves its photographs."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchall_results=[_photo_row(0)])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 200
        assert len(conn.cursor_obj.executed) == 1
        sql, params = conn.cursor_obj.executed[0]
        assert "LEFT JOIN photographs p ON p.inspection_id = i.id" in sql
        assert "WHERE i.id = %s AND i.user_id = %s" in sql
        assert str(params[0]) == _INSPECTION_ID
        assert params[1] == "clerk_user_123"  # authenticated identity only

    def test_prediction_metadata_returned(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Persisted prediction metadata is returned where available."""
        from fastapi.testclient import TestClient

        ts = datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        conn = _SeqConn(
            fetchall_results=[
                _photo_row(
                    0,
                    model_version="m3_baseline_b1",
                    prediction_timestamp=ts,
                    pixel_measurements={"crack_pixel_count": 1234},
                )
            ]
        )
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        photo = resp.json()["photographs"][0]
        assert photo["prediction_available"] is True
        assert photo["model_version"] == "m3_baseline_b1"
        assert photo["prediction_timestamp"] is not None
        assert photo["pixel_measurements"] == {"crack_pixel_count": 1234}

    def test_null_prediction_fields_handled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NULL prediction fields are represented as nulls, never fabricated."""
        from fastapi.testclient import TestClient

        unanalysed = _photo_row(
            0,
            model_version=None,
            prediction_timestamp=None,
            pixel_measurements=None,
        )
        unanalysed["prediction_available"] = False
        conn = _SeqConn(fetchall_results=[unanalysed])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 200
        photo = resp.json()["photographs"][0]
        assert photo["prediction_available"] is False
        assert photo["model_version"] is None
        assert photo["prediction_timestamp"] is None
        assert photo["pixel_measurements"] is None

    def test_internal_storage_keys_not_exposed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Internal R2 object keys and bucket details are never returned."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchall_results=[_photo_row(0)])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        photo = resp.json()["photographs"][0]
        expected_keys = {
            "id",
            "inspection_id",
            "structure_type",
            "observation",
            "verification_status",
            "model_version",
            "prediction_timestamp",
            "pixel_measurements",
            "created_at",
            "prediction_available",
        }
        assert set(photo.keys()) == expected_keys
        assert "original_image_key" not in resp.text
        assert "prediction_mask_key" not in resp.text
        assert "prediction_overlay_key" not in resp.text
        assert "bucket" not in resp.text.lower()

    def test_foreign_inspection_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Another user's inspection returns an opaque 404."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchall_results=[])
        app = _reopen_app(
            monkeypatch, conn, user_id="clerk_other_user"
        )

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Inspection not found"

    def test_nonexistent_inspection_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A nonexistent inspection returns 404."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchall_results=[])
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections/3f1d2b4e-0000-4000-8000-000000000099/photos")

        assert resp.status_code == 404, resp.text
        assert conn.committed is False  # read-only listing

    def test_guest_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guest principals cannot access the listing endpoint."""
        from fastapi.testclient import TestClient

        class _SimulateGuestMiddleware:
            """Pure ASGI middleware simulating a valid guest session state."""

            def __init__(self, app) -> None:
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    state = scope.setdefault("state", {})
                    state["is_authenticated"] = False
                    state["is_guest"] = True
                    state["user_id"] = None
                    state["user_email"] = None
                    state["guest_session_id"] = "sess_1"
                await self.app(scope, receive, send)

        conn = _SeqConn(fetchall_results=[])
        app = _reopen_app(monkeypatch, conn, with_auth_middleware=False)
        app.add_middleware(_SimulateGuestMiddleware)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 403, resp.text
        assert conn.cursor_obj.executed == []  # no database access

    def test_unauthenticated_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unauthenticated requests are rejected with 401."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchall_results=[])
        app = _reopen_app(monkeypatch, conn, with_auth_middleware=False)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 401, resp.text
        assert conn.cursor_obj.executed == []

    def test_database_failure_handled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A database failure surfaces the structured internal-error response."""
        from fastapi.testclient import TestClient

        from crack_detection.backend import database

        conn = _SeqConn()

        def _boom(sql, params=None):
            raise database.DatabaseError("connection lost")

        conn.cursor_obj.execute = _boom
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(f"/inspections/{_INSPECTION_ID}/photos")

        assert resp.status_code == 500, resp.text
        assert resp.json()["error"] == "internal_error"
        assert conn.committed is False


# ---------------------------------------------------------------------------
# Registered-user analysis persistence and versioning (Task 1.4)
# ---------------------------------------------------------------------------

_PHOTO_ID = "00000000-0000-4000-8000-000000000010"
_INSPECTION_ID = "3f1d2b4e-0000-4000-8000-000000000003"


def _fake_storage() -> SimpleNamespace:
    """Fake R2 storage recording uploads and deletions."""
    storage = SimpleNamespace()
    storage.uploaded: list = []
    storage.deleted: list = []

    def download_file(key: str) -> bytes:
        return b"fake-original-image-bytes"

    def upload_file(key: str, data, content_type: str) -> str:
        storage.uploaded.append((key, content_type))
        return key

    def delete_file(key: str) -> None:
        storage.deleted.append(key)

    storage.download_file = download_file
    storage.upload_file = upload_file
    storage.delete_file = delete_file
    return storage


_MEASUREMENTS_DEFAULT = object()


def _fake_inference_result(*, measurements=_MEASUREMENTS_DEFAULT, image_data=None) -> dict:
    if measurements is _MEASUREMENTS_DEFAULT:
        measurements = {
            "crack_pixel_count": 42,
            "crack_pixel_percentage": 6.5,
            "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1},
            "region_count": 2,
        }
    return {
        "binary_mask": [[0, 1], [1, 0]],
        "overlay": [[0, 0, 0], [0, 0, 0]],
        "model_version": "m3_baseline_b1",
        "inference_duration_ms": 123.45,
        "processing_status": "completed",
        "original_image_size": [256, 256],
        "pixel_measurements": measurements,
    }


def _analysis_photo_row(*, user_id="clerk_user_123", prediction_mask_key=None) -> dict:
    return {
        "id": _PHOTO_ID,
        "inspection_id": _INSPECTION_ID,
        "user_id": user_id,
        "structure_type": "wall",
        "observation": "Hairline crack",
        "verification_status": "not_verified",
        "original_image_key": f"inspections/{_INSPECTION_ID}/originals/{_PHOTO_ID}.jpg",
    "prediction_mask_key": prediction_mask_key,
    "prediction_overlay_key": None,
    "model_version": None,
    "prediction_timestamp": None,
    "pixel_measurements": None,
    "inspection_status": "draft",
    "created_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
}


def _existing_version_row() -> dict:
    return {
        "id": "22222222-2222-4222-8222-222222222222",
        "version_number": 1,
        "original_image_key": f"inspections/{_INSPECTION_ID}/originals/{_PHOTO_ID}.jpg",
        "binary_mask_key": f"inspections/{_PHOTO_ID}/masks/{_PHOTO_ID}_mask.png",
        "overlay_key": f"inspections/{_PHOTO_ID}/overlays/{_PHOTO_ID}_overlay.png",
        "model_version": "m3_baseline_b1",
        "prediction_timestamp": datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
        "pixel_measurements": {
            "crack_pixel_count": 10,
            "crack_pixel_percentage": 0.0,
            "bounding_box": None,
            "region_count": 0,
        },
        "inference_duration_ms": 50.0,
        "processing_status": "completed",
    }


def _photos_app(monkeypatch: pytest.MonkeyPatch, conn, *, is_guest: bool = False, user_id: str = "clerk_user_123", mock_allowance: bool = True):
    """Build a test app exposing only the real photographs router with mocked DB."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from crack_detection.backend import database
    from crack_detection.backend import dependencies as deps
    from crack_detection.backend.exceptions import register_exception_handlers
    import importlib.util
    from pathlib import Path

    _StdEnv.apply(monkeypatch)
    module_path = (
        Path(__file__).resolve().parents[2]
        / "src" / "crack_detection" / "backend" / "routers" / "photographs.py"
    )
    spec = importlib.util.spec_from_file_location(
        "photographs_router_under_test", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)
    monkeypatch.setattr(
        database,
        "get_db_connection",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("Unit tests must not open a real DB connection")
        ),
    )

    app = FastAPI()
    if is_guest:

        class _GuestMiddleware:
            def __init__(self, app) -> None:
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    state = scope.setdefault("state", {})
                    state["is_authenticated"] = False
                    state["is_guest"] = True
                    state["user_id"] = None
                    state["user_email"] = None
                    state["guest_session_id"] = "guest-sess-1"
                await self.app(scope, receive, send)

        app.add_middleware(_GuestMiddleware)
    else:
        app.add_middleware(_SimulateVerifiedClerkMiddleware, user_id=user_id)
        # Mock registered-user monthly allowance so that
        # analyse_photograph does not attempt to open a DB connection
        # during persistence-only tests. Tests that verify allowance
        # behaviour pass mock_allowance=False and set their own mocks.
        if mock_allowance:
            monkeypatch.setattr(
                database,
                "increment_user_analysis_count",
                lambda user_id, max_analyses=100, month_key=None: 1,
            )
            monkeypatch.setattr(
                database,
                "decrement_user_analysis_count",
                lambda user_id, month_key=None: None,
            )
    register_exception_handlers(app)
    app.include_router(module.router, prefix="/photos")
    app.dependency_overrides[deps.get_db] = lambda: conn
    return app, module


def _find_executed(conn, fragment: str):
    for sql, params in conn.cursor_obj.executed:
        if fragment in sql:
            return sql, params
    return None


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestAnalysisPersistence:
    """Focused tests for Task 1.4: analysis persistence, versioning, idempotency."""

    # ---- Prediction measurements ----

    def test_calculated_measurements_persisted_in_prediction_versions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Actual calculated measurements are stored in prediction_versions."""
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,  # idempotency check: no existing
            {"id": _PHOTO_ID},  # FOR UPDATE lock
            {"max_ver": 0},  # version lookup -> version 1
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        insert = _find_executed(conn, "INSERT INTO prediction_versions")
        assert insert is not None, "prediction_versions INSERT must run"
        _, params = insert
        assert params[8] is not None  # pixel_measurements (9th value)
        stored = params[8].adapted if hasattr(params[8], "adapted") else params[8]
        if isinstance(stored, str):
            stored = json.loads(stored)
        assert stored == _fake_inference_result()["pixel_measurements"]
        assert conn.committed is True

    def test_same_measurements_persisted_in_photograph(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The photograph row receives the same measurements as its version."""
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        update = _find_executed(conn, "UPDATE photographs")
        assert update is not None, "photographs UPDATE must run"
        _, params = update
        # UPDATE photographs SET prediction_mask_key, prediction_overlay_key,
        # model_version, prediction_timestamp, pixel_measurements WHERE id
        assert params[0].endswith("_mask.png")
        assert params[1].endswith("_overlay.png")
        assert params[2] == "m3_baseline_b1"
        assert params[3] is not None  # prediction_timestamp
        assert params[4] is not None  # pixel_measurements
        assert str(params[5]) == _PHOTO_ID
        stored = params[4].adapted if hasattr(params[4], "adapted") else params[4]
        if isinstance(stored, str):
            stored = json.loads(stored)
        assert stored["crack_pixel_count"] == 42
        assert conn.committed is True

    def test_unavailable_measurements_stored_as_null(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no measurements are available, NULL is stored (not fabricated)."""
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(
            module,
            "analyze_image",
            lambda image_data=None: _fake_inference_result(measurements=None, image_data=image_data),
        )
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        insert = _find_executed(conn, "INSERT INTO prediction_versions")
        assert insert is not None
        assert insert[1][8] is None  # pixel_measurements NULL
        update = _find_executed(conn, "UPDATE photographs")
        assert update is not None
        assert update[1][4] is None  # pixel_measurements NULL
        body = resp.json()
        assert body["pixel_measurements"] is None

    # ---- Photograph persistence ----

    def test_successful_analysis_updates_photograph_prediction_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        update = _find_executed(conn, "UPDATE photographs")
        assert update is not None
        _, params = update
        assert params[0] == f"inspections/{_PHOTO_ID}/masks/{_PHOTO_ID}_mask.png"
        assert params[1] == f"inspections/{_PHOTO_ID}/overlays/{_PHOTO_ID}_overlay.png"
        assert params[2] == "m3_baseline_b1"
        assert params[3] is not None
        assert params[4] is not None

    def test_photograph_reflects_latest_successful_prediction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The photograph references the newest prediction's artifacts."""
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["prediction_mask_key"] == f"inspections/{_PHOTO_ID}/masks/{_PHOTO_ID}_mask.png"
        assert body["prediction_overlay_key"] == f"inspections/{_PHOTO_ID}/overlays/{_PHOTO_ID}_overlay.png"
        assert body["original_image_key"] == _analysis_photo_row()["original_image_key"]
        assert body["pixel_measurements"]["crack_pixel_count"] == 42

    def test_failed_analysis_does_not_overwrite_existing_prediction_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed analysis leaves the previous photograph prediction intact."""
        from crack_detection.backend import database
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(prediction_mask_key="inspections/old/mask.png"),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        # Make the prediction_versions INSERT fail (DB persistence failure).
        def _wrapped(sql, params=None):
            conn.cursor_obj.execute_orig(sql, params)
            if "INSERT INTO prediction_versions" in sql:
                raise database.DatabaseError("insert failed")
        conn.cursor_obj.execute_orig = conn.cursor_obj.execute
        conn.cursor_obj.execute = _wrapped

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 500, resp.text
        # The photograph UPDATE never runs because the INSERT failed first.
        assert _find_executed(conn, "UPDATE photographs") is None
        assert conn.committed is False

    # ---- Versioning ----

    def test_first_successful_analysis_receives_version_1(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        insert = _find_executed(conn, "INSERT INTO prediction_versions")
        assert insert is not None
        assert insert[1][1] == 1  # version_number (2nd value)

    def test_second_successful_analysis_receives_version_2(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 1},  # one prior version
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        insert = _find_executed(conn, "INSERT INTO prediction_versions")
        assert insert is not None
        assert insert[1][1] == 2  # next version

    def test_reanalysis_receives_next_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            {"id": _PHOTO_ID},
            {"max_ver": 1},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/reanalyse")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["version_number"] == 2
        assert body["model_version"] == "m3_baseline_b1"
        assert body["previous_predictions_preserved"] is True
        insert = _find_executed(conn, "INSERT INTO prediction_versions")
        assert insert is not None
        assert insert[1][1] == 2

    def test_failed_analysis_does_not_consume_a_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import database
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        def _wrapped(sql, params=None):
            conn.cursor_obj.execute_orig(sql, params)
            if "INSERT INTO prediction_versions" in sql:
                raise database.DatabaseError("insert failed")
        conn.cursor_obj.execute_orig = conn.cursor_obj.execute
        conn.cursor_obj.execute = _wrapped

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 500, resp.text
        # No photograph UPDATE (version not consumed/persisted).
        assert _find_executed(conn, "UPDATE photographs") is None

    def test_version_assignment_uses_row_lock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Version numbers are assigned under a row lock (FOR UPDATE), not a
        bare SELECT MAX + 1, so concurrent attempts cannot collide."""
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        lock_sql = _find_executed(conn, "FOR UPDATE")
        assert lock_sql is not None, "photograph row must be locked for version assignment"
        assert "FROM photographs WHERE id = %s FOR UPDATE" in lock_sql[0]

    # ---- Idempotency ----

    def test_retry_same_request_does_not_create_duplicate_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import dependencies as deps

        existing = _existing_version_row()
        conn = _SeqConn([
            _analysis_photo_row(),
            existing,  # idempotency check finds existing version
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        assert _find_executed(conn, "INSERT INTO prediction_versions") is None
        body = resp.json()
        assert body["prediction_mask_key"] == existing["binary_mask_key"]
        assert body["pixel_measurements"] == existing["pixel_measurements"]

    def test_new_intentional_analysis_creates_new_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import dependencies as deps
        from uuid import UUID

        conn = _SeqConn([
            _analysis_photo_row(),
            None,  # first idempotency check: none
            {"id": _PHOTO_ID},
            {"max_ver": 0},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(
                f"/photos/{_PHOTO_ID}/analyse",
                headers={"Idempotency-Key": "11111111-1111-4111-8111-111111111111"},
            )

        assert resp.status_code == 202, resp.text
        insert = _find_executed(conn, "INSERT INTO prediction_versions")
        assert insert is not None
        assert insert[1][1] == 1
        assert insert[1][9] == UUID("11111111-1111-4111-8111-111111111111")

    def test_reanalysis_does_not_reuse_earlier_idempotency_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            {"id": _PHOTO_ID},
            {"max_ver": 1},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/reanalyse")

        assert resp.status_code == 200, resp.text
        insert = _find_executed(conn, "INSERT INTO prediction_versions")
        assert insert is not None
        assert insert[1][1] == 2  # new version, fresh idempotency key (uuid4)
        assert insert[1][9] is not None

    def test_guest_idempotency_and_allowance_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import database, dependencies as deps

        session = {
            "id": "guest-session-id",
            "analyses_count": 1,
            "is_active": True,
        }
        monkeypatch.setattr(
            database, "validate_guest_session", lambda token: session
        )
        monkeypatch.setattr(
            database,
            "increment_guest_analysis_count",
            lambda sid, max_analyses=3: 2,
        )

        existing = _existing_version_row()
        conn = _SeqConn([
            _analysis_photo_row(user_id="guest"),
            existing,  # idempotency check finds existing -> retry, no new work
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn, is_guest=True, user_id="guest")
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(
                f"/photos/{_PHOTO_ID}/analyse",
                headers={"X-Guest-Session-Token": "guest-token"},
            )

        assert resp.status_code == 202, resp.text
        # Retry: no new INSERT, no additional allowance consumption.
        assert _find_executed(conn, "INSERT INTO prediction_versions") is None
        body = resp.json()
        assert body["pixel_measurements"] == existing["pixel_measurements"]

    # ---- Failure handling ----

    def test_r2_upload_failure_creates_no_prediction_record(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
        ])
        storage = _fake_storage()

        def _failing_upload(key, data, content_type):
            raise StorageError("bucket unavailable")

        storage.upload_file = _failing_upload
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 500, resp.text
        assert _find_executed(conn, "INSERT INTO prediction_versions") is None
        assert _find_executed(conn, "UPDATE photographs") is None

    def test_database_persistence_failure_triggers_cleanup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import database
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        def _wrapped(sql, params=None):
            conn.cursor_obj.execute_orig(sql, params)
            if "INSERT INTO prediction_versions" in sql:
                raise database.DatabaseError("insert failed")
        conn.cursor_obj.execute_orig = conn.cursor_obj.execute
        conn.cursor_obj.execute = _wrapped

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 500, resp.text
        # Newly uploaded artifacts are cleaned up.
        uploaded_keys = {k for k, _ in storage.uploaded}
        assert set(storage.deleted) == uploaded_keys
        assert len(storage.deleted) == 2  # mask + overlay

    def test_previous_successful_artifacts_intact_after_failed_analysis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from crack_detection.backend import database
        from crack_detection.backend import dependencies as deps

        conn = _SeqConn([
            _analysis_photo_row(),
            None,
            {"id": _PHOTO_ID},
            {"max_ver": 0},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        def _wrapped(sql, params=None):
            conn.cursor_obj.execute_orig(sql, params)
            if "INSERT INTO prediction_versions" in sql:
                raise database.DatabaseError("insert failed")
        conn.cursor_obj.execute_orig = conn.cursor_obj.execute
        conn.cursor_obj.execute = _wrapped

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 500, resp.text
        # Only the newly uploaded keys are deleted; no "previous" keys are touched.
        assert set(storage.deleted) == {k for k, _ in storage.uploaded}
        assert "previous-version-key" not in storage.deleted

    # ---- Guest allowance: not consumed on failure ----

    def test_guest_allowance_not_consumed_on_inference_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed inference must not permanently consume guest allowance."""
        from crack_detection.backend import database, dependencies as deps

        session = {"id": "guest-session-id", "analyses_count": 0, "is_active": True}
        incremented: list = []
        decremented: list = []

        monkeypatch.setattr(
            database, "validate_guest_session", lambda token: session
        )
        monkeypatch.setattr(
            database,
            "increment_guest_analysis_count",
            lambda sid, max_analyses=3: incremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database,
            "decrement_guest_analysis_count",
            lambda sid: decremented.append(1) or 1,
        )

        conn = _SeqConn([
            _analysis_photo_row(user_id="guest"),
            None,  # idempotency check: none
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn, is_guest=True, user_id="guest")
        monkeypatch.setattr(
            module,
            "analyze_image",
            lambda image_data=None: (_ for _ in ()).throw(
                RuntimeError("model failure")
            ),
        )
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                f"/photos/{_PHOTO_ID}/analyse",
                headers={"X-Guest-Session-Token": "guest-token"},
            )

        assert resp.status_code == 500, resp.text
        assert incremented == [1], "allowance was reserved"
        assert decremented == [1], "allowance was compensated on failure"

    def test_guest_allowance_not_consumed_on_r2_upload_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed R2 upload must not permanently consume guest allowance."""
        from crack_detection.backend import database, dependencies as deps
        from crack_detection.backend.storage import StorageError

        session = {"id": "guest-session-id", "analyses_count": 0, "is_active": True}
        incremented: list = []
        decremented: list = []

        monkeypatch.setattr(
            database, "validate_guest_session", lambda token: session
        )
        monkeypatch.setattr(
            database,
            "increment_guest_analysis_count",
            lambda sid, max_analyses=3: incremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database,
            "decrement_guest_analysis_count",
            lambda sid: decremented.append(1) or 1,
        )

        conn = _SeqConn([
            _analysis_photo_row(user_id="guest"),
            None,  # idempotency check: none
        ])
        storage = _fake_storage()

        def _failing_upload(key, data, content_type):
            raise StorageError("bucket unavailable")

        storage.upload_file = _failing_upload
        app, module = _photos_app(monkeypatch, conn, is_guest=True, user_id="guest")
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                f"/photos/{_PHOTO_ID}/analyse",
                headers={"X-Guest-Session-Token": "guest-token"},
            )

        assert resp.status_code == 500, resp.text
        assert incremented == [1], "allowance was reserved"
        assert decremented == [1], "allowance was compensated on failure"

    def test_guest_allowance_not_consumed_on_db_persistence_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed DB persistence must not permanently consume guest allowance."""
        from crack_detection.backend import database, dependencies as deps

        session = {"id": "guest-session-id", "analyses_count": 0, "is_active": True}
        incremented: list = []
        decremented: list = []

        monkeypatch.setattr(
            database, "validate_guest_session", lambda token: session
        )
        monkeypatch.setattr(
            database,
            "increment_guest_analysis_count",
            lambda sid, max_analyses=3: incremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database,
            "decrement_guest_analysis_count",
            lambda sid: decremented.append(1) or 1,
        )

        conn = _SeqConn([
            _analysis_photo_row(user_id="guest"),
            None,  # idempotency check: none
            {"id": _PHOTO_ID},  # FOR UPDATE lock
            {"max_ver": 0},  # version lookup
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn, is_guest=True, user_id="guest")
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        def _wrapped(sql, params=None):
            conn.cursor_obj.execute_orig(sql, params)
            if "INSERT INTO prediction_versions" in sql:
                raise database.DatabaseError("insert failed")
        conn.cursor_obj.execute_orig = conn.cursor_obj.execute
        conn.cursor_obj.execute = _wrapped

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                f"/photos/{_PHOTO_ID}/analyse",
                headers={"X-Guest-Session-Token": "guest-token"},
            )

        assert resp.status_code == 500, resp.text
        assert incremented == [1], "allowance was reserved"
        assert decremented == [1], "allowance was compensated on failure"
        # Newly uploaded R2 artifacts cleaned up by _persist_analysis.
        uploaded_keys = {k for k, _ in storage.uploaded}
        assert set(storage.deleted) == uploaded_keys

    def test_guest_allowance_consumed_once_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A successful guest analysis consumes exactly one allowance."""
        from crack_detection.backend import database, dependencies as deps

        session = {"id": "guest-session-id", "analyses_count": 0, "is_active": True}
        incremented: list = []
        decremented: list = []

        monkeypatch.setattr(
            database, "validate_guest_session", lambda token: session
        )
        monkeypatch.setattr(
            database,
            "increment_guest_analysis_count",
            lambda sid, max_analyses=3: incremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database,
            "decrement_guest_analysis_count",
            lambda sid: decremented.append(1) or 1,
        )

        conn = _SeqConn([
            _analysis_photo_row(user_id="guest"),
            None,  # idempotency check: none
            {"id": _PHOTO_ID},
            {"max_ver": 0},
            {"id": "11111111-1111-4111-8111-111111111111"},
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn, is_guest=True, user_id="guest")
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(
                f"/photos/{_PHOTO_ID}/analyse",
                headers={"X-Guest-Session-Token": "guest-token"},
            )

        assert resp.status_code == 202, resp.text
        assert incremented == [1], "allowance reserved exactly once"
        assert decremented == [], "no compensation on success"

    # ---- Registered-user monthly allowance: not consumed on failure ----

    def test_registered_allowance_not_consumed_on_inference_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed inference must not permanently consume registered-user monthly allowance."""
        from crack_detection.backend import database, dependencies as deps

        incremented: list = []
        decremented: list = []

        monkeypatch.setattr(
            database,
            "increment_user_analysis_count",
            lambda user_id, max_analyses=100, month_key=None: incremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database,
            "decrement_user_analysis_count",
            lambda user_id, month_key=None: decremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database, "get_settings", lambda: SimpleNamespace(registered_monthly_analyses_limit=3)
        )

        conn = _SeqConn([
            _analysis_photo_row(user_id="clerk_user_123"),
            None,  # idempotency check: none
            (1,),  # allowance check INSERT RETURNING
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn, mock_allowance=False)
        monkeypatch.setattr(
            module,
            "analyze_image",
            lambda image_data=None: (_ for _ in ()).throw(
                RuntimeError("model failure")
            ),
        )
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 500, resp.text
        assert incremented == [1], "allowance was reserved"
        assert decremented == [1], "allowance was compensated on failure"

    def test_registered_allowance_not_consumed_on_r2_upload_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed R2 upload must not permanently consume registered-user monthly allowance."""
        from crack_detection.backend import database, dependencies as deps
        from crack_detection.backend.storage import StorageError

        incremented: list = []
        decremented: list = []

        monkeypatch.setattr(
            database,
            "increment_user_analysis_count",
            lambda user_id, max_analyses=100, month_key=None: incremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database,
            "decrement_user_analysis_count",
            lambda user_id, month_key=None: decremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database, "get_settings", lambda: SimpleNamespace(registered_monthly_analyses_limit=3)
        )

        conn = _SeqConn([
            _analysis_photo_row(user_id="clerk_user_123"),
            None,  # idempotency check: none
            (1,),  # allowance check INSERT RETURNING
        ])
        storage = _fake_storage()

        def _failing_upload(key, data, content_type):
            raise StorageError("bucket unavailable")

        storage.upload_file = _failing_upload
        app, module = _photos_app(monkeypatch, conn, mock_allowance=False)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 500, resp.text
        assert incremented == [1], "allowance was reserved"
        assert decremented == [1], "allowance was compensated on failure"

    def test_registered_allowance_not_consumed_on_db_persistence_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed DB persistence must not permanently consume registered-user monthly allowance."""
        from crack_detection.backend import database, dependencies as deps

        incremented: list = []
        decremented: list = []

        monkeypatch.setattr(
            database,
            "increment_user_analysis_count",
            lambda user_id, max_analyses=100, month_key=None: incremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database,
            "decrement_user_analysis_count",
            lambda user_id, month_key=None: decremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database, "get_settings", lambda: SimpleNamespace(registered_monthly_analyses_limit=3)
        )

        conn = _SeqConn([
            _analysis_photo_row(user_id="clerk_user_123"),
            None,  # idempotency check: none
            (1,),  # allowance check INSERT RETURNING
            {"id": _PHOTO_ID},  # FOR UPDATE lock
            {"max_ver": 0},  # version lookup
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn, mock_allowance=False)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        def _wrapped(sql, params=None):
            conn.cursor_obj.execute_orig(sql, params)
            if "INSERT INTO prediction_versions" in sql:
                raise database.DatabaseError("insert failed")
        conn.cursor_obj.execute_orig = conn.cursor_obj.execute
        conn.cursor_obj.execute = _wrapped

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 500, resp.text
        assert incremented == [1], "allowance was reserved"
        assert decremented == [1], "allowance was compensated on failure"
        # Newly uploaded R2 artifacts cleaned up by _persist_analysis.
        uploaded_keys = {k for k, _ in storage.uploaded}
        assert set(storage.deleted) == uploaded_keys

    def test_registered_allowance_consumed_once_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A successful registered-user analysis consumes exactly one monthly allowance."""
        from crack_detection.backend import database, dependencies as deps

        incremented: list = []
        decremented: list = []

        monkeypatch.setattr(
            database,
            "increment_user_analysis_count",
            lambda user_id, max_analyses=100, month_key=None: incremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database,
            "decrement_user_analysis_count",
            lambda user_id, month_key=None: decremented.append(1) or 1,
        )
        monkeypatch.setattr(
            database, "get_settings", lambda: SimpleNamespace(registered_monthly_analyses_limit=3)
        )

        conn = _SeqConn([
            _analysis_photo_row(user_id="clerk_user_123"),
            None,  # idempotency check: none
            {"id": _PHOTO_ID},  # FOR UPDATE lock
            {"max_ver": 0},  # version lookup
            {"id": "11111111-1111-4111-8111-111111111111"},  # INSERT RETURNING id
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn, mock_allowance=False)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        assert incremented == [1], "allowance was reserved exactly once"
        assert decremented == [], "no compensation on success"

    def test_registered_monthly_limit_enforced(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When monthly limit is reached, further analyses are rejected with 429."""
        from crack_detection.backend import database, dependencies as deps

        call_count = [0]

        def _incrementing(user_id, max_analyses=100, month_key=None):
            call_count[0] += 1
            return None  # Simulate monthly limit reached

        monkeypatch.setattr(
            database,
            "increment_user_analysis_count",
            _incrementing,
        )
        monkeypatch.setattr(
            database, "get_settings", lambda: SimpleNamespace(registered_monthly_analyses_limit=3)
        )

        conn = _SeqConn([
            _analysis_photo_row(user_id="clerk_user_123"),
            None,  # idempotency check: none
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn, mock_allowance=False)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            # Allowance returns ``None`` once the configured monthly limit is
            # exhausted, which must surface as a 429 from the endpoint.
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")
            assert resp.status_code == 429, resp.text
            assert "monthly analysis limit reached" in resp.json().get("detail", "").lower()

    # ---- Registered user idempotency without header ----

    def test_registered_idempotent_retry_deterministic_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A registered-user retry without Idempotency-Key header returns the
        existing result without creating a duplicate version."""
        from crack_detection.backend import dependencies as deps

        existing = _existing_version_row()
        conn = _SeqConn([
            _analysis_photo_row(),
            existing,  # idempotency check finds existing (deterministic key)
        ])
        storage = _fake_storage()
        app, module = _photos_app(monkeypatch, conn)
        monkeypatch.setattr(module, "analyze_image", _fake_inference_result)
        app.dependency_overrides[deps.get_r2_storage] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(f"/photos/{_PHOTO_ID}/analyse")

        assert resp.status_code == 202, resp.text
        # No new INSERT — the deterministic key matched the existing version.
        assert _find_executed(conn, "INSERT INTO prediction_versions") is None
        body = resp.json()
        assert body["prediction_mask_key"] == existing["binary_mask_key"]
        assert body["pixel_measurements"] == existing["pixel_measurements"]


# ---------------------------------------------------------------------------
# Registered-user image downloads (Task 1.5)
# ---------------------------------------------------------------------------

_DOWNLOAD_PHOTO_ID = "00000000-0000-4000-8000-000000000050"
_DOWNLOAD_INSPECTION_ID = "3f1d2b4e-0000-4000-8000-000000000060"


def _download_photo_row(*, user_id="clerk_user_123", with_prediction=True) -> dict:
    """A photograph row with the R2 keys the download endpoint selects."""
    mask_key = (
        f"inspections/{_DOWNLOAD_PHOTO_ID}/masks/{_DOWNLOAD_PHOTO_ID}_mask.png"
        if with_prediction
        else None
    )
    overlay_key = (
        f"inspections/{_DOWNLOAD_PHOTO_ID}/overlays/{_DOWNLOAD_PHOTO_ID}_overlay.png"
        if with_prediction
        else None
    )
    return {
        "id": _DOWNLOAD_PHOTO_ID,
        "inspection_id": _DOWNLOAD_INSPECTION_ID,
        "user_id": user_id,
        "original_image_key": f"inspections/{_DOWNLOAD_INSPECTION_ID}/originals/{_DOWNLOAD_PHOTO_ID}.jpg",
        "prediction_mask_key": mask_key,
        "prediction_overlay_key": overlay_key,
    }


def _downloads_app(
    monkeypatch: pytest.MonkeyPatch,
    conn,
    storage,
    *,
    is_guest: bool = False,
    user_id: str = "clerk_user_123",
):
    """Build a test app exposing the real photographs router with mocked DB.

    Reuses the ``_photos_app`` builder (registered or guest principal) and
    wires the mocked R2 storage into the route. No real R2 or PostgreSQL is
    contacted.
    """
    from crack_detection.backend import dependencies as deps_local

    app, _ = _photos_app(
        monkeypatch, conn, is_guest=is_guest, user_id=user_id
    )
    app.dependency_overrides[deps_local.get_r2_storage] = lambda: storage
    return app


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestRegisteredUserImageDownload:
    """Focused tests for Task 1.5: registered-user image downloads.

    Storage access is mocked; no real R2 or PostgreSQL is contacted. This
    verifies endpoint behaviour, authorisation, and ownership enforcement,
    not a live R2 integration.
    """

    def test_successful_original_image_download(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The owner can download the original uploaded photograph."""
        conn = _SeqConn([_download_photo_row()])
        downloaded: list = []
        storage = _fake_storage()
        storage.download_file = lambda key: downloaded.append(key) or b"original-bytes"
        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/original")

        assert resp.status_code == 200, resp.text
        assert resp.content == b"original-bytes"
        assert resp.headers["content-type"] == "image/jpeg"
        assert "attachment" in resp.headers["content-disposition"]
        # Ownership verified before storage; correct R2 key downloaded.
        assert downloaded == [_download_photo_row()["original_image_key"]]
        sql, params = conn.cursor_obj.executed[0]
        assert "JOIN inspections i ON p.inspection_id = i.id" in sql
        assert str(params[0]) == _DOWNLOAD_PHOTO_ID
        assert params[1] == "clerk_user_123"
        assert conn.committed is False  # read-only download

    def test_successful_mask_download(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The owner can download the AI-generated prediction mask."""
        conn = _SeqConn([_download_photo_row()])
        downloaded: list = []
        storage = _fake_storage()
        storage.download_file = lambda key: downloaded.append(key) or b"mask-bytes"
        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/mask")

        assert resp.status_code == 200, resp.text
        assert resp.content == b"mask-bytes"
        assert resp.headers["content-type"] == "image/png"
        assert downloaded == [_download_photo_row()["prediction_mask_key"]]

    def test_successful_overlay_download(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The owner can download the AI-generated prediction overlay."""
        conn = _SeqConn([_download_photo_row()])
        downloaded: list = []
        storage = _fake_storage()
        storage.download_file = lambda key: downloaded.append(key) or b"overlay-bytes"
        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/overlay")

        assert resp.status_code == 200, resp.text
        assert resp.content == b"overlay-bytes"
        assert resp.headers["content-type"] == "image/png"
        assert downloaded == [_download_photo_row()["prediction_overlay_key"]]

    def test_unauthenticated_request_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unauthenticated requests are rejected with 401 before any DB or
        storage access."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from crack_detection.backend import database
        from crack_detection.backend import dependencies as deps_local
        from crack_detection.backend.exceptions import register_exception_handlers
        import importlib.util
        from pathlib import Path

        _StdEnv.apply(monkeypatch)
        module_path = (
            Path(__file__).resolve().parents[2]
            / "src" / "crack_detection" / "backend" / "routers" / "photographs.py"
        )
        spec = importlib.util.spec_from_file_location(
            "photographs_router_download_unauth", module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        monkeypatch.setattr(deps_local, "ensure_registered_user", lambda uid, email=None: True)
        monkeypatch.setattr(
            database,
            "get_db_connection",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("Unit tests must not open a real DB connection")
            ),
        )

        conn = _SeqConn([_download_photo_row()])
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(module.router, prefix="/photos")
        app.dependency_overrides[deps_local.get_db] = lambda: conn
        app.dependency_overrides[deps_local.get_r2_storage] = lambda: _fake_storage()

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/original")

        assert resp.status_code == 401, resp.text
        # No database access occurred (auth rejected before the route ran).
        assert conn.cursor_obj.executed == []

    def test_guest_request_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Guest principals cannot access registered-user download endpoints."""
        conn = _SeqConn([_download_photo_row()])
        storage = _fake_storage()
        app = _downloads_app(
            monkeypatch, conn, storage, is_guest=True, user_id="guest"
        )

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/original")

        assert resp.status_code == 403, resp.text
        assert conn.cursor_obj.executed == []  # no database access

    def test_foreign_photograph_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A user cannot download another user's photograph; opaque 404."""
        conn = _SeqConn([None])
        storage = _fake_storage()
        app = _downloads_app(
            monkeypatch, conn, storage, user_id="clerk_other_user"
        )

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/original")

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Photograph not found"

    def test_nonexistent_photograph_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A nonexistent photograph returns 404 without touching storage."""
        conn = _SeqConn([None])
        storage = _fake_storage()
        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/original")

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Photograph not found"

    def test_unsupported_image_type_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unsupported image type is rejected with 400 before any storage
        access."""
        conn = _SeqConn([_download_photo_row()])
        storage = _fake_storage()
        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/thumbnail")

        assert resp.status_code == 400, resp.text
        assert "thumbnail" in resp.text
        # No database query or storage access for an unsupported type.
        assert conn.cursor_obj.executed == []

    def test_missing_mask_not_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A photograph without a prediction reports the mask as unavailable."""
        conn = _SeqConn([_download_photo_row(with_prediction=False)])
        storage = _fake_storage()
        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/mask")

        assert resp.status_code == 404, resp.text
        assert "not available" in resp.text

    def test_missing_overlay_not_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A photograph without a prediction reports the overlay as unavailable."""
        conn = _SeqConn([_download_photo_row(with_prediction=False)])
        storage = _fake_storage()
        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/overlay")

        assert resp.status_code == 404, resp.text
        assert "not available" in resp.text

    def test_r2_object_missing_reported_as_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An R2 object that no longer exists surfaces a storage error."""
        from crack_detection.backend.storage import StorageError

        conn = _SeqConn([_download_photo_row()])
        storage = _fake_storage()

        def _missing(key: str) -> bytes:
            raise StorageError("The specified key does not exist.")

        storage.download_file = _missing
        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/original")

        assert resp.status_code == 500, resp.text

    def test_r2_storage_failure_reported_as_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An R2 storage failure surfaces a storage error."""
        from crack_detection.backend.storage import StorageError

        conn = _SeqConn([_download_photo_row()])
        storage = _fake_storage()

        def _failing(key: str) -> bytes:
            raise StorageError("bucket unavailable")

        storage.download_file = _failing
        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(f"/photos/{_DOWNLOAD_PHOTO_ID}/download/original")

        assert resp.status_code == 500, resp.text


# ---------------------------------------------------------------------------
# Registered-user photograph upload (multipart)
# ---------------------------------------------------------------------------

_UPLOAD_PHOTO_ID = "00000000-0000-4000-8000-000000000090"
_UPLOAD_INSPECTION_ID = "3f1d2b4e-0000-4000-8000-000000000091"


def _upload_inspection_row(*, user_id="clerk_user_123", status="draft") -> dict:
    return {
        "id": _UPLOAD_INSPECTION_ID,
        "user_id": user_id,
        "title": "Facade survey",
        "status": status,
    }


def _upload_photograph_row(*, structure_type="wall") -> dict:
    return {
        "id": _UPLOAD_PHOTO_ID,
        "inspection_id": _UPLOAD_INSPECTION_ID,
        "user_id": "clerk_user_123",
        "structure_type": structure_type,
        "observation": None,
        "verification_status": "not_verified",
        "original_image_key": f"inspections/{_UPLOAD_INSPECTION_ID}/originals/{_UPLOAD_PHOTO_ID}.jpg",
        "prediction_mask_key": None,
        "prediction_overlay_key": None,
        "model_version": None,
        "prediction_timestamp": None,
        "pixel_measurements": None,
        "created_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    }


class _FakeUploadFile:
    """Stand-in for FastAPI's UploadFile with an async ``read()``."""

    def __init__(self, filename: str, content_type: str, data: bytes) -> None:
        self.filename = filename
        self.content_type = content_type
        self._data = data

    async def read(self) -> bytes:
        return self._data


def _make_png_bytes() -> bytes:
    from PIL import Image
    import io

    img = Image.new("RGB", (8, 8), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _upload_request(*, user_id="clerk_user_123") -> SimpleNamespace:
    """Fake authenticated registered-user request state."""
    return SimpleNamespace(
        state=SimpleNamespace(
            is_authenticated=True,
            is_guest=False,
            user_id=user_id,
            user_email="alice@example.com",
            guest_session_id=None,
        )
    )


def _load_photographs_upload_module():
    """Load the real photographs router module directly from its file.

    Bypasses the ``routers`` package ``__init__`` (which imports the guest
    router and requires the optional ``python-multipart`` dependency). The
    router code under test is real and unmodified.
    """
    import importlib.util
    from pathlib import Path

    module_path = (
        Path(__file__).resolve().parents[2]
        / "src" / "crack_detection" / "backend" / "routers" / "photographs.py"
    )
    spec = importlib.util.spec_from_file_location(
        "photographs_router_upload_under_test", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_upload(
    monkeypatch: pytest.MonkeyPatch,
    conn,
    storage,
    *,
    structure_type: str = "wall",
    file,
    user_id: str = "clerk_user_123",
):
    """Call the real upload handler directly with mocked DB and storage.

    ``python-multipart`` is not installed, so the multipart route cannot be
    driven through TestClient. Invoking the handler helper directly covers
    the identical validation, ownership, R2 upload, persistence, and
    cleanup behaviour, with auth exercised through the same
    ``require_ownership`` / ``get_current_user`` path the route uses.
    """
    import asyncio

    from crack_detection.backend import dependencies as deps

    # Provide the standard environment so get_settings() (used by image
    # validation) resolves, without touching a real database.
    _StdEnv.apply(monkeypatch)

    # Stub identity synchronisation so require_ownership -> get_current_user
    # never opens a real DB connection (guard matches _photos_app).
    monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

    module = _load_photographs_upload_module()
    request = _upload_request(user_id=user_id)

    return asyncio.run(
        module._store_uploaded_photograph(
            request,
            conn,
            storage,
            _UPLOAD_INSPECTION_ID,
            user_id,
            structure_type,
            file,
        )
    )


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestRegisteredUserPhotographUpload:
    """Focused tests for registered-user photograph upload.

    Storage and database are mocked; no real R2 or PostgreSQL is contacted.
    """

    # ---- Success ----

    def test_successful_registered_user_upload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A registered user can upload a photograph to their draft inspection."""
        from crack_detection.backend import dependencies as deps

        file = _FakeUploadFile("wall.jpg", "image/jpeg", _make_png_bytes())
        conn = _SeqConn([_upload_inspection_row(), _upload_photograph_row()])
        storage = _fake_storage()

        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)
        result = _run_upload(
            monkeypatch, conn, storage, file=file, structure_type="wall"
        )

        assert str(result.id) == _UPLOAD_PHOTO_ID
        assert str(result.inspection_id) == _UPLOAD_INSPECTION_ID
        assert result.user_id == "clerk_user_123"
        assert result.structure_type == "wall"
        assert result.verification_status == "not_verified"
        expected_prefix = f"inspections/{_UPLOAD_INSPECTION_ID}/originals/"
        assert result.original_image_key.startswith(expected_prefix)
        assert result.original_image_key.endswith(".jpg")
        assert result.prediction_mask_key is None
        # R2 received the original image once, under the inspection originals
        # prefix (the DB row's key is mocked; the upload key follows the same
        # pattern).
        assert len(storage.uploaded) == 1
        assert storage.uploaded[0][0].startswith(expected_prefix)
        assert storage.uploaded[0][0].endswith(".jpg")
        assert conn.committed is True

    def test_structure_type_persisted_for_each_component(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """wall, beam and column are each accepted and stored."""
        from crack_detection.backend import dependencies as deps

        for structure_type in ("wall", "beam", "column"):
            file = _FakeUploadFile(f"{structure_type}.png", "image/png", _make_png_bytes())
            conn = _SeqConn([_upload_inspection_row(), _upload_photograph_row(structure_type=structure_type)])
            storage = _fake_storage()

            result = _run_upload(
                monkeypatch, conn, storage, file=file, structure_type=structure_type
            )
            assert result.structure_type == structure_type

    # ---- Inspection eligibility ----

    def test_foreign_inspection_ownership_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A user cannot upload to another user's inspection (404 opaque,
        matching the download/reopen convention of not disclosing resource
        existence)."""
        from crack_detection.backend import dependencies as deps
        from fastapi import HTTPException

        file = _FakeUploadFile("wall.jpg", "image/jpeg", _make_png_bytes())
        conn = _SeqConn([_upload_inspection_row()])  # owned by clerk_user_123
        storage = _fake_storage()

        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

        try:
            _run_upload(
                monkeypatch,
                conn,
                storage,
                file=file,
                user_id="clerk_other_user",
            )
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("expected 404 for foreign inspection")

        # No photograph record was created.
        assert storage.uploaded == []
        assert conn.committed is False

    def test_update_photograph_foreign_ownership_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Updating another user's photograph returns 404, not 403."""
        from fastapi.testclient import TestClient

        photo_row = _upload_photograph_row()  # owned by clerk_user_123
        conn = _SeqConn([photo_row, photo_row])  # SELECT then UPDATE

        app, _ = _photos_app(
            monkeypatch, conn, user_id="clerk_other_user"
        )

        with TestClient(app) as client:
            resp = client.patch(
                f"/photos/{photo_row['id']}",
                json={"structure_type": "beam"},
            )

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Resource not found"

    def test_nonexistent_inspection_not_found(self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uploading to a nonexistent inspection returns 404."""
        from crack_detection.backend import dependencies as deps
        from fastapi import HTTPException

        file = _FakeUploadFile("wall.jpg", "image/jpeg", _make_png_bytes())
        conn = _SeqConn([None])
        storage = _fake_storage()

        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

        try:
            _run_upload(monkeypatch, conn, storage, file=file)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("expected 404 for nonexistent inspection")

        assert storage.uploaded == []
        assert conn.committed is False

    def test_completed_inspection_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Photographs cannot be added to a completed inspection."""
        from crack_detection.backend import dependencies as deps
        from fastapi import HTTPException

        file = _FakeUploadFile("wall.jpg", "image/jpeg", _make_png_bytes())
        conn = _SeqConn([_upload_inspection_row(status="completed")])
        storage = _fake_storage()

        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

        try:
            _run_upload(monkeypatch, conn, storage, file=file)
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "draft" in exc.detail.lower()
        else:
            raise AssertionError("expected 400 for completed inspection")

        assert storage.uploaded == []
        assert conn.committed is False

    # ---- Input validation ----

    def test_unsupported_structure_type_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unsupported structure type is rejected before storage/DB."""
        from crack_detection.backend import dependencies as deps
        from fastapi import HTTPException

        file = _FakeUploadFile("wall.jpg", "image/jpeg", _make_png_bytes())
        conn = _SeqConn([_upload_inspection_row()])
        storage = _fake_storage()

        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

        try:
            _run_upload(
                monkeypatch, conn, storage, file=file, structure_type="floor"
            )
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("expected 400 for unsupported structure type")

        assert storage.uploaded == []
        assert conn.committed is False

    def test_unsupported_image_format_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-image file extension is rejected (validated by extension)."""
        from crack_detection.backend import dependencies as deps
        from fastapi import HTTPException

        file = _FakeUploadFile("document.txt", "text/plain", b"not an image")
        conn = _SeqConn([_upload_inspection_row()])
        storage = _fake_storage()

        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

        try:
            _run_upload(monkeypatch, conn, storage, file=file)
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("expected 400 for unsupported format")

        assert storage.uploaded == []
        assert conn.committed is False

    def test_invalid_image_content_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A file with a valid extension but corrupt content is rejected."""
        from crack_detection.backend import dependencies as deps
        from fastapi import HTTPException

        file = _FakeUploadFile("corrupt.jpg", "image/jpeg", b"not-an-image-at-all")
        conn = _SeqConn([_upload_inspection_row()])
        storage = _fake_storage()

        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

        try:
            _run_upload(monkeypatch, conn, storage, file=file)
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("expected 400 for invalid image content")

        assert storage.uploaded == []
        assert conn.committed is False

    def test_file_size_exceeds_limit_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Files larger than the configured limit are rejected."""
        from crack_detection.backend import dependencies as deps
        from crack_detection.backend.config import get_settings
        from fastapi import HTTPException

        _StdEnv.apply(monkeypatch)
        settings = get_settings()
        oversized = b"x" * (settings.max_upload_size_bytes + 1)
        file = _FakeUploadFile("big.jpg", "image/jpeg", oversized)
        conn = _SeqConn([_upload_inspection_row()])
        storage = _fake_storage()

        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

        try:
            _run_upload(monkeypatch, conn, storage, file=file)
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("expected 400 for oversized file")

        assert storage.uploaded == []
        assert conn.committed is False

    # ---- Failure handling ----

    def test_r2_upload_failure_creates_no_photograph_record(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An R2 upload failure must not create a photograph record."""
        from crack_detection.backend import dependencies as deps
        from crack_detection.backend.storage import StorageError
        from fastapi import HTTPException

        file = _FakeUploadFile("wall.jpg", "image/jpeg", _make_png_bytes())
        conn = _SeqConn([_upload_inspection_row()])
        storage = _fake_storage()

        def _failing_upload(key, data, content_type):
            raise StorageError("bucket unavailable")

        storage.upload_file = _failing_upload
        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

        try:
            _run_upload(monkeypatch, conn, storage, file=file)
        except HTTPException as exc:
            assert exc.status_code == 500
        else:
            raise AssertionError("expected 500 for R2 upload failure")

        # No photograph record was attempted/committed.
        assert _find_executed(conn, "INSERT INTO photographs") is None
        assert conn.committed is False

    def test_database_persistence_failure_cleans_up_r2_object(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If R2 upload succeeds but DB persistence fails, the uploaded object
        is removed so no orphaned R2 object remains."""
        from crack_detection.backend import database, dependencies as deps
        from fastapi import HTTPException

        file = _FakeUploadFile("wall.jpg", "image/jpeg", _make_png_bytes())
        conn = _SeqConn([_upload_inspection_row()])
        storage = _fake_storage()

        def _wrapped(sql, params=None):
            conn.cursor_obj.execute_orig(sql, params)
            if "INSERT INTO photographs" in sql:
                raise database.DatabaseError("insert failed")

        conn.cursor_obj.execute_orig = conn.cursor_obj.execute
        conn.cursor_obj.execute = _wrapped
        monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

        try:
            _run_upload(monkeypatch, conn, storage, file=file)
        except HTTPException as exc:
            assert exc.status_code == 500
        else:
            raise AssertionError("expected 500 for DB persistence failure")

        # The newly uploaded R2 object was cleaned up.
        uploaded_keys = {k for k, _ in storage.uploaded}
        assert len(storage.uploaded) == 1
        assert set(storage.deleted) == uploaded_keys
        assert conn.committed is False

    # ---- Authentication enforcement (the gate the endpoint uses) ----

    def test_unauthenticated_request_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unauthenticated requests are rejected by require_authenticated_user
        before any upload logic runs (401)."""
        from crack_detection.backend import dependencies as deps
        from fastapi import HTTPException

        request = SimpleNamespace(state=SimpleNamespace())
        with pytest.raises(HTTPException) as exc:
            deps.require_authenticated_user(request)
        assert exc.value.status_code == 401

    def test_guest_request_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Guest principals are rejected by require_authenticated_user (403)."""
        from crack_detection.backend import dependencies as deps
        from fastapi import HTTPException

        request = SimpleNamespace(
            state=SimpleNamespace(
                is_authenticated=False,
                is_guest=True,
                user_id=None,
                user_email=None,
                guest_session_id="sess_1",
            )
        )
        with pytest.raises(HTTPException) as exc:
            deps.require_authenticated_user(request)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Registered-user inspection persistence beyond 24-hour guest-session expiry
# ---------------------------------------------------------------------------

_REGISTERED_USER_ID = "clerk_user_123"
_REGISTERED_INSPECTION_ID = "3f1d2b4e-0000-4000-8000-000000000070"
_REGISTERED_PHOTO_ID = "00000000-0000-4000-8000-000000000070"


def _persistence_inspection_row() -> dict:
    return {
        "id": _REGISTERED_INSPECTION_ID,
        "user_id": _REGISTERED_USER_ID,
        "title": "Facade survey",
        "building_type": None,
        "building_location": None,
        "notes": None,
        "status": "draft",
        "created_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "completed_at": None,
        "photograph_count": 1,
    }


def _persistence_photo_row() -> dict:
    return {
        "id": _REGISTERED_PHOTO_ID,
        "inspection_id": _REGISTERED_INSPECTION_ID,
        "user_id": _REGISTERED_USER_ID,
        "structure_type": "wall",
        "observation": "Hairline crack",
        "verification_status": "not_verified",
        "original_image_key": f"inspections/{_REGISTERED_INSPECTION_ID}/originals/{_REGISTERED_PHOTO_ID}.jpg",
        "prediction_mask_key": f"inspections/{_REGISTERED_PHOTO_ID}/masks/{_REGISTERED_PHOTO_ID}_mask.png",
        "prediction_overlay_key": f"inspections/{_REGISTERED_PHOTO_ID}/overlays/{_REGISTERED_PHOTO_ID}_overlay.png",
        "model_version": "m3_baseline_b1",
        "prediction_timestamp": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "pixel_measurements": {"crack_pixel_count": 1234},
        "created_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "prediction_available": True,
    }


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestRegisteredUserPersistenceBeyond24Hours:
    """Registered-user inspection results persist beyond the 24-hour
    guest-session expiry window. Guest session expiry and cleanup must
    never remove registered-user inspections, photographs, or prediction
    records, and registered-user retrieval must not apply any time-based
    cutoff."""

    # ---- Schema: no expiry on registered-user tables ----

    def test_registered_tables_have_no_expiry_column(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """inspections, photographs, and prediction_versions define no
        expires_at column; only guest_sessions carries an expiry."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        import inspect as py_inspect

        source = py_inspect.getsource(database.init_schema)
        blocks = {
            table: [
                s
                for s in source.split('"""')
                if f"CREATE TABLE IF NOT EXISTS {table}" in s
            ]
            for table in (
                "users",
                "inspections",
                "photographs",
                "prediction_versions",
                "guest_sessions",
            )
        }
        for table in ("users", "inspections", "photographs", "prediction_versions"):
            assert blocks[table], f"{table} CREATE TABLE statement must exist"
            assert "expires_at" not in blocks[table][0], (
                f"{table} must not define an expires_at expiry column"
            )
        assert blocks["guest_sessions"], "guest_sessions CREATE TABLE must exist"
        assert "expires_at" in blocks["guest_sessions"][0], (
            "guest_sessions must define the 24-hour expires_at expiry"
        )

    # ---- Guest cleanup isolation ----

    def test_cleanup_expired_guest_sessions_only_touches_guest_sessions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guest session cleanup must only deactivate rows in guest_sessions
        and must not delete or deactivate registered-user inspections,
        photographs, users, or prediction versions."""
        from crack_detection.backend import database

        _StdEnv.apply(monkeypatch)

        executed: list = []

        class _Cursor:
            def execute(self, sql: str, params=None) -> None:
                executed.append((sql, params))

            def fetchall(self):
                return []

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> bool:
                return False

        class _Conn:
            def cursor(self, *a, **k):
                return _Cursor()

            def commit(self) -> None:
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> bool:
                return False

        monkeypatch.setattr(database, "get_db_connection", lambda: _Conn())

        deactivated = database.cleanup_expired_guest_sessions()
        assert deactivated == 0

        for sql, _ in executed:
            upper = sql.upper()
            assert "guest_sessions" in sql, (
                f"cleanup must only target guest_sessions, got: {sql}"
            )
            assert "INSPECTIONS" not in upper
            assert "PHOTOGRAPHS" not in upper
            assert "PREDICTION_VERSIONS" not in upper
            assert "USERS" not in upper

    # ---- Retrieval after simulated time passage ----

    def test_registered_user_retrieves_photographs_after_simulated_24_hours(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Registered-user photographs remain listable after the original
        analysis request has completed, independent of guest session age."""
        from fastapi.testclient import TestClient

        inspection_row = _persistence_inspection_row()
        photo_row = _persistence_photo_row()
        assert inspection_row["created_at"] < datetime.now(timezone.utc) - timedelta(
            hours=24
        )

        conn = _SeqConn(
            fetchone_results=[inspection_row],
            fetchall_results=[photo_row],
        )
        app = _reopen_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(f"/inspections/{_REGISTERED_INSPECTION_ID}/photos")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["inspection_id"] == _REGISTERED_INSPECTION_ID
        assert body["total"] == 1
        assert len(body["photographs"]) == 1
        assert body["photographs"][0]["structure_type"] == "wall"
        assert body["photographs"][0]["prediction_available"] is True
        assert conn.committed is False  # read-only retrieval

    def test_registered_user_downloads_photograph_after_simulated_24_hours(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The registered-user original image remains downloadable from
        private R2 regardless of session age; no 24-hour cutoff applies and
        the key uses the inspections/ prefix (never guest/)."""
        from crack_detection.backend import dependencies as deps
        from fastapi.testclient import TestClient

        photo_row = _persistence_photo_row()
        conn = _SeqConn([photo_row])
        captured: list = []
        storage = _fake_storage()
        storage.download_file = lambda key: (captured.append(key) or b"persisted-bytes")

        app = _downloads_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.get(f"/photos/{_REGISTERED_PHOTO_ID}/download/original")

        assert resp.status_code == 200, resp.text
        assert resp.content == b"persisted-bytes"
        assert len(captured) == 1
        key = captured[0]
        assert key == photo_row["original_image_key"]
        assert key.startswith(f"inspections/{_REGISTERED_INSPECTION_ID}/originals/")
        assert not key.startswith("guest/")
        assert conn.committed is False  # read-only retrieval


# ---------------------------------------------------------------------------
# Inspection list filtering (GET /inspections)
# ---------------------------------------------------------------------------

def _list_app(
    monkeypatch: pytest.MonkeyPatch,
    conn,
    *,
    user_id: str = "clerk_user_123",
):
    """Build a minimal app exposing only the real inspections router with a
    mocked DB connection for list filtering tests."""
    from fastapi import FastAPI
    from crack_detection.backend import dependencies as deps
    from crack_detection.backend.exceptions import register_exception_handlers

    _StdEnv.apply(monkeypatch)
    inspections_router = _load_inspections_router()

    # Identity synchronisation is verified separately; stub it here.
    monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)

    app = FastAPI()
    app.add_middleware(_SimulateVerifiedClerkMiddleware, user_id=user_id)
    register_exception_handlers(app)
    app.include_router(inspections_router.router, prefix="/inspections")
    app.dependency_overrides[deps.get_db] = lambda: conn
    return app


def _sample_inspection_row(**overrides) -> dict:
    """Create a sample inspection row for list filtering tests."""
    from datetime import datetime, timezone
    from uuid import UUID, uuid5, NAMESPACE_DNS

    base = {
        "id": "3f1d2b4e-0000-4000-8000-000000000010",
        "user_id": "clerk_user_123",
        "title": "Facade survey",
        "building_type": "commercial",
        "building_location": "123 Main St",
        "notes": "Hairline crack",
        "status": "draft",
        "created_at": datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc),
        "completed_at": None,
        "photograph_count": 2,
    }
    base.update(overrides)
    # ``InspectionResponse.id`` is a UUID; allow short override strings by
    # deriving a deterministic UUID from them so the mock rows stay valid.
    raw_id = base.get("id")
    if isinstance(raw_id, str):
        try:
            UUID(raw_id)
        except (ValueError, AttributeError):
            base["id"] = str(uuid5(NAMESPACE_DNS, f"cracksight-test:{raw_id}"))
    return base


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestInspectionListFiltering:
    """Tests for GET /inspections filter query parameters."""

    def test_unfiltered_returns_all_user_inspections(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No filters returns all inspections for the authenticated user."""
        from fastapi.testclient import TestClient

        rows = [
            _sample_inspection_row(id="1", title="First"),
            _sample_inspection_row(id="2", title="Second"),
        ]
        conn = _SeqConn(count_fetchone_results=[{"total": 2}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 2
        assert len(body["inspections"]) == 2

    def test_search_filters_by_title_ilike(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """search parameter applies ILIKE filter on inspection title."""
        from fastapi.testclient import TestClient

        # The mock returns fixed rows; the test verifies the query includes the search condition
        rows = [_sample_inspection_row(id="1", title="Wall inspection")]
        conn = _SeqConn(count_fetchone_results=[{"total": 1}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?search=wall")

        assert resp.status_code == 200
        # Verify the WHERE clause contains the search condition
        sql, params = conn.cursor_obj.executed[0]  # count query
        assert "i.title ILIKE %s" in sql
        assert params[1] == "%wall%"

    def test_status_filter_valid_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """status filter with valid values passes validation."""
        from fastapi.testclient import TestClient

        rows = [_sample_inspection_row(id="1", status="completed")]
        conn = _SeqConn(count_fetchone_results=[{"total": 1}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?status=completed")

        assert resp.status_code == 200
        sql, params = conn.cursor_obj.executed[0]
        assert "i.status = %s" in sql
        assert params[1] == "completed"

    def test_status_filter_invalid_value_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """status filter with invalid value returns 400 validation error."""
        from fastapi.testclient import TestClient

        conn = _SeqConn()
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?status=invalid")

        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["error"] == "validation_error"
        assert "status" in body["message"]

    def test_structure_type_filter_valid_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """structure_type filter with valid values uses EXISTS on photographs."""
        from fastapi.testclient import TestClient

        rows = [_sample_inspection_row(id="1")]
        conn = _SeqConn(count_fetchone_results=[{"total": 1}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?structure_type=beam")

        assert resp.status_code == 200
        sql, params = conn.cursor_obj.executed[0]
        assert "EXISTS (SELECT 1 FROM photographs p" in sql
        assert "p.structure_type = %s" in sql
        assert "beam" in params

    def test_structure_type_filter_invalid_value_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """structure_type filter with invalid value returns 400."""
        from fastapi.testclient import TestClient

        conn = _SeqConn()
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?structure_type=floor")

        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["error"] == "validation_error"
        assert "structure" in body["message"].lower()

    def test_verification_status_filter_valid_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """verification_status filter with valid values uses EXISTS on photographs."""
        from fastapi.testclient import TestClient

        rows = [_sample_inspection_row(id="1")]
        conn = _SeqConn(count_fetchone_results=[{"total": 1}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?verification_status=correct")

        assert resp.status_code == 200
        sql, params = conn.cursor_obj.executed[0]
        assert "EXISTS (SELECT 1 FROM photographs p" in sql
        assert "p.verification_status = %s" in sql
        assert "correct" in params

    def test_verification_status_filter_invalid_value_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """verification_status filter with invalid value returns 400."""
        from fastapi.testclient import TestClient

        conn = _SeqConn()
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?verification_status=unknown")

        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["error"] == "validation_error"
        assert "verification" in body["message"].lower()

    def test_date_from_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """date_from filter uses >= on created_at with UTC midnight."""
        from fastapi.testclient import TestClient

        rows = [_sample_inspection_row(id="1")]
        conn = _SeqConn(count_fetchone_results=[{"total": 1}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?date_from=2026-10-01")

        assert resp.status_code == 200
        sql, params = conn.cursor_obj.executed[0]
        assert "i.created_at >= %s" in sql
        # The param should be a datetime at UTC midnight
        from datetime import datetime, timezone
        expected = datetime(2026, 10, 1, tzinfo=timezone.utc)
        # Find the datetime param
        datetime_params = [p for p in params if isinstance(p, datetime)]
        assert len(datetime_params) >= 1
        assert datetime_params[0] == expected

    def test_date_to_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """date_to filter uses < on created_at with next-day UTC midnight (inclusive)."""
        from fastapi.testclient import TestClient

        rows = [_sample_inspection_row(id="1")]
        conn = _SeqConn(count_fetchone_results=[{"total": 1}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?date_to=2026-10-31")

        assert resp.status_code == 200
        sql, params = conn.cursor_obj.executed[0]
        assert "i.created_at < %s" in sql
        from datetime import datetime, timezone, timedelta
        expected = datetime(2026, 10, 31, tzinfo=timezone.utc) + timedelta(days=1)
        datetime_params = [p for p in params if isinstance(p, datetime)]
        assert len(datetime_params) >= 1
        assert datetime_params[0] == expected

    def test_multiple_filters_combine_with_and(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple filters combine with AND in the WHERE clause."""
        from fastapi.testclient import TestClient

        rows = [_sample_inspection_row(id="1")]
        conn = _SeqConn(count_fetchone_results=[{"total": 1}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get(
                "/inspections?search=wall&status=completed&structure_type=beam"
            )

        assert resp.status_code == 200
        sql, _ = conn.cursor_obj.executed[0]
        assert "i.title ILIKE %s" in sql
        assert "i.status = %s" in sql
        assert "EXISTS (SELECT 1 FROM photographs p" in sql
        assert sql.count(" AND ") >= 2  # three conditions = two ANDs

    def test_total_returns_filtered_count_not_page_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """total in response equals filtered row count, not page size."""
        from fastapi.testclient import TestClient

        # Return 5 rows in fetchall but paginate with limit=2
        rows = [_sample_inspection_row(id=str(i)) for i in range(5)]
        conn = _SeqConn(
            count_fetchone_results=[{"total": 5}], fetchall_results=rows[:2]
        )
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?limit=2")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5  # filtered total, not page size
        assert len(body["inspections"]) == 2  # page size

    def test_owner_isolation_on_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """List only returns inspections owned by the authenticated user."""
        from fastapi.testclient import TestClient

        # User A's row - different user_id in WHERE clause
        rows = [_sample_inspection_row(user_id="clerk_user_123", id="1")]
        conn = _SeqConn(count_fetchone_results=[{"total": 1}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections")

        assert resp.status_code == 200
        sql, params = conn.cursor_obj.executed[0]
        assert "i.user_id = %s" in sql
        assert params[0] == "clerk_user_123"

    def test_guest_user_lists_own_inspections(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Guest user (user_id='guest') can list their own inspections."""
        from fastapi.testclient import TestClient

        rows = [_sample_inspection_row(user_id="guest", id="1")]
        conn = _SeqConn(count_fetchone_results=[{"total": 1}], fetchall_results=rows)
        app = _list_app(monkeypatch, conn, user_id="guest")

        with TestClient(app) as client:
            resp = client.get("/inspections")

        assert resp.status_code == 200
        sql, params = conn.cursor_obj.executed[0]
        assert "i.user_id = %s" in sql
        assert params[0] == "guest"

    def test_pagination_limit_offset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """limit and offset are applied to the page query."""
        from fastapi.testclient import TestClient

        rows = [_sample_inspection_row(id=str(i)) for i in range(5)]
        conn = _SeqConn(
            count_fetchone_results=[{"total": 5}], fetchall_results=rows[:2]
        )
        app = _list_app(monkeypatch, conn)

        with TestClient(app) as client:
            resp = client.get("/inspections?limit=2&offset=2")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["inspections"]) == 2
        # Page query should have LIMIT 2 OFFSET 2
        page_sql = conn.cursor_obj.executed[1][0]
        assert "LIMIT %s" in page_sql
        assert "OFFSET %s" in page_sql


# ---------------------------------------------------------------------------
# Task 6 (Step 3): Professional PDF report generation endpoint
# ---------------------------------------------------------------------------

_REPORT_INSPECTION_ID = "11111111-2222-4333-8444-555555555555"
_REPORT_DB_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _report_png_bytes() -> bytes:
    """Small valid PNG used as fake R2 photograph content."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color=(90, 90, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _report_inspection_row(status: str = "draft", user_id: str = "clerk_user_123") -> dict:
    return {
        "id": _REPORT_INSPECTION_ID,
        "user_id": user_id,
        "title": "Tower A facade survey",
        "building_type": "Residential",
        "building_location": "Downtown district",
        "notes": "Annual visual check for settlement cracks.",
        "status": status,
        "created_at": datetime(2026, 11, 1, 9, 0, 0, tzinfo=timezone.utc),
        "completed_at": (
            None if status == "draft"
            else datetime(2026, 11, 2, 15, 30, 0, tzinfo=timezone.utc)
        ),
    }


def _report_photo_rows(
    count: int = 1, *, with_overlay: bool = True, inspection_id: str = _REPORT_INSPECTION_ID
) -> list:
    rows = []
    for i in range(count):
        pid = f"00000000-0000-4000-8000-{i:012d}"
        rows.append(
            {
                "id": pid,
                "structure_type": "wall",
                "observation": "Hairline crack near window frame.",
                "verification_status": "correct",
                "model_version": "ep120",
                "prediction_timestamp": datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc),
                "pixel_measurements": {"crack_length_px": 214.5, "max_width_px": 6.2},
                "original_image_key": f"inspections/{inspection_id}/originals/{pid}.jpg",
                "prediction_overlay_key": (
                    f"inspections/{inspection_id}/overlays/{pid}_overlay.png"
                    if with_overlay
                    else None
                ),
            }
        )
    return rows


def _report_insert_row() -> dict:
    return {
        "id": _REPORT_DB_ID,
        "generated_at": datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc),
    }


def _report_storage(*, download_fail: bool = False, upload_fail: bool = False):
    """Fake R2 storage recording uploads/downloads/deletes for report tests."""
    from crack_detection.backend.storage import StorageError

    storage = SimpleNamespace()
    storage.uploaded = []
    storage.downloads = []
    storage.deleted = []
    png = _report_png_bytes()

    def download_file(key: str) -> bytes:
        if download_fail:
            raise StorageError("bucket unreachable")
        storage.downloads.append(key)
        return png

    def upload_file(key: str, data: bytes, content_type: str) -> str:
        if upload_fail:
            raise StorageError("quota exceeded")
        storage.uploaded.append(
            {"key": key, "content_type": content_type, "data": data}
        )
        return key

    def delete_file(key: str) -> None:
        storage.deleted.append(key)

    storage.download_file = download_file
    storage.upload_file = upload_file
    storage.delete_file = delete_file
    return storage


def _reports_app(
    monkeypatch: pytest.MonkeyPatch,
    conn,
    *,
    mode: str = "registered",
    user_id: str = "clerk_user_123",
):
    """Build a test app exposing only the real reports router with a mocked DB.

    ``mode`` selects the simulated request identity: ``"registered"``
    (verified Clerk middleware), ``"guest"``, or ``"anonymous"`` (no
    middleware at all).
    """
    import importlib.util
    from pathlib import Path

    from fastapi import FastAPI

    from crack_detection.backend import database
    from crack_detection.backend import dependencies as deps
    from crack_detection.backend.exceptions import register_exception_handlers

    _StdEnv.apply(monkeypatch)
    module_path = (
        Path(__file__).resolve().parents[2]
        / "src" / "crack_detection" / "backend" / "routers" / "reports.py"
    )
    spec = importlib.util.spec_from_file_location("reports_router_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(deps, "ensure_registered_user", lambda uid, email=None: True)
    monkeypatch.setattr(
        database,
        "get_db_connection",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("Unit tests must not open a real DB connection")
        ),
    )

    app = FastAPI()
    if mode == "guest":

        class _GuestMiddleware:
            def __init__(self, app) -> None:
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    state = scope.setdefault("state", {})
                    state["is_authenticated"] = False
                    state["is_guest"] = True
                    state["user_id"] = None
                    state["user_email"] = None
                    state["guest_session_id"] = "guest-sess-1"
                await self.app(scope, receive, send)

        app.add_middleware(_GuestMiddleware)
    elif mode == "registered":
        app.add_middleware(_SimulateVerifiedClerkMiddleware, user_id=user_id)

    register_exception_handlers(app)
    app.include_router(module.router, prefix="/reports")
    app.dependency_overrides[deps.get_db] = lambda: conn
    return app, module


def _pdf_text(data: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() for page in reader.pages)


def _pdf_page_count(data: bytes) -> int:
    from io import BytesIO

    from pypdf import PdfReader

    return len(PdfReader(BytesIO(data)).pages)


def _r2_storage_dep():
    from crack_detection.backend import dependencies as deps
    return deps.get_r2_storage


def _report_generate_url() -> str:
    return f"/reports/generate/{_REPORT_INSPECTION_ID}"


def _report_download_url() -> str:
    return f"/reports/{_REPORT_DB_ID}/download"


def _report_download_row(owner: str = "clerk_user_123") -> dict:
    """Row returned by the download endpoint's ownership-scoped query."""
    return {
        "report_pdf_key": f"reports/{_REPORT_DB_ID}.pdf",
        "user_id": owner,
    }


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestReportGeneration:
    """Step 3 of Task 6: POST /reports/generate/{inspection_id}."""

    # ---- happy paths ----

    def test_generate_report_success_registered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Registered user generates a PDF, stored on R2 and persisted."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(status="draft"),
                _report_insert_row(),
            ],
            fetchall_results=_report_photo_rows(count=1),
        )
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["report_id"] == _REPORT_DB_ID
        assert body["download_url"] == f"/reports/{_REPORT_DB_ID}/download"
        assert "generated_at" in body

        # PDF physically stored in R2 with PDF content type
        assert len(storage.uploaded) == 1
        upload = storage.uploaded[0]
        assert upload["key"].startswith("reports/")
        assert upload["key"].endswith(".pdf")
        assert upload["content_type"] == "application/pdf"

        # Embedded inspection data renders inside the stored PDF
        pdf_text = _pdf_text(upload["data"])
        assert "Tower A facade survey" in pdf_text
        assert "Annual visual check" in pdf_text

        # Report row persisted with the real page count
        insert_sql, insert_params = conn.cursor_obj.executed[-1]
        assert "INSERT INTO reports" in insert_sql
        assert "page_count" in insert_sql
        # The generated report id is internally consistent with its R2 key
        assert str(insert_params[0]) == upload["key"].removeprefix("reports/").removesuffix(".pdf")
        assert insert_params[3] == upload["key"]
        assert str(insert_params[1]) == _REPORT_INSPECTION_ID
        assert insert_params[2] == "clerk_user_123"
        assert insert_params[3] == upload["key"]
        assert insert_params[4] == _pdf_page_count(upload["data"])
        assert conn.committed is True

        # Internal R2 keys never leak to the client
        assert "originals/" not in resp.text
        assert "overlays/" not in resp.text

    def test_draft_inspection_labelled_in_pdf(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Draft inspections may be reported and labelled 'Draft'."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(status="draft"),
                _report_insert_row(),
            ],
            fetchall_results=[],
        )
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 200, resp.text
        pdf_text = _pdf_text(storage.uploaded[0]["data"])
        assert "Draft" in pdf_text
        assert "No photographs were analysed" in pdf_text

    def test_completed_inspection_labelled_in_pdf(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Completed inspections may be reported and labelled 'Completed'."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(status="completed"),
                _report_insert_row(),
            ],
            fetchall_results=[],
        )
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 200, resp.text
        pdf_text = _pdf_text(storage.uploaded[0]["data"])
        assert "Completed" in pdf_text

    def test_multiple_photographs_assembled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All photographs are included and their count is shown."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(),
                _report_insert_row(),
            ],
            fetchall_results=_report_photo_rows(count=2),
        )
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 200, resp.text
        upload = storage.uploaded[0]
        pdf_text = _pdf_text(upload["data"])
        assert "Hairline crack near window frame" in pdf_text
        assert "2" in pdf_text  # photographs analysed count
        assert len(storage.downloads) == 4  # 2 originals + 2 overlays
        # Persisted page count matches real PDF structure
        insert_params = conn.cursor_obj.executed[-1][1]
        assert insert_params[4] == _pdf_page_count(upload["data"])

    def test_missing_overlay_degrades_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An analysed photograph without an overlay still reports, with
        an explicit placeholder (only the original is downloaded)."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(),
                _report_insert_row(),
            ],
            fetchall_results=_report_photo_rows(count=1, with_overlay=False),
        )
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 200, resp.text
        assert len(storage.downloads) == 1  # original only
        pdf_text = _pdf_text(storage.uploaded[0]["data"])
        assert "Predicted overlay not available" in pdf_text

    # ---- access control ----

    def test_guest_generation_forbidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Guests are rejected with 403 and nothing is generated."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[])
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn, mode="guest")
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 403, resp.text
        assert conn.cursor_obj.executed == []
        assert storage.uploaded == []

    def test_unauthenticated_generation_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Requests without identity state are rejected with 401."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[])
        app, _module = _reports_app(monkeypatch, conn, mode="anonymous")

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 401, resp.text
        assert conn.cursor_obj.executed == []

    def test_unknown_inspection_opaque_404(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nonexistent inspections return an opaque 404; nothing generated."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[None])
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Inspection not found"
        assert storage.uploaded == []
        # Only the inspection lookup ran — no report INSERT
        assert len(conn.cursor_obj.executed) == 1

    def test_foreign_inspection_opaque_404(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Another user's inspection is indistinguishable from nonexistent."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(user_id="someone_else")
            ]
        )
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Resource not found"
        assert storage.uploaded == []
        assert len(conn.cursor_obj.executed) == 1

    # ---- failure stages and compensation ----

    def test_asset_download_failure_returns_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R2 failures while fetching photograph images surface as 500."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(),
                _report_insert_row(),
            ],
            fetchall_results=_report_photo_rows(count=1),
        )
        storage = _report_storage(download_fail=True)
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 500, resp.text
        assert "Failed to retrieve photograph assets" in resp.json()["detail"]
        assert storage.uploaded == []
        # No report row was inserted
        assert all(
            "INSERT INTO reports" not in sql
            for sql, _ in conn.cursor_obj.executed
        )
        assert conn.committed is False

    def test_pdf_generation_failure_no_side_effects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ReportLab failure surfaces as 500 with nothing uploaded/persisted."""
        import types

        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(),
                _report_insert_row(),
            ],
            fetchall_results=_report_photo_rows(count=1),
        )
        storage = _report_storage()
        app, module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        def _boom(*args, **kwargs):
            raise RuntimeError("reportlab exploded")

        monkeypatch.setattr(module, "generate_inspection_report_pdf", _boom)

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 500, resp.text
        assert "Failed to generate PDF report" in resp.json()["detail"]
        assert storage.uploaded == []
        assert all(
            "INSERT INTO reports" not in sql
            for sql, _ in conn.cursor_obj.executed
        )
        assert conn.committed is False

    def test_r2_upload_failure_no_orphan(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Upload failure results in 500, no report row, no orphan PDF."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(),
                _report_insert_row(),
            ],
            fetchall_results=_report_photo_rows(count=1),
        )
        storage = _report_storage(upload_fail=True)
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 500, resp.text
        assert "Failed to upload generated report" in resp.json()["detail"]
        assert storage.uploaded == []
        assert all(
            "INSERT INTO reports" not in sql
            for sql, _ in conn.cursor_obj.executed
        )
        assert conn.committed is False

    def test_persistence_failure_removes_uploaded_pdf(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DB failure after upload compensates by deleting the PDF."""
        from fastapi.testclient import TestClient

        from crack_detection.backend import database

        conn = _SeqConn(
            fetchone_results=[
                _report_inspection_row(),
                _report_insert_row(),
            ],
            fetchall_results=_report_photo_rows(count=1),
        )
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        orig_execute = conn.cursor_obj.execute

        def _failing_execute(sql, params=None):
            orig_execute(sql, params)
            if "INSERT INTO reports" in sql:
                raise database.DatabaseError("simulated insert failure")

        conn.cursor_obj.execute = _failing_execute

        with TestClient(app) as client:
            resp = client.post(_report_generate_url())

        assert resp.status_code == 500, resp.text
        assert "Failed to record report generation" in resp.json()["detail"]
        # The uploaded PDF was removed (best-effort compensation)
        assert len(storage.deleted) == 1
        assert storage.deleted[0].startswith("reports/")
        assert storage.deleted[0].endswith(".pdf")
        assert conn.committed is False


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestReportDownload:
    """Step 4 of Task 6: GET /reports/{report_id}/download.

    Storage access is mocked; no real R2 or PostgreSQL is contacted. This
    verifies endpoint behaviour, authorisation, and ownership enforcement,
    not a live R2 integration.
    """

    def test_successful_report_download(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The owning registered user gets the actual PDF bytes streamed."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[_report_download_row()])
        downloaded: list = []
        storage = _report_storage()
        storage.download_file = (
            lambda key: downloaded.append(key) or b"%PDF-1.7 fake report bytes"
        )
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.get(_report_download_url())

        assert resp.status_code == 200, resp.text
        # Actual PDF bytes, not JSON or a URL
        assert resp.content == b"%PDF-1.7 fake report bytes"
        assert "json" not in resp.headers["content-type"]
        # Response headers
        assert resp.headers["content-type"] == "application/pdf"
        assert "attachment" in resp.headers["content-disposition"]
        assert (
            resp.headers["content-disposition"]
            == f'attachment; filename="cracksight-report-{_REPORT_DB_ID}.pdf"'
        )
        # Ownership verified through the inspection before storage access;
        # the correct internal R2 key was used
        assert downloaded == [_report_download_row()["report_pdf_key"]]
        sql, params = conn.cursor_obj.executed[0]
        assert "JOIN inspections i ON r.inspection_id = i.id" in sql
        assert str(params[0]) == _REPORT_DB_ID
        assert conn.committed is False  # read-only download
        # Internal storage details never appear in the response
        for header_value in resp.headers.values():
            assert _report_download_row()["report_pdf_key"] not in header_value

    def test_guest_download_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Guests must not download reports (403, zero DB/storage access)."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[])
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn, mode="guest")
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.get(_report_download_url())

        assert resp.status_code == 403, resp.text
        assert conn.cursor_obj.executed == []
        assert storage.downloads == []

    def test_anonymous_download_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Requests without identity state are rejected with 401."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[])
        app, _module = _reports_app(monkeypatch, conn, mode="anonymous")

        with TestClient(app) as client:
            resp = client.get(_report_download_url())

        assert resp.status_code == 401, resp.text
        assert conn.cursor_obj.executed == []

    def test_nonexistent_report_opaque_404(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown report IDs return an opaque 404; storage never contacted."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[None])
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.get(_report_download_url())

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Report not found"
        assert len(conn.cursor_obj.executed) == 1  # only the report lookup
        assert storage.downloads == []  # storage never contacted

    def test_foreign_report_opaque_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Another user's report is indistinguishable from nonexistent."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[_report_download_row(owner="someone_else")])
        downloaded: list = []
        storage = _report_storage()
        storage.download_file = lambda key: downloaded.append(key) or b"x"
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.get(_report_download_url())

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Resource not found"
        assert len(conn.cursor_obj.executed) == 1
        assert downloaded == []  # storage never contacted

    def test_missing_pdf_in_r2_returns_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A report row whose PDF object is missing follows the established
        storage-error convention (500), without exposing the R2 key."""
        from fastapi.testclient import TestClient

        from crack_detection.backend.storage import StorageError

        conn = _SeqConn(fetchone_results=[_report_download_row()])
        storage = _report_storage()
        storage.download_file = lambda key: (_ for _ in ()).throw(
            StorageError("An error occurred (NoSuchKey) when calling the GetObject")
        )
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.get(_report_download_url())

        assert resp.status_code == 500, resp.text
        assert "Failed to retrieve report" in resp.json()["detail"]
        assert resp.headers.get("content-disposition") is None

    def test_r2_download_failure_returns_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """General R2 failures surface as 500 per established convention."""
        from fastapi.testclient import TestClient

        from crack_detection.backend.storage import StorageError

        conn = _SeqConn(fetchone_results=[_report_download_row()])
        storage = _report_storage()
        storage.download_file = lambda key: (_ for _ in ()).throw(
            StorageError("bucket unreachable")
        )
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.get(_report_download_url())

        assert resp.status_code == 500, resp.text
        assert "Failed to retrieve report" in resp.json()["detail"]

    def test_report_download_filename_uses_report_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The attachment filename is derived from the report ID."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[_report_download_row()])
        storage = _report_storage()
        storage.download_file = lambda key: b"%PDF-1.7"
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.get(_report_download_url())

        disposition = resp.headers["content-disposition"]
        assert disposition.startswith("attachment")
        assert _REPORT_DB_ID in disposition
        assert disposition.endswith('.pdf"')

    def test_report_download_after_parent_inspection_deleted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Once the inspection is deleted, the FK cascade removes the report
        rows, so a report download returns an opaque 404 (row not found)."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[None])  # report row gone via cascade
        storage = _report_storage()
        app, _module = _reports_app(monkeypatch, conn)
        app.dependency_overrides[_r2_storage_dep()] = lambda: storage

        with TestClient(app) as client:
            resp = client.get(_report_download_url())

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Report not found"
        assert storage.downloads == []


# ---------------------------------------------------------------------------
# Task 6 (Step 5): reports FK cascade migration + R2 PDF cleanup on
# inspection deletion
# ---------------------------------------------------------------------------

_DELETION_INSPECTION_ID = "22222222-3333-4333-8333-222222222222"
_DELETION_KEY_A = f"reports/33333333-3333-4333-8333-333333333333.pdf"
_DELETION_KEY_B = f"reports/44444444-4444-4334-8444-444444444444.pdf"


def _cleanup_storage():
    """Fake R2 storage recording report-PDF deletions and photograph-prefix
    deletions in a shared ordered event log (for ordering assertions)."""
    storage = SimpleNamespace()
    storage.deleted = []
    storage.prefix_deleted = []
    storage.events = []
    storage.fail_next = False

    def delete_file(key: str) -> None:
        storage.events.append(f"delete_file:{key}")
        storage.deleted.append(key)
        if storage.fail_next:
            storage.fail_next = False
            from crack_detection.backend.storage import StorageError
            raise StorageError("bucket unreachable")

    def delete_objects_by_prefix(prefix: str) -> int:
        storage.events.append(f"prefix:{prefix}")
        storage.prefix_deleted.append(prefix)
        return 0

    storage.delete_file = delete_file
    storage.delete_objects_by_prefix = delete_objects_by_prefix
    return storage


def _deletion_owner_row(owner: str = "clerk_user_123") -> dict:
    return {"user_id": owner}


def _deletion_app(monkeypatch: pytest.MonkeyPatch, conn, storage, user_id: str = "clerk_user_123"):
    """Reopen-style app for the real inspections router, with the R2
    storage dependency overridden by ``storage``."""
    app = _reopen_app(monkeypatch, conn, user_id=user_id)
    app.dependency_overrides[_r2_storage_dep()] = lambda: storage
    return app


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestReportsForeignKeyCascadeMigration:
    """Step 5: fk_reports_inspection must cascade on inspection deletion.

    Migration coverage is mocked (statements captured, not executed against
    PostgreSQL): this verifies the schema statements, not a live constraint.
    """

    def test_create_table_fk_declares_on_delete_cascade(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fresh databases create fk_reports_inspection with ON DELETE CASCADE."""
        from crack_detection.backend import database

        conn = _SeqConn()
        with patch.object(database, "get_db_connection", lambda: conn):
            database.init_schema()

        create_stmts = [
            sql for sql, _ in conn.cursor_obj.executed
            if "CREATE TABLE IF NOT EXISTS reports" in sql
        ]
        assert len(create_stmts) == 1
        assert "CONSTRAINT fk_reports_inspection" in create_stmts[0]
        assert (
            "FOREIGN KEY (inspection_id) REFERENCES inspections(id) ON DELETE CASCADE"
            in create_stmts[0]
        )

    def test_idempotent_constraint_swap_statement_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Existing deployments get the constraint swapped via a guarded,
        repeatable DO-block statement."""
        from crack_detection.backend import database

        conn = _SeqConn()
        with patch.object(database, "get_db_connection", lambda: conn):
            database.init_schema()

        do_stmts = [sql for sql, _ in conn.cursor_obj.executed if "DO $$" in sql]
        assert len(do_stmts) == 1
        stmt = do_stmts[0]
        # Guard: only fire when the constraint still lacks the cascade rule
        assert "information_schema.referential_constraints" in stmt
        assert "delete_rule <> 'CASCADE'" in stmt
        # Swap: drop the old constraint and re-add it with the cascade rule
        assert "ALTER TABLE reports DROP CONSTRAINT fk_reports_inspection" in stmt
        assert (
            "FOREIGN KEY (inspection_id) REFERENCES inspections(id)\n" in stmt
            and "ON DELETE CASCADE" in stmt
        )

    def test_migration_leaves_unrelated_fk_statements_alone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The schema statements do not rewrite other foreign keys."""
        from crack_detection.backend import database

        conn = _SeqConn()
        with patch.object(database, "get_db_connection", lambda: conn):
            database.init_schema()

        drop_stmts = [
            sql for sql, _ in conn.cursor_obj.executed
            if "DROP CONSTRAINT" in sql and "DO $$" not in sql
        ]
        assert drop_stmts == []  # only the guarded DO block may drop constraints
        # Other FKs keep their original definitions (spot checks)
        photo_stmt = next(
            sql
            for sql, _ in conn.cursor_obj.executed
            if "CREATE TABLE IF NOT EXISTS photographs" in sql
        )
        assert "fk_photographs_inspection" in photo_stmt
        assert "ON DELETE CASCADE" in photo_stmt  # unchanged, was already cascading


@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestInspectionDeletionWithReports:
    """Step 5: DELETE /inspections/{id} cleans up associated report PDFs.

    Storage access is mocked; no real R2 or PostgreSQL is contacted. The
    FK cascade itself is exercised by the migration statements; per-endpoint
    tests verify ordering, ownership, failure handling, and retries.
    """

    def test_delete_without_reports(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Inspections with no reports delete normally; no report PDFs touched."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[_deletion_owner_row()],
            fetchall_results=[],
        )
        storage = _cleanup_storage()
        app = _deletion_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.delete(f"/inspections/{_DELETION_INSPECTION_ID}")

        assert resp.status_code == 204, resp.text
        assert storage.deleted == []
        assert storage.prefix_deleted == [f"inspections/{_DELETION_INSPECTION_ID}/"]
        delete_sql = [
            sql for sql, _ in conn.cursor_obj.executed
            if "DELETE FROM inspections" in sql
        ]
        assert len(delete_sql) == 1
        assert conn.committed is True

    def test_delete_with_one_report(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The single associated report PDF is removed from R2 before the
        database rows are deleted."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[_deletion_owner_row()],
            fetchall_results=[{"report_pdf_key": _DELETION_KEY_A}],
        )
        storage = _cleanup_storage()
        app = _deletion_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.delete(f"/inspections/{_DELETION_INSPECTION_ID}")

        assert resp.status_code == 204, resp.text
        assert storage.deleted == [_DELETION_KEY_A]
        assert storage.prefix_deleted == [f"inspections/{_DELETION_INSPECTION_ID}/"]
        assert conn.committed is True

    def test_delete_with_multiple_reports(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every associated report PDF is removed."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[_deletion_owner_row()],
            fetchall_results=[
                {"report_pdf_key": _DELETION_KEY_A},
                {"report_pdf_key": _DELETION_KEY_B},
            ],
        )
        storage = _cleanup_storage()
        app = _deletion_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.delete(f"/inspections/{_DELETION_INSPECTION_ID}")

        assert resp.status_code == 204, resp.text
        assert storage.deleted == [_DELETION_KEY_A, _DELETION_KEY_B]
        assert conn.committed is True

    def test_report_keys_retrieved_before_inspection_delete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The report-key lookup runs first; the DELETE runs after R2
        cleanup (rows are removed by the FK cascade in the same transaction)."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[_deletion_owner_row()],
            fetchall_results=[{"report_pdf_key": _DELETION_KEY_A}],
        )
        storage = _cleanup_storage()
        app = _deletion_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.delete(f"/inspections/{_DELETION_INSPECTION_ID}")

        executed = [sql for sql, _ in conn.cursor_obj.executed]
        reports_select_idx = next(
            i for i, sql in enumerate(executed) if "FROM reports" in sql
        )
        delete_idx = next(
            i for i, sql in enumerate(executed) if "DELETE FROM inspections" in sql
        )
        assert reports_select_idx < delete_idx
        # R2 cleanup happened before the database DELETE executed: every
        # report-PDF deletion precedes the photograph-prefix cleanup event.
        assert storage.events[0].startswith("delete_file:")
        prefix_event_idx = storage.events.index(
            f"prefix:inspections/{_DELETION_INSPECTION_ID}/"
        )
        delete_file_idxs = [
            i for i, e in enumerate(storage.events) if e.startswith("delete_file:")
        ]
        assert all(i < prefix_event_idx for i in delete_file_idxs)
        # Report-row removal is delegated to the FK cascade: no explicit
        # "DELETE FROM reports" statement is executed.
        assert all("DELETE FROM reports" not in sql for sql in executed)

    def test_delete_failure_leaves_rows_for_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An R2 report-PDF deletion failure aborts BEFORE the database
        DELETE, so the committed reports rows retain their keys."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(
            fetchone_results=[_deletion_owner_row()],
            fetchall_results=[
                {"report_pdf_key": _DELETION_KEY_A},
                {"report_pdf_key": _DELETION_KEY_B},
            ],
        )
        storage = _cleanup_storage()
        storage.fail_next = True
        app = _deletion_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.delete(f"/inspections/{_DELETION_INSPECTION_ID}")

        assert resp.status_code == 500, resp.text
        assert (
            "Failed to delete associated report files" in resp.json()["detail"]
        )
        assert conn.committed is False
        # The inspection DELETE and photograph-prefix cleanup never ran
        assert all(
            "DELETE FROM inspections" not in sql
            for sql, _ in conn.cursor_obj.executed
        )
        assert storage.prefix_deleted == []

    def test_retry_after_failed_cleanup_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repeating the deletion after a cleanup failure is safe: the
        already-deleted PDF is a no-op re-delete, the remaining PDF is
        deleted, and the inspection rows are then removed."""
        from fastapi.testclient import TestClient

        storage = _cleanup_storage()
        storage.fail_next = True

        conn1 = _SeqConn(
            fetchone_results=[_deletion_owner_row()],
            fetchall_results=[
                {"report_pdf_key": _DELETION_KEY_A},
                {"report_pdf_key": _DELETION_KEY_B},
            ],
        )
        app1 = _deletion_app(monkeypatch, conn1, storage)
        with TestClient(app1) as client:
            resp1 = client.delete(f"/inspections/{_DELETION_INSPECTION_ID}")
        assert resp1.status_code == 500, resp1.text

        # Second attempt: same R2 bucket state, fresh connection
        storage.fail_next = False
        conn2 = _SeqConn(
            fetchone_results=[_deletion_owner_row()],
            fetchall_results=[
                {"report_pdf_key": _DELETION_KEY_A},
                {"report_pdf_key": _DELETION_KEY_B},
            ],
        )
        app2 = _deletion_app(monkeypatch, conn2, storage)
        with TestClient(app2) as client:
            resp2 = client.delete(f"/inspections/{_DELETION_INSPECTION_ID}")

        assert resp2.status_code == 204, resp2.text
        assert conn2.committed is True
        # Attempt 1 aborted at the first failing key (1 delete_file call);
        # attempt 2 re-deleted key A (a safe no-op on R2) and deleted key B.
        delete_file_events = [
            e for e in storage.events if e.startswith("delete_file:")
        ]
        assert len(delete_file_events) == 3

    def test_nonexistent_inspection_return_404(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deleting an unknown inspection is a 404 with no cleanup."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[None])
        storage = _cleanup_storage()
        app = _deletion_app(monkeypatch, conn, storage)

        with TestClient(app) as client:
            resp = client.delete(f"/inspections/{_DELETION_INSPECTION_ID}")

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Inspection not found"
        assert conn.committed is False
        assert storage.deleted == []
        assert storage.prefix_deleted == []

    def test_foreign_inspection_returns_404(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The existing opaque-404 ownership rule is unchanged (regression)."""
        from fastapi.testclient import TestClient

        conn = _SeqConn(fetchone_results=[_deletion_owner_row(owner="clerk_other_user")])
        storage = _cleanup_storage()
        app = _deletion_app(monkeypatch, conn, storage, user_id="clerk_user_123")

        with TestClient(app) as client:
            resp = client.delete(f"/inspections/{_DELETION_INSPECTION_ID}")

        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Resource not found"
        assert conn.committed is False
        assert storage.deleted == []
        assert storage.prefix_deleted == []
