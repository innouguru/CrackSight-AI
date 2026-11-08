"""Pydantic request/response schemas for the CrackSight AI backend.

Defines consistent API contract models for inspections, photographs,
authentication, and error responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ------------------------------------------------------------------ base
class BaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ health
class HealthResponse(BaseModel):
    status: str = Field("ok")
    service: str = "CrackSight AI"
    version: str = "0.1.0"


# ------------------------------------------------------------------ authentication
class SignInUrlResponse(BaseModel):
    sign_in_url: str


class TokenVerifyResponse(BaseModel):
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None


class ErrorDetail(BaseModel):
    """Structured error detail returned by API error responses.

    Mirrors the body produced by ``exceptions._error_response`` so that the
    error schema is explicit and reusable across the API contract.
    """

    error: str
    message: str
    retryable: bool
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------ inspections
class StructureType(str):
    WALL = "wall"
    BEAM = "beam"
    COLUMN = "column"


class InspectionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    building_type: Optional[str] = Field(None, max_length=128)
    building_location: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class InspectionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    building_type: Optional[str] = Field(None, max_length=128)
    building_location: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|completed)$")


class InspectionResponse(BaseModel):
    id: UUID
    user_id: str
    title: str
    building_type: Optional[str]
    building_location: Optional[str]
    notes: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    photograph_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class InspectionListResponse(BaseModel):
    inspections: List[InspectionResponse]
    total: int


# ------------------------------------------------------------------ photographs
class PhotographCreate(BaseModel):
    structure_type: str = Field(..., pattern="^(wall|beam|column)$")
    original_image_key: str = Field(..., min_length=1)
    observation: Optional[str] = None


class PhotographUpdate(BaseModel):
    structure_type: Optional[str] = Field(None, pattern="^(wall|beam|column)$")
    observation: Optional[str] = None
    verification_status: Optional[str] = Field(
        None, pattern="^(correct|incorrect|partial|not_verified)$"
    )


class PhotographResponse(BaseModel):
    id: UUID
    inspection_id: UUID
    user_id: str
    structure_type: str
    observation: Optional[str]
    verification_status: str
    original_image_key: str
    prediction_mask_key: Optional[str]
    prediction_overlay_key: Optional[str]
    model_version: Optional[str]
    prediction_timestamp: Optional[datetime]
    pixel_measurements: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ reanalysis
class PhotographMetadataResponse(BaseModel):
    """Owner-facing photograph entry for inspection photo listings.

    Deliberately excludes internal R2 object keys (``original_image_key``,
    ``prediction_mask_key``, ``prediction_overlay_key``) and any other
    private storage details; image retrieval is handled separately by
    owner-only download endpoints. Persisted prediction metadata is
    returned as-is: NULL fields stay ``null`` — values are never fabricated.
    """

    id: UUID
    inspection_id: UUID
    structure_type: str
    observation: Optional[str]
    verification_status: str
    model_version: Optional[str]
    prediction_timestamp: Optional[datetime]
    pixel_measurements: Optional[Dict[str, Any]]
    created_at: datetime
    prediction_available: bool


class PhotographListResponse(BaseModel):
    """All photographs belonging to one owned inspection (oldest first)."""

    inspection_id: UUID
    photographs: List[PhotographMetadataResponse]
    total: int


class ReanalyseResponse(BaseModel):
    photograph_id: UUID
    version_number: int
    model_version: str
    prediction_timestamp: datetime
    previous_predictions_preserved: bool = True


# ------------------------------------------------------------------ reports
class ReportGenerateResponse(BaseModel):
    report_id: UUID
    generated_at: datetime
    download_url: str


# ------------------------------------------------------------------ analysis
class AnalysisResponse(BaseModel):
    photograph_id: UUID
    prediction_mask_key: str
    prediction_overlay_key: str
    original_image_key: str
    model_version: str
    prediction_timestamp: datetime
    inference_duration_ms: float
    processing_status: str
    original_image_size: tuple[int, int]
    pixel_measurements: Optional[PixelMeasurements] = None
    analyses_remaining: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AnalysisStatusResponse(BaseModel):
    status: str = "analysis_queued"  # or "completed", "failed", "rate_limited"
    message: str
    photograph_id: UUID
    error: str
    message: str
    retryable: bool
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------ guest sessions
class GuestSessionCreateResponse(BaseModel):
    session_token: str
    session_id: UUID
    expires_at: datetime
    max_analyses: int = 3
    analyses_count: int = 0


class GuestSessionValidateResponse(BaseModel):
    valid: bool
    session_id: Optional[UUID] = None
    analyses_count: int = 0
    max_analyses: int = 3
    analyses_remaining: int = 3
    expires_at: Optional[datetime] = None


class GuestAnalysisConsumeResponse(BaseModel):
    consumed: bool
    analyses_count: int
    max_analyses: int
    analyses_remaining: int


# ------------------------------------------------------------------ guest photograph upload
class GuestPhotographUploadResponse(BaseModel):
    photograph_id: UUID
    session_id: UUID
    structure_type: str
    original_image_key: str
    file_size: int
    content_type: str
    analyses_remaining: int


class GuestPhotographDownloadResponse(BaseModel):
    photograph_id: UUID
    file_type: str
    download_url: str
    content_type: str


# ------------------------------------------------------------------ pixel measurements
class PixelMeasurements(BaseModel):
    crack_pixel_count: int
    crack_pixel_percentage: float
    bounding_box: Optional[Dict[str, int]] = None
    region_count: int = 0
