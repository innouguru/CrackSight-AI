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
        # ``probability_map_key`` is intentionally not populated by the analysis
        # pipeline (probability maps are not stored as standalone objects), so
        # the column must allow NULL. The analysis endpoint inserts NULL for it.
        # ``ALTER COLUMN ... DROP NOT NULL`` is idempotent and safe to repeat
        # on an already-nullable column; it never drops data or recreates the
        # table.
        """
        ALTER TABLE prediction_versions ALTER COLUMN probability_map_key DROP NOT NULL;
        """,
        """
        CREATE TABLE IF NOT EXISTS reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            inspection_id UUID NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            report_pdf_key VARCHAR(512) NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            page_count INTEGER,
            CONSTRAINT fk_reports_inspection FOREIGN KEY (inspection_id) REFERENCES inspections(id) ON DELETE CASCADE,
            CONSTRAINT fk_reports_user FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """,
        # ``reports.inspection_id`` must cascade on inspection deletion so the
        # bare ``DELETE FROM inspections`` used by ``delete_inspection``
        # succeeds once report rows exist. Fresh databases get the cascade
        # from the CREATE TABLE above; pre-existing deployments still hold the
        # original constraint (CREATE TABLE IF NOT EXISTS never alters an
        # existing table). The guard below swaps the constraint only when it
        # exists with a non-CASCADE delete rule, making the migration
        # idempotent and repeatable on both fresh and existing databases
        # without recreating tables or touching any rows.
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM information_schema.referential_constraints
            WHERE constraint_name = 'fk_reports_inspection'
              AND delete_rule <> 'CASCADE'
          ) THEN
            ALTER TABLE reports DROP CONSTRAINT fk_reports_inspection;
            ALTER TABLE reports ADD CONSTRAINT fk_reports_inspection
              FOREIGN KEY (inspection_id) REFERENCES inspections(id)
              ON DELETE CASCADE;
          END IF;
        END $$;
        """,
        """
        CREATE TABLE IF NOT EXISTS user_usage (
            user_id VARCHAR(255) NOT NULL,
            month_key VARCHAR(7) NOT NULL,
            analyses_count INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, month_key),
            CONSTRAINT fk_user_usage_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_user_usage_user_id ON user_usage(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_usage_month_key ON user_usage(month_key);
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


def decrement_guest_analysis_count(session_id: str) -> Optional[int]:
    """Atomically decrement the guest session analysis count.

    Used to compensate (refund) an allowance reservation when a reserved
    analysis fails before successful persistence. Only decrements when the
    count is greater than zero, so it can never go negative.

    Returns the new count if the decrement succeeded, or ``None`` if the
    count was already zero.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE guest_sessions
                SET analyses_count = analyses_count - 1
                WHERE id = %s
                  AND analyses_count > 0
                RETURNING analyses_count
                """,
                (session_id,),
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


# ------------------------------------------------------------------
# Registered-user monthly usage allowance
# ------------------------------------------------------------------

def _current_month_key(now: Optional[datetime] = None) -> str:
    """Return the YYYY-MM calendar month key for the given (or current UTC) time."""
    if now is None:
        now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def increment_user_analysis_count(
    user_id: str,
    max_analyses: int = 100,
    month_key: Optional[str] = None,
) -> Optional[int]:
    """Atomically reserve one registered-user monthly analysis allowance.

    Uses an atomic conditional UPSERT so that:
    - The first analysis in a month creates the row (count = 1).
    - Subsequent analyses increment the existing row.
    - Concurrent requests cannot exceed the limit (the conditional UPDATE
      guards against races).
    - If the limit has already been reached, returns ``None`` (no row
      created or modified).

    Returns the new count if the reservation succeeded, or ``None`` if the
    user has already reached the monthly allowance.
    """
    if month_key is None:
        month_key = _current_month_key()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_usage (user_id, month_key, analyses_count)
                VALUES (%s, %s, 1)
                ON CONFLICT (user_id, month_key)
                DO UPDATE
                SET analyses_count = user_usage.analyses_count + 1,
                    updated_at = NOW()
                WHERE user_usage.analyses_count < %s
                RETURNING analyses_count
                """,
                (user_id, month_key, max_analyses),
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        return None
    return row[0]


def decrement_user_analysis_count(
    user_id: str,
    month_key: Optional[str] = None,
) -> Optional[int]:
    """Compensate (refund) a reserved monthly allowance for a failed analysis.

    Only decrements when the count is greater than zero, so it can never go
    negative. Used when a reserved analysis fails before successful
    persistence (inference failure, R2 upload failure, or DB persistence
    failure).

    Returns the new count if the decrement succeeded, or ``None`` if the
    count was already zero or the row does not exist.
    """
    if month_key is None:
        month_key = _current_month_key()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE user_usage
                SET analyses_count = analyses_count - 1,
                    updated_at = NOW()
                WHERE user_id = %s
                  AND month_key = %s
                  AND analyses_count > 0
                RETURNING analyses_count
                """,
                (user_id, month_key),
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        return None
    return row[0]


def get_user_monthly_usage(
    user_id: str,
    month_key: Optional[str] = None,
) -> int:
    """Return the current monthly analysis count for the user (0 if absent)."""
    if month_key is None:
        month_key = _current_month_key()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT analyses_count FROM user_usage WHERE user_id = %s AND month_key = %s",
                (user_id, month_key),
            )
            row = cur.fetchone()

    if row is None:
        return 0
    return row[0]


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


def ensure_registered_user(user_id: str, email: Optional[str] = None) -> bool:
    """Ensure a local ``users`` record exists for an authenticated Clerk user.

    Uses an idempotent upsert (``INSERT ... ON CONFLICT (id) DO NOTHING``) so
    that concurrent requests cannot create duplicate rows and existing records
    are never overwritten. The Clerk user id (``sub``) is preserved as the
    local primary key; the verified email is stored when available.

    Returns ``True`` if the user is present locally after the call, ``False`` if
    the user could not be synchronised (for example, a missing Clerk user id or
    no usable email claim for the NOT NULL ``email`` column). No invalid user
    record is ever created.

    When no email claim is available, an existing local record is *confirmed*
    with a read-only ``SELECT`` (no invented email is stored and nothing is
    written); a user with no email claim and no local record fails closed.
    """
    if not user_id:
        logger.warning("Cannot synchronise user: missing Clerk user id")
        return False

    with get_db_connection() as conn:
        if email is None:
            # No usable email claim. An email can never be invented client-side
            # (the ``users.email`` column is NOT NULL and must hold a verified
            # value), so the only safe path is confirming that a local record
            # for this verified Clerk id already exists. Read-only: no write.
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
            if row is None:
                logger.warning(
                    "Cannot synchronise user %s: no usable email claim and "
                    "no existing local record",
                    user_id,
                )
                return False
            return True

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, email, role)
                VALUES (%s, %s, 'registered')
                ON CONFLICT (id) DO NOTHING
                """,
                (user_id, email),
            )
        conn.commit()
    return True
