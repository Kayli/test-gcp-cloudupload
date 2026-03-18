"""
Unit tests for src/db.py.

No server, no network — each test gets an isolated in-memory SQLite file
via the isolated_db fixture in conftest.py.
"""

import pytest

from src.db import complete_upload, get_file, insert_upload


def _insert(**kwargs: object) -> None:
    """insert_upload with defaults so tests only specify what they care about."""
    defaults: dict[str, object] = dict(
        id="file-1",
        tenant_id="team-a",
        filename="doc.pdf",
        object_key="tenant/team-a/files/file-1/doc.pdf",
        content_type="application/pdf",
        owner_email="user@example.com",
    )
    defaults.update(kwargs)
    insert_upload(**defaults)  # type: ignore[arg-type]


# ── insert / get ──────────────────────────────────────────────────────────────


def test_insert_creates_pending_record():
    _insert()
    row = get_file("file-1")
    assert row is not None
    assert row["status"] == "pending"
    assert row["filename"] == "doc.pdf"
    assert row["tenant_id"] == "team-a"
    assert row["owner_email"] == "user@example.com"
    assert row["completed_at"] is None
    assert row["size"] is None


def test_get_file_returns_none_for_unknown_id():
    assert get_file("nonexistent") is None


def test_insert_duplicate_id_raises():
    _insert(id="dup")
    with pytest.raises(Exception):
        _insert(id="dup")


# ── complete_upload ───────────────────────────────────────────────────────────


def test_complete_upload_transitions_to_complete():
    _insert(id="file-2")
    assert complete_upload(id="file-2", size=1024) is True
    row = get_file("file-2")
    assert row is not None
    assert row["status"] == "complete"
    assert row["size"] == 1024
    assert row["completed_at"] is not None


def test_complete_upload_without_size_leaves_size_null():
    _insert(id="file-3")
    assert complete_upload(id="file-3") is True
    row = get_file("file-3")
    assert row is not None
    assert row["size"] is None


def test_complete_upload_returns_false_for_missing_id():
    assert complete_upload(id="no-such-id") is False


def test_complete_upload_idempotency_guard():
    """Second complete on the same record must return False (already complete)."""
    _insert(id="file-4")
    assert complete_upload(id="file-4") is True
    assert complete_upload(id="file-4") is False


# ── timestamps ────────────────────────────────────────────────────────────────


def test_created_at_is_set_on_insert():
    _insert(id="file-5")
    row = get_file("file-5")
    assert row is not None
    assert row["created_at"] is not None
    # ISO-8601 UTC — basic shape check
    assert "T" in row["created_at"]


def test_completed_at_is_set_on_complete():
    _insert(id="file-6")
    complete_upload(id="file-6")
    row = get_file("file-6")
    assert row is not None
    assert row["completed_at"] is not None
    assert "T" in row["completed_at"]
