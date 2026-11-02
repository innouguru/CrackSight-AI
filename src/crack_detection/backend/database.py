"""Neon PostgreSQL database connection and schema initialization.

Uses ``psycopg2`` directly (no ORM, per project decision). Provides a
context-managed connection helper and idempotent schema creation for all
application entities.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Generator, Optional

import psycopg2
import psycopg2.extras

from crack_detection.backend.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()


class DatabaseError(Exception):
    """Raised when a database operation fails."""


@contextlib.contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a PostgreSQL connection, rolling back on exception and closing after use."""
    conn: Optional[psycopg2.extensions.connection] = None
    try:
        conn = psycopg2.connect(_settings.database_url)
        yield conn
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        logger.error("Database operation failed: %s", exc)
        raise DatabaseError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def init_schema() -> None:
    """Create all application tables if they do not already exist.

    Idempotent — safe to run on every application startup.
    """
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(255) PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            role VARCHAR(32) NOT NULL DEFAULT 'registered',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS inspections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(255) NOT NULL,
            title VARCHAR(255) NOT NULL,
            building_type VARCHAR(128),
            building_location VARCHAR(255),
            notes TEXT,
            status VARCHAR(32) NOT NULL DEFAULT 'draft',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            CONSTRAINT fk_inspections_user FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS photographs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            inspection_id UUID NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            structure_type VARCHAR(32) NOT NULL CHECK (structure_type IN ('wall', 'beam', 'column')),
            observation TEXT,
            verification_status VARCHAR(32) NOT NULL DEFAULT 'not_verified',
            original_image_key VARCHAR(512) NOT NULL,
            prediction_mask_key VARCHAR(512),
            prediction_overlay_key VARCHAR(512),
            model_version VARCHAR(128),
            prediction_timestamp TIMESTAMPTZ,
            pixel_measurements JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_photographs_inspection FOREIGN KEY (inspection_id) REFERENCES inspections(id) ON DELETE CASCADE,
            CONSTRAINT fk_photographs_user FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS prediction_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            photograph_id UUID NOT NULL,
            version_number INTEGER NOT NULL,
            original_image_key VARCHAR(512) NOT NULL,
            probability_map_key VARCHAR(512) NOT NULL,
            binary_mask_key VARCHAR(512) NOT NULL,
            overlay_key VARCHAR(512) NOT NULL,
            model_version VARCHAR(128) NOT NULL,
            prediction_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            pixel_measurements JSONB,
            CONSTRAINT fk_prediction_versions_photograph FOREIGN KEY (photograph_id) REFERENCES photographs(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            inspection_id UUID NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            report_pdf_key VARCHAR(512) NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            page_count INTEGER,
            CONSTRAINT fk_reports_inspection FOREIGN KEY (inspection_id) REFERENCES inspections(id),
            CONSTRAINT fk_reports_user FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_inspections_user_id ON inspections(user_id);
        CREATE INDEX IF NOT EXISTS idx_inspections_status ON inspections(status);
        CREATE INDEX IF NOT EXISTS idx_photographs_inspection_id ON photographs(inspection_id);
        CREATE INDEX IF NOT EXISTS idx_photographs_user_id ON photographs(user_id);
        CREATE INDEX IF NOT EXISTS idx_prediction_versions_photograph_id ON prediction_versions(photograph_id);
        CREATE INDEX IF NOT EXISTS idx_reports_inspection_id ON reports(inspection_id);
        """,
    ]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()
    logger.info("Database schema initialized successfully")
