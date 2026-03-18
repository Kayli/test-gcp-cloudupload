"""
Unit test configuration.

The isolated_db fixture gives every test its own temporary SQLite file and
resets the module-level connection singleton in src.db so tests never share
database state.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point src.db at a fresh temporary database for each test."""
    import backend.db as db_module

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    # Reset singleton so the next get_db() call opens the temp file.
    monkeypatch.setattr(db_module, "_conn", None)
    yield
    # Close the connection if one was opened during the test.
    if db_module._conn is not None:
        db_module._conn.close()
