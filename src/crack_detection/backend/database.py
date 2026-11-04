"""Neon PostgreSQL database connection and schema initialization.

Uses ``psycopg2`` directly (no ORM, per project decision). Provides a
context-managed connection helper and idempotent schema creation for all
application entities.
"""

from __future__ import annotations

import contextlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Generator, Optional

import psycopg2
import psycopg2.extras

from crack_detection.backend.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised when a database operation fails."""


@contextlib.contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a PostgreSQL connection, rolling back on exception and closing after use."""
    settings = get_settings()
    conn: Optional[psycopg2.extensions.connection] = None
    try:
        conn = psycopg2.connect(settings.database_url)
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
            idempotency_key UUID UNIQUE,
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
        CREATE TABLE IF NOT EXISTS guest_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_token VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            analyses_count INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_inspections_user_id ON inspections(user_id);
        CREATE INDEX IF NOT EXISTS idx_inspections_status ON inspections(status);
        CREATE INDEX IF NOT EXISTS idx_photographs_inspection_id ON photographs(inspection_id);
        CREATE INDEX IF NOT EXISTS idx_photographs_user_id ON photographs(user_id);
        CREATE INDEX IF NOT EXISTS idx_prediction_versions_photograph_id ON prediction_versions(photograph_id);
        CREATE INDEX IF NOT EXISTS idx_reports_inspection_id ON reports(inspection_id);
        CREATE INDEX IF NOT EXISTS idx_guest_sessions_token ON guest_sessions(session_token);
        CREATE INDEX IF NOT EXISTS idx_guest_sessions_expires_at ON guest_sessions(expires_at);
        """,
    ]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()
    logger.info("Database schema initialized successfully")


# ------------------------------------------------------------------
# Guest session helpers
# ------------------------------------------------------------------

def create_guest_session(
    expiration_hours: int = 24,
) -> dict:
    """Create a new guest session with an unpredictable token.

    Returns a dict with ``id``, ``session_token``, ``created_at``,
    ``expires_at``, ``analyses_count``, and ``is_active``.
    """
    settings = get_settings()
    hours = expiration_hours or settings.guest_session_expiration_hours
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO guest_sessions (
                    session_token, expires_at, analyses_count, is_active
                )
                VALUES (%s, %s, 0, TRUE)
                RETURNING id, session_token, created_at, expires_at,
                          analyses_count, is_active
                """,
                (session_token, expires_at),
            )
            row = cur.fetchone()
            conn.commit()
    return dict(row)


def validate_guest_session(session_token: str) -> Optional[dict]:
    """Validate a guest session token.

    Returns the session dict if valid and active and not expired,
    otherwise ``None``. Deactivates expired sessions as a side effect.
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, session_token, created_at, expires_at,
                       analyses_count, is_active
                FROM guest_sessions
                WHERE session_token = %s AND is_active = TRUE
                """,
                (session_token,),
            )
            row = cur.fetchone()

    if not row:
        return None

    now = datetime.now(timezone.utc)
    expires_at = row["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        # Deactivate the expired session.
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE guest_sessions SET is_active = FALSE WHERE id = %s",
                    (row["id"],),
                )
                conn.commit()
        return None

    return dict(row)


def increment_guest_analysis_count(
    session_id: str,
    max_analyses: int = 3,
) -> Optional[int]:
    """Atomically increment the guest session analysis count.

    Returns the new count if the increment succeeded, or ``None`` if the
    session has already reached the limit. Uses an atomic conditional
    UPDATE so concurrent requests cannot exceed the allowance.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE guest_sessions
                SET analyses_count = analyses_count + 1
                WHERE id = %s
                  AND is_active = TRUE
                  AND analyses_count < %s
                  AND expires_at > NOW()
                RETURNING analyses_count
                """,
                (session_id, max_analyses),
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        return None
    return row[0]


def deactivate_guest_session(session_id: str) -> None:
    """Mark a guest session as inactive."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE guest_sessions SET is_active = FALSE WHERE id = %s",
                (session_id,),
            )
            conn.commit()


def cleanup_expired_guest_sessions() -> int:
    """Deactivate all expired guest sessions. Returns the count deactivated."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE guest_sessions
                SET is_active = FALSE
                WHERE is_active = TRUE AND expires_at <= NOW()
                RETURNING id
                """
            )
            rows = cur.fetchall()
            conn.commit()
    return len(rows)
