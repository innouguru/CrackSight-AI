"""Integration tests for database operations using local PostgreSQL.

These tests verify actual database interactions including schema creation,
CRUD operations, foreign key constraints, transactions, and guest session
lifecycle management.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Conditional imports -- tests skip gracefully if DB not available
# ---------------------------------------------------------------------------
try:
    import crack_detection.backend.database as db_module
    from crack_detection.backend.database import (
        cleanup_expired_guest_sessions,
        create_guest_session,
        increment_guest_analysis_count,
        init_schema,
        validate_guest_session,
    )
    from crack_detection.backend.dependencies import get_db

    _DB_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Connection fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def set_env_vars() -> None:
    """Set required environment variables for tests.

    Assignments (not setdefault) are deliberate: when the whole ``tests/unit``
    folder runs, ``test_backend.py`` leaves a throwaway ``DATABASE_URL`` behind
    in ``os.environ``, which would otherwise win over the dedicated test
    database this suite requires. ``get_settings`` is ``lru_cache``d, so the
    cache is cleared to force a re-read of the corrected environment.
    """
    os.environ["SECRET_KEY"] = "test-secret-key-12345"
    os.environ["CLERK_PUBLISHABLE_KEY"] = "pk_test_123"
    os.environ["CLERK_SECRET_KEY"] = "sk_test_123"
    os.environ["CLERK_JWT_ISSUER"] = "https://test.clerk.accounts.com"
    os.environ["CLERK_JWKS_URL"] = "https://test.clerk.accounts.com/.well-known/jwks.json"
    os.environ["DATABASE_URL"] = "postgresql://postgres@localhost:5432/xportra_test?sslmode=disable"
    os.environ["R2_ACCOUNT_ID"] = "test-account"
    os.environ["R2_ACCESS_KEY_ID"] = "test-key"
    os.environ["R2_SECRET_ACCESS_KEY"] = "test-secret"
    os.environ["R2_BUCKET_NAME"] = "test-bucket"
    os.environ["R2_ENDPOINT"] = "https://test.r2.cloudflarestorage.com"
    if _DB_AVAILABLE:
        from crack_detection.backend.config import get_settings

        get_settings.cache_clear()


@pytest.fixture(scope="session")
def db_conn():
    """Create a PostgreSQL connection to the test database."""
    conn = psycopg2.connect("postgresql://postgres@localhost:5432/xportra_test?sslmode=disable")
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def rollback_db_transaction(db_conn):
    """Guarantee a clean transaction lifecycle around every test.

    The session-scoped connection runs with autocommit disabled, so a
    test's statements open a transaction that otherwise outlives the test
    (idle in transaction): row locks are retained indefinitely, failed
    assertions leave aborted transactions on the shared connection, and
    later ``init_schema`` calls wait forever for DDL locks held against
    those lingering transactions (the historical suite hang). Rolling back
    before and after every test releases the locks and discards the test's
    uncommitted rows without destroying committed application data.
    """
    db_conn.rollback()  # discard leftovers from any previous test/failure
    yield
    db_conn.rollback()  # release locks; do not persist this test's rows


def _delete_test_guest_session(session_id: str) -> None:
    """Targeted cleanup for guest sessions created by a test.

    Guest-session helpers commit on their own connections, so the rollback
    of the shared fixture connection cannot remove their rows. This deletes
    exactly the row created by the test (and nothing else), keeping runs
    idempotent without broad cleanup statements.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM guest_sessions WHERE id = %s", (session_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema initialization tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _DB_AVAILABLE, reason="backend dependencies not installed")
