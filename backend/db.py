"""SQLite metadata store for uploaded files.

Schema
------
files(
    id           TEXT PRIMARY KEY,        -- UUID assigned by the server
    tenant_id    TEXT NOT NULL,
    filename     TEXT NOT NULL,           -- original file name
    object_key   TEXT NOT NULL,           -- storage key (path inside the bucket)
    content_type TEXT,
    size         INTEGER,                 -- bytes, filled in on /complete
    owner_email  TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'complete'
    created_at   TEXT NOT NULL,           -- ISO-8601 UTC timestamp
    completed_at TEXT                     -- ISO-8601 UTC timestamp, nullable
)

Thread safety: a module-level threading.Lock serialises writes so the
connection can safely be shared across FastAPI's worker threads.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
    db = get_db()
    with _lock:
        db.execute(
            """
            INSERT INTO files
                (id, tenant_id, filename, object_key, content_type, owner_email, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                id,
                tenant_id,
                filename,
                object_key,
                content_type,
                owner_email,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        db.commit()


def complete_upload(*, id: str, size: Optional[int] = None) -> bool:
    """Transition a pending upload to 'complete'.

    Returns True if the row was updated, False if the id was not found or
    was already in a non-pending state (idempotency guard).
    """
    db = get_db()
    with _lock:
        cur = db.execute(
            """
            UPDATE files
               SET status       = 'complete',
                   completed_at = ?,
                   size         = COALESCE(?, size)
             WHERE id     = ?
               AND status = 'pending'
            """,
            (datetime.now(timezone.utc).isoformat(), size, id),
        )
        db.commit()
        return cur.rowcount == 1


def get_file(id: str) -> Optional[sqlite3.Row]:
    """Fetch a single file record by id, or None if not found."""
    db = get_db()
    return db.execute("SELECT * FROM files WHERE id = ?", (id,)).fetchone()


def list_files(owner_email: str) -> list[sqlite3.Row]:
    """Return all file records belonging to *owner_email*, newest first."""
    db = get_db()
    return db.execute(
        "SELECT * FROM files WHERE owner_email = ? ORDER BY created_at DESC LIMIT 20",
        (owner_email,),
    ).fetchall()
