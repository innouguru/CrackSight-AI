"""Application configuration.

Loads all configuration from environment variables via ``pydantic-settings``.
Never hardcode secrets or credentials. All values come from the environment
(or a ``.env`` file for local development).
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration, all values sourced from environment."""

    # ------------------------------------------------------------------ app
    app_name: str = "CrackSight AI"
    app_env: str = Field("development", validation_alias="APP_ENV")
    debug: bool = Field(False, validation_alias="DEBUG")
    backend_host: str = Field("0.0.0.0", validation_alias="BACKEND_HOST")
    backend_port: int = Field(8000, validation_alias="BACKEND_PORT")

    # ------------------------------------------------------------------ security
    secret_key: str = Field(..., validation_alias="SECRET_KEY")

    # ------------------------------------------------------------------ authentication — Clerk
    clerk_publishable_key: str = Field(..., validation_alias="CLERK_PUBLISHABLE_KEY")
    clerk_secret_key: str = Field(..., validation_alias="CLERK_SECRET_KEY")
    clerk_jwt_issuer: str = Field(..., validation_alias="CLERK_JWT_ISSUER")
    clerk_jwks_url: Optional[str] = Field(
        None, validation_alias="CLERK_JWKS_URL"
    )

    # ------------------------------------------------------------------ database — Neon PostgreSQL
    database_url: str = Field(..., validation_alias="DATABASE_URL")

    # ------------------------------------------------------------------ object storage — Cloudflare R2
    r2_account_id: str = Field(..., validation_alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(..., validation_alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(..., validation_alias="R2_SECRET_ACCESS_KEY")
    r2_bucket_name: str = Field(..., validation_alias="R2_BUCKET_NAME")
    r2_endpoint: str = Field(..., validation_alias="R2_ENDPOINT")

    # ------------------------------------------------------------------ inference service
    inference_service_url: str = Field(
        "http://localhost:8001", validation_alias="INFERENCE_SERVICE_URL"
    )
    inference_service_timeout: int = Field(
        30, validation_alias="INFERENCE_SERVICE_TIMEOUT"
    )
    inference_checkpoint_path: str = Field(
        "model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth",
        validation_alias="INFERENCE_CHECKPOINT_PATH",
    )
    inference_image_size: str = Field("256,256", validation_alias="INFERENCE_IMAGE_SIZE")
    inference_threshold: float = Field(0.5, validation_alias="INFERENCE_THRESHOLD")
    inference_device: str = Field("cpu", validation_alias="INFERENCE_DEVICE")

    # ------------------------------------------------------------------ file upload limits
    max_upload_size_bytes: int = Field(
        10485760, validation_alias="MAX_UPLOAD_SIZE_BYTES"
    )
    max_image_dimension: int = Field(4096, validation_alias="MAX_IMAGE_DIMENSION")
    allowed_image_extensions: str = Field(
        "jpg,jpeg,png,webp", validation_alias="ALLOWED_IMAGE_EXTENSIONS"
    )

    # ------------------------------------------------------------------ guest session limits
    guest_max_analyses_per_session: int = Field(
        3, validation_alias="GUEST_MAX_ANALYSES_PER_SESSION"
    )
    guest_session_expiration_hours: int = Field(
        24, validation_alias="GUEST_SESSION_EXPIRATION_HOURS"
    )
    registered_unsaved_expiration_hours: int = Field(
        24, validation_alias="REGISTERED_UNSAVED_EXPIRATION_HOURS"
    )

    # ------------------------------------------------------------------ registered user monthly allowance
    registered_monthly_analyses_limit: int = Field(
        100, validation_alias="REGISTERED_MONTHLY_ANALYSES_LIMIT"
    )

    @field_validator("inference_image_size")
    @classmethod
    def _validate_image_size(cls, value: str) -> str:
        parts = value.split(",")
        if len(parts) != 2:
            raise ValueError("INFERENCE_IMAGE_SIZE must be 'height,width'")
        try:
            h, w = int(parts[0]), int(parts[1])
        except ValueError as exc:
            raise ValueError("INFERENCE_IMAGE_SIZE values must be integers") from exc
        if h <= 0 or w <= 0:
            raise ValueError("INFERENCE_IMAGE_SIZE values must be positive")
        return value

    @field_validator("allowed_image_extensions")
    @classmethod
    def _validate_extensions(cls, value: str) -> str:
        allowed = {"jpg", "jpeg", "png", "webp"}
        for ext in value.split(","):
            ext = ext.strip().lower()
            if ext not in allowed:
                raise ValueError(
                    f"Extension '{ext}' not allowed. Allowed: {sorted(allowed)}"
                )
        return value

    @field_validator("clerk_jwks_url", mode="after")
    @classmethod
    def _derive_jwks_url(cls, value: Optional[str], info) -> Optional[str]:
        """Derive JWKS URL from issuer if not explicitly set."""
        if value is not None:
            return value
        issuer = info.data.get("clerk_jwt_issuer")
        if issuer and "CHANGE_ME" not in issuer:
            return f"{issuer}/.well-known/jwks.json"
        return value

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
