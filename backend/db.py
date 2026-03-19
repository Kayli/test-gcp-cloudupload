"""Metadata store for uploaded files.

Backends
--------
SQLite (default / dev / test):
    Active when DATABASE_URL env var is NOT set.
    DB file path defaults to ./data/uploads.db; override with DB_PATH.
    This is the only backend used by unit tests (test/unit/conftest.py
    monkeypatches DB_PATH and _conn directly — both names are preserved).

PostgreSQL (prod / Cloud Run + Cloud SQL):
    Active when DATABASE_URL env var is set, e.g.:
        postgresql://docstore:PASSWORD@/docstore?host=/cloudsql/PROJECT:REGION:INSTANCE
    Requires psycopg2-binary.  Cloud Run connects via the Cloud SQL Auth
    Proxy Unix socket — no VPC connector needed.

Both backends expose the same public API and return dict-accessible row
objects (sqlite3.Row and psycopg2.extras.RealDictRow both support
row["column"] syntax), so callers in app.py are unaffected.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Backend selection ─────────────────────────────────────────────────────────

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
_USE_PG: bool = bool(DATABASE_URL)

# ── SQLite state ──────────────────────────────────────────────────────────────
# These module-level names are kept for test-fixture compatibility:
# test/unit/conftest.py monkeypatches them directly.

DB_PATH = Path(os.getenv("DB_PATH", "./data/uploads.db"))
_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

_DDL = """
CREATE TABLE IF NOT EXISTS files (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    filename     TEXT NOT NULL,
    object_key   TEXT NOT NULL,
    content_type TEXT,
    size         INTEGER,
    owner_email  TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TEXT NOT NULL,
    completed_at TEXT
);
"""


def get_db() -> sqlite3.Connection:
    """Return (and lazily initialise) the shared SQLite connection.

    Not called in PostgreSQL mode — kept for test-fixture compatibility.
    """
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        # WAL mode allows concurrent reads while a write is in progress.
        _conn.execute("PRAGMA journal_mode=WAL;")
        _conn.execute(_DDL)
        _conn.commit()
    return _conn


# ── PostgreSQL helpers ─────────────────────────────────────────────────────────

_pg_conn: Optional[Any] = None  # psycopg2.extensions.connection


def _get_pg() -> Any:
    """Return the shared psycopg2 connection, reconnecting when needed.

    Handles idle-timeout disconnects from the Cloud SQL Auth Proxy.
    Must be called while holding _lock (or before any concurrent access).
    """
    global _pg_conn
    try:
        if _pg_conn is None or _pg_conn.closed:
            raise Exception("reconnect")
        # Cheap liveness probe — raises if the underlying socket is gone.
        _pg_conn.poll()
    except Exception:
        import psycopg2  # type: ignore[import]

        _pg_conn = psycopg2.connect(DATABASE_URL)
        # Ensure schema exists on every fresh connection.
        with _pg_conn.cursor() as cur:
            cur.execute(_DDL)
        _pg_conn.commit()

    return _pg_conn


def _pg_exec(sql: str, params: tuple = ()) -> Any:
    """Execute *sql* on the PG connection and return a RealDictCursor.

    Converts SQLite '?' placeholders to psycopg2 '%s' automatically.
    Must be called while holding _lock.
    """
    import psycopg2.extras  # type: ignore[import]

    conn = _get_pg()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql.replace("?", "%s"), params)
    return cur


# ── Public API ────────────────────────────────────────────────────────────────


def insert_upload(
    *,
    id: str,
    tenant_id: str,
    filename: str,
    object_key: str,
    content_type: str,
    owner_email: Optional[str],
) -> None:
    """Insert a new 'pending' upload record."""
    sql = """
        INSERT INTO files
            (id, tenant_id, filename, object_key, content_type, owner_email, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
    """
    params = (
        id,
        tenant_id,
        filename,
        object_key,
        content_type,
        owner_email,
        datetime.now(timezone.utc).isoformat(),
    )
    with _lock:
        if _USE_PG:
            _pg_exec(sql, params)
            _get_pg().commit()
        else:
            get_db().execute(sql, params)
            get_db().commit()


def complete_upload(*, id: str, size: Optional[int] = None) -> bool:
    """Transition a pending upload to 'complete'.

    Returns True if the row was updated, False if the id was not found or
    was already in a non-pending state (idempotency guard).
    """
    sql = """
        UPDATE files
           SET status       = 'complete',
               completed_at = ?,
               size         = COALESCE(?, size)
         WHERE id     = ?
           AND status = 'pending'
    """
    params = (datetime.now(timezone.utc).isoformat(), size, id)
    with _lock:
        if _USE_PG:
            cur = _pg_exec(sql, params)
            _get_pg().commit()
            return cur.rowcount == 1
        else:
            cur = get_db().execute(sql, params)
            get_db().commit()
            return cur.rowcount == 1


def get_file(id: str) -> Optional[Any]:
    """Fetch a single file record by id, or None if not found."""
    sql = "SELECT * FROM files WHERE id = ?"
    if _USE_PG:
        with _lock:
            return _pg_exec(sql, (id,)).fetchone()
    else:
        # SQLite WAL allows concurrent reads without the write lock.
        return get_db().execute(sql, (id,)).fetchone()


def list_files(owner_email: str) -> list[Any]:
    """Return all file records belonging to *owner_email*, newest first."""
    sql = "SELECT * FROM files WHERE owner_email = ? ORDER BY created_at DESC LIMIT 20"
    if _USE_PG:
        with _lock:
            return _pg_exec(sql, (owner_email,)).fetchall()
    else:
        return get_db().execute(sql, (owner_email,)).fetchall()
