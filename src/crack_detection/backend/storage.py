"""Cloudflare R2 object storage integration.

Wraps ``boto3`` S3-compatible client for R2. Provides upload, download,
and delete operations with the key structure defined in TECHNICAL_DESIGN.md.
"""

from __future__ import annotations

import logging
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from crack_detection.backend.config import get_settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when an object storage operation fails."""


class R2Storage:
    """Cloudflare R2 storage client."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
            config=Config(
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=10,
                read_timeout=30,
            ),
        )
        self._bucket = settings.r2_bucket_name

    def upload_file(self, key: str, data: bytes, content_type: str) -> str:
        """Upload bytes to R2 at the given key. Returns the object key."""
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            logger.debug("Uploaded object to R2: %s", key)
            return key
        except ClientError as exc:
            logger.error("R2 upload failed for key %s: %s", key, exc)
            raise StorageError(str(exc)) from exc

    def download_file(self, key: str) -> bytes:
        """Download object bytes from R2 at the given key."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            data = response["Body"].read()
            logger.debug("Downloaded object from R2: %s (%d bytes)", key, len(data))
            return data
        except ClientError as exc:
            logger.error("R2 download failed for key %s: %s", key, exc)
            raise StorageError(str(exc)) from exc

    def delete_file(self, key: str) -> None:
        """Delete object from R2 at the given key. Silently ignores missing objects."""
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
            logger.debug("Deleted object from R2: %s", key)
        except ClientError as exc:
            logger.warning("R2 delete failed for key %s: %s", key, exc)

    def file_exists(self, key: str) -> bool:
        """Return True if the object exists in R2."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def generate_key(self, prefix: str, filename: str) -> str:
        """Generate a namespaced R2 object key."""
        return f"{prefix}/{filename}"


def get_storage() -> R2Storage:
    """Return a configured R2Storage instance."""
    return R2Storage()
