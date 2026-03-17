"""
Tests for POST /uploads and GET /files/:id/download.

Mirrors legacy/test/uploads.spec.js.
"""

import json

from playwright.sync_api import APIRequestContext

from helpers.server import APP_URL

# x-dummy-user header used by all upload/download tests
_DUMMY_HEADERS = {"x-dummy-user": "tester@example.com"}
_JSON_HEADERS = {**_DUMMY_HEADERS, "content-type": "application/json"}


def test_post_uploads_returns_upload_url(api_context: APIRequestContext) -> None:
    payload = {"tenantId": "team-a", "filename": "doc.pdf"}
    resp = api_context.post(
        f"{APP_URL}/uploads",
        headers=_JSON_HEADERS,
        data=json.dumps(payload),
    )
    assert resp.status == 200
    body = resp.json()
    assert body.get("id"), "response must include an id"
    assert body.get("uploadUrl"), "response must include an uploadUrl"
    assert body.get("expiresIn"), "response must include expiresIn"


def test_post_uploads_without_required_fields_returns_400(api_context: APIRequestContext) -> None:
    resp = api_context.post(
        f"{APP_URL}/uploads",
        headers=_JSON_HEADERS,
        data=json.dumps({}),
    )
    assert resp.status == 400
    body = resp.json()
    assert "error" in body, "400 response must contain an 'error' key"


def test_get_files_download_returns_download_url(api_context: APIRequestContext) -> None:
    resp = api_context.get(
        f"{APP_URL}/files/abc123/download",
        headers=_DUMMY_HEADERS,
    )
    assert resp.status == 200
    body = resp.json()
    assert "downloadUrl" in body, "response must include downloadUrl"
    assert "expiresIn" in body, "response must include expiresIn"
