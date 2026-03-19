"""
Unit test configuration.

Backend selection
-----------------
PostgreSQL (preferred, realistic):
    Active when the DATABASE_URL environment variable is set.
    Set it to the locally-running Postgres from docker-compose:

        export DATABASE_URL=postgresql://docstore:docstore@localhost:5432/docstore

    Each test gets a clean slate via TRUNCATE TABLE after it runs.
    This catches PG-specific behaviour (type coercion, constraint handling,
    transaction semantics) that SQLite silently swallows.

SQLite (offline fallback):
    Used when DATABASE_URL is not set (e.g. quick offline iteration).
    Each test gets its own temp file so there is no shared state.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Isolate every test from every other test's database state."""
    import backend.db as db_module

    if db_module._USE_PG:
        # ── PostgreSQL mode ───────────────────────────────────────────────────
        # Drop the module-level connection so the test starts with a fresh one.
        monkeypatch.setattr(db_module, "_pg_conn", None)
        yield
        # Truncate all tables after the test so the next test starts clean.
        # TRUNCATE is faster than DELETE and resets any sequence state.
        # rollback() first: if the test intentionally triggered a PG error
        # (e.g. duplicate key), the connection is in an aborted-transaction
        # state and will reject any command until the transaction is reset.
        conn = db_module._pg_conn
        if conn is not None and not conn.closed:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE files")
            conn.commit()
            conn.close()
        monkeypatch.setattr(db_module, "_pg_conn", None)
    else:
        # ── SQLite fallback ───────────────────────────────────────────────────
        db_path = tmp_path / "test.db"
        monkeypatch.setattr(db_module, "DB_PATH", db_path)
        monkeypatch.setattr(db_module, "_conn", None)
        yield
        if db_module._conn is not None:
            db_module._conn.close()
