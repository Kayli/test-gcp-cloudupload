"""
Integration tests for backend/db.py.

These tests call the db module directly (bypassing the HTTP layer) against the
real PostgreSQL instance started by docker-compose.  Each test is isolated via
the clean_db fixture, which truncates the files table before and after the test.
"""

import pytest

from backend.db import complete_upload, get_file, insert_upload, list_files

# Apply clean_db isolation and a tight timeout to every test in this module.
# 5 s is plenty for direct DB calls; a hang almost certainly means a lost connection.
pytestmark = [
    pytest.mark.usefixtures("clean_db"),
    pytest.mark.timeout(5),
]


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


# ── list_files ───────────────────────────────────────────────────────────────────


def test_list_files_returns_only_owner_records():
    """Records are filtered strictly by owner_email."""
    _insert(id="lf-1", owner_email="alice@example.com", filename="a.pdf")
    _insert(id="lf-2", owner_email="bob@example.com",   filename="b.pdf")
    _insert(id="lf-3", owner_email="alice@example.com", filename="c.pdf")

    alice_rows = list_files("alice@example.com")
    assert len(alice_rows) == 2
    filenames = {r["filename"] for r in alice_rows}
    assert filenames == {"a.pdf", "c.pdf"}

    bob_rows = list_files("bob@example.com")
    assert len(bob_rows) == 1
    assert bob_rows[0]["filename"] == "b.pdf"


def test_list_files_returns_empty_for_unknown_owner():
    _insert(id="lf-4", owner_email="someone@example.com")
    assert list_files("nobody@example.com") == []


def test_list_files_ordered_newest_first():
    """Rows must come back in descending created_at order."""
    import time

    _insert(id="lf-5", owner_email="order@example.com", filename="first.pdf")
    time.sleep(0.01)  # ensure distinct timestamps
    _insert(id="lf-6", owner_email="order@example.com", filename="second.pdf")

    rows = list_files("order@example.com")
    assert len(rows) == 2
    assert rows[0]["filename"] == "second.pdf", "newest file must be first"
    assert rows[1]["filename"] == "first.pdf"


def test_list_files_capped_at_20():
    """list_files must return at most 20 records even when more exist."""
    for i in range(25):
        insert_upload(
            id=f"cap-{i}",
            tenant_id="team-a",
            filename=f"file-{i}.pdf",
            object_key=f"tenant/team-a/files/cap-{i}/file-{i}.pdf",
            content_type="application/pdf",
            owner_email="capped@example.com",
        )

    rows = list_files("capped@example.com")
    assert len(rows) == 20, "must return exactly 20 rows when more than 20 exist"
