"""
Tests for GET /health.

Mirrors legacy/test/health.spec.js.
"""

from helpers.server import APP_URL


def test_health_returns_status_ok(api_context) -> None:
    resp = api_context.get(f"{APP_URL}/health")
    assert resp.status == 200
    assert resp.json() == {"status": "ok"}
