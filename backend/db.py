"""Metadata store for uploaded files.

Backends
--------
SQLite (default / offline dev):
    Active when DATABASE_URL env var is NOT set.
    DB file path defaults to ./data/uploads.db; override with DB_PATH.

PostgreSQL (prod / Cloud Run + Cloud SQL):
    Active when DATABASE_URL env var is set, e.g.:
        postgresql://docstore:PASSWORD@/docstore?host=/cloudsql/PROJECT:REGION:INSTANCE
    Requires psycopg2-binary.  Cloud Run connects via the Cloud SQL Auth
    Proxy Unix socket — no VPC connector needed.

    Each public function opens its own connection, commits, and closes it.
    PostgreSQL handles concurrency natively — no application-level locking
    or shared connection state is needed.

Both backends expose the same public API and return dict-accessible row
objects (sqlite3.Row and psycopg2.extras.RealDictRow both support
row["column"] syntax), so callers in app.py are unaffected.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

# ── Backend selection ─────────────────────────────────────────────────────────

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
_USE_PG: bool = bool(DATABASE_URL)

# ── SQLite state ──────────────────────────────────────────────────────────────

DB_PATH = Path(os.getenv("DB_PATH", "./data/uploads.db"))
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
    """Return (and lazily initialise) the shared SQLite connection."""
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


# ── PostgreSQL helpers ────────────────────────────────────────────────────────


@contextmanager
def _pg_connection() -> Generator[Any, None, None]:
    """Open a fresh psycopg2 connection for one unit of work.

    Ensures the schema exists, commits on success, rolls back on error,
    and always closes the connection.  Each caller gets its own connection
    — PostgreSQL handles concurrent access natively.
    """
    import psycopg2  # type: ignore[import]

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(_DDL)
        conn.commit()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _exec(conn: Any, sql: str, params: tuple = ()) -> Any:
    """Execute *sql* on *conn* using a RealDictCursor.

    Converts SQLite '?' placeholders to psycopg2 '%s' automatically.
    """
    import psycopg2.extras  # type: ignore[import]

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql.replace("?", "%s"), params)
    return cur


# ── Test helpers ──────────────────────────────────────────────────────────────
# Not used by the application — exposed only for the clean_db test fixture.


def _truncate_for_tests() -> None:
    """Wipe all rows from the files table (PG only; no-op for SQLite)."""
    if not _USE_PG:
        return
    with _pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM files")


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
        id, tenant_id, filename, object_key, content_type, owner_email,
        datetime.now(timezone.utc).isoformat(),
    )
    if _USE_PG:
        with _pg_connection() as conn:
            _exec(conn, sql, params)
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
    if _USE_PG:
        with _pg_connection() as conn:
            cur = _exec(conn, sql, params)
            return cur.rowcount == 1
    else:
        cur = get_db().execute(sql, params)
        get_db().commit()
        return cur.rowcount == 1


def get_file(id: str) -> Optional[Any]:
    """Fetch a single file record by id, or None if not found."""
    sql = "SELECT * FROM files WHERE id = ?"
    if _USE_PG:
        with _pg_connection() as conn:
            return _exec(conn, sql, (id,)).fetchone()
    else:
        return get_db().execute(sql, (id,)).fetchone()


def list_files(owner_email: str) -> list[Any]:
    """Return all file records belonging to *owner_email*, newest first."""
    sql = "SELECT * FROM files WHERE owner_email = ? ORDER BY created_at DESC LIMIT 20"
    if _USE_PG:
        with _pg_connection() as conn:
            return _exec(conn, sql, (owner_email,)).fetchall()
    else:
        return get_db().execute(sql, (owner_email,)).fetchall()