class TestDatabaseSchema:
    """Tests for database schema initialization."""

    def test_init_schema_creates_tables(self, db_conn) -> None:
        """Init schema creates all expected tables."""
        init_schema()

        cur = db_conn.cursor()
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
            """
        )
        tables = {row[0] for row in cur.fetchall()}
        cur.close()

        expected_tables = {
            "users",
            "inspections",
            "photographs",
            "prediction_versions",
            "reports",
            "guest_sessions",
        }
        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    def test_init_schema_idempotent(self, db_conn) -> None:
        """Running init_schema twice should not error."""
        init_schema()
        init_schema()  # Should not raise


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _DB_AVAILABLE, reason="backend dependencies not installed")
class TestDatabaseCRUD:
    """Tests for database CRUD operations."""

    def test_create_and_read_inspection(self, db_conn) -> None:
        """Create an inspection and read it back."""
        init_schema()

        cur = db_conn.cursor()

        # Create a user first (unique ids so reruns cannot collide with
        # committed rows from earlier executions).
        cur.execute(
            "INSERT INTO users (id, email, role) VALUES (%s, %s, %s) RETURNING id",
            (f"user-{uuid4()}", f"{uuid4()}@example.com", "registered"),
        )
        user_id = cur.fetchone()[0]

        # Create inspection
        cur.execute(
            """
            INSERT INTO inspections (id, user_id, title, building_type, status)
            VALUES (%s, %s, %s, %s, 'draft')
            RETURNING id, title, status
            """,
            (str(uuid4()), user_id, "Test Inspection", "residential"),
        )
        row = cur.fetchone()
        assert row[1] == "Test Inspection"
        assert row[2] == "draft"

        # Read it back
        cur.execute("SELECT title, status FROM inspections WHERE id = %s", (row[0],))
        fetched = cur.fetchone()
        assert fetched[0] == "Test Inspection"
        assert fetched[1] == "draft"

        cur.close()

    def test_create_photograph(self, db_conn) -> None:
        """Create a photograph linked to an inspection."""
        init_schema()

        cur = db_conn.cursor()

        cur.execute(
            "INSERT INTO users (id, email) VALUES (%s, %s) RETURNING id",
            (f"user-{uuid4()}", f"{uuid4()}@example.com"),
        )
        user_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO inspections (id, user_id, title) VALUES (%s, %s, %s) RETURNING id",
            (str(uuid4()), user_id, "Test Inspection"),
        )
        inspection_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO photographs (
                id, inspection_id, user_id, structure_type,
                original_image_key, verification_status
            )
            VALUES (%s, %s, %s, %s, %s, 'not_verified')
            RETURNING id, structure_type
            """,
            (str(uuid4()), inspection_id, user_id, "wall", "inspections/test/photo.jpg"),
        )
        row = cur.fetchone()
        assert row[1] == "wall"

        cur.close()

    def test_foreign_key_constraint(self, db_conn) -> None:
        """Inserting a photograph for a nonexistent inspection raises the
        real PostgreSQL foreign-key constraint violation (SQLSTATE 23503)."""
        init_schema()

        cur = db_conn.cursor()

        # A genuinely existing user so the only constraint that can fail is
        # fk_photographs_inspection (the created user is rolled back by the
        # isolation fixture afterwards).
        user_id = f"user-{uuid4()}"
        cur.execute(
            "INSERT INTO users (id, email) VALUES (%s, %s)",
            (user_id, f"{uuid4()}@example.com"),
        )
        photograph_id = str(uuid4())
        nonexistent_inspection_id = str(uuid4())

        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cur.execute(
                """
                INSERT INTO photographs (
                    id, inspection_id, user_id, structure_type,
                    original_image_key
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    photograph_id,
                    nonexistent_inspection_id,
                    user_id,
                    "wall",
                    "inspections/test.jpg",
                ),
            )

        # A failed statement aborts the current PostgreSQL transaction; the
        # rollback clears that state so the connection stays usable and no
        # partial data persists.
        db_conn.rollback()

        cur.execute("SELECT COUNT(*) FROM photographs WHERE id = %s", (photograph_id,))
        assert cur.fetchone()[0] == 0
        cur.close()


# ---------------------------------------------------------------------------
# Guest session tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _DB_AVAILABLE, reason="backend dependencies not installed")
class TestGuestSession:
    """Tests for guest session creation, validation, and limits."""

    def test_create_and_validate_guest_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Creating and validating a guest session."""
        init_schema()

        session = create_guest_session(expiration_hours=24)
        try:
            assert session["session_token"] is not None
            assert session["analyses_count"] == 0
            assert session["is_active"] is True

            validated = validate_guest_session(session["session_token"])
            assert validated is not None
            assert validated["session_token"] == session["session_token"]
        finally:
            _delete_test_guest_session(session["id"])

    def test_validate_guest_session_expiration(
        self, monkeypatch: pytest.MonkeyPatch, db_conn
    ) -> None:
        """Expired guest sessions are rejected."""
        init_schema()

        session = create_guest_session(expiration_hours=24)
        try:
            # Manually expire it so the helper's own connection (used by
            # validate_guest_session) observes the committed expiry; the
            # committed UPDATE is scoped to this test's own session row,
            # which the finally-block deletes entirely.
            cur = db_conn.cursor()
            cur.execute(
                "UPDATE guest_sessions SET expires_at = NOW() - interval '1 hour' WHERE id = %s",
                (session["id"],),
            )
            db_conn.commit()
            cur.close()

            validated = validate_guest_session(session["session_token"])
            assert validated is None
        finally:
            _delete_test_guest_session(session["id"])

    def test_increment_analysis_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Incrementing analysis count works."""
        init_schema()

        session = create_guest_session(expiration_hours=24)
        try:
            count1 = increment_guest_analysis_count(session["id"], max_analyses=3)
            assert count1 == 1

            count2 = increment_guest_analysis_count(session["id"], max_analyses=3)
            assert count2 == 2

            count3 = increment_guest_analysis_count(session["id"], max_analyses=3)
            assert count3 == 3

            # At limit
            result = increment_guest_analysis_count(session["id"], max_analyses=3)
            assert result is None
        finally:
            _delete_test_guest_session(session["id"])


# ---------------------------------------------------------------------------
# Guest session report
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _DB_AVAILABLE, reason="backend dependencies not installed")
class TestGuestSessionRouter:
    """Tests for guest session API endpoints."""

    @classmethod
    def setup_class(cls) -> None:
        """Pin authoritative test-environment variables for API tests."""
        os.environ["SECRET_KEY"] = "test-secret-key-12345"
        os.environ["CLERK_PUBLISHABLE_KEY"] = "pk_test_123"
        os.environ["CLERK_SECRET_KEY"] = "sk_test_123"
        os.environ["CLERK_JWT_ISSUER"] = "https://test.clerk.accounts.com"
        os.environ["CLERK_JWKS_URL"] = (
            "https://test.clerk.accounts.com/.well-known/jwks.json"
        )
        os.environ["DATABASE_URL"] = (
            "postgresql://postgres@localhost:5432/xportra_test?sslmode=disable"
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
                "expires_at": "2026-01-02T00:00:00+00:00",
                "analyses_count": 0,
                "is_active": True,
            }
            resp = self.client.post("/guest/session")
            assert resp.status_code == 201
            data = resp.json()
            assert data["session_token"] == "guest-token-abc"
            assert data["analyses_count"] == 0
            assert data["max_analyses"] == 3