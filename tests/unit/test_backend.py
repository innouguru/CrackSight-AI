"""Tests for the CrackSight AI backend foundation.

These tests exercise configuration validation, exception handling,
schema validation, middleware logic, and API endpoints. They require
the backend dependencies (fastapi, pydantic-settings, psycopg2,
boto3, etc.) to be installed before they can run.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
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


# ---------------------------------------------------------------------------
# Guest session tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BACKEND_AVAILABLE, reason="backend dependencies not installed")
class TestGuestSession:
    """Tests for guest session creation, validation, and limits."""

    def test_create_guest_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Creating a guest session returns a valid token and session data."""
        from crack_detection.backend import database
        from unittest.mock import patch

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

        expected_session = {
            "id": "test-session-id",
            "session_token": "test-token-123",
            "created_at": "2026-01-01T00:00:00+00:00",
            "expires_at": "2026-01-02T00:00:00+00:00",
            "analyses_count": 0,
            "is_active": True,
        }

        with patch.object(
            database, "create_guest_session", return_value=expected_session
        ):
            session = database.create_guest_session(expiration_hours=24)

        assert session["session_token"] == "test-token-123"
        assert session["analyses_count"] == 0
        assert session["is_active"] is True

    def test_validate_guest_session_valid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A valid, non-expired guest session is validated."""
        from crack_detection.backend import database
        from unittest.mock import patch

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

        expected_session = {
            "id": "test-session-id",
            "session_token": "valid-token",
            "created_at": "2026-01-01T00:00:00+00:00",
            "expires_at": "2026-01-02T00:00:00+00:00",
            "analyses_count": 1,
            "is_active": True,
        }

        with patch.object(
            database, "validate_guest_session", return_value=expected_session
        ):
            session = database.validate_guest_session("valid-token")

        assert session is not None
        assert session["analyses_count"] == 1
        assert session["is_active"] is True

    def test_validate_guest_session_expired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An expired guest session is rejected."""
        from crack_detection.backend import database
        from unittest.mock import patch

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

        with patch.object(
            database, "validate_guest_session", return_value=None
        ):
            session = database.validate_guest_session("expired-token")

        assert session is None

    def test_increment_analysis_count_atomic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Incrementing analysis count works and returns the new count."""
        from crack_detection.backend import database
        from unittest.mock import patch

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

        with patch.object(
            database,
            "increment_guest_analysis_count",
            return_value=1,
        ):
            result = database.increment_guest_analysis_count(
                "session-id", max_analyses=3
            )

        assert result == 1

    def test_increment_analysis_count_at_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Incrementing beyond the limit returns None."""
        from crack_detection.backend import database
        from unittest.mock import patch

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

        with patch.object(
            database,
            "increment_guest_analysis_count",
            return_value=None,
        ):
            result = database.increment_guest_analysis_count(
                "session-id", max_analyses=3
            )

        assert result is None


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