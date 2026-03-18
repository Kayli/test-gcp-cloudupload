"""
Tests for POST /uploads, POST /uploads/{id}/complete, and GET /files/:id/download.

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


def test_post_uploads_complete_marks_record(api_context: APIRequestContext) -> None:
    # 1. Create the upload
    create_resp = api_context.post(
        f"{APP_URL}/uploads",
        headers=_JSON_HEADERS,
        data=json.dumps({"tenantId": "team-a", "filename": "report.pdf"}),
    )
    assert create_resp.status == 200
    upload_id = create_resp.json()["id"]

    # 2. Mark as complete (simulates client calling back after successful PUT)
    complete_resp = api_context.post(
        f"{APP_URL}/uploads/{upload_id}/complete",
        headers=_JSON_HEADERS,
        data=json.dumps({"size": 2048}),
    )
    assert complete_resp.status == 200
    body = complete_resp.json()
    assert body.get("id") == upload_id
    assert body.get("status") == "complete"

    # 3. A second complete on the same id must 404 (idempotency guard)
    repeat_resp = api_context.post(
        f"{APP_URL}/uploads/{upload_id}/complete",
        headers=_JSON_HEADERS,
        data=json.dumps({}),
    )
    assert repeat_resp.status == 404


def test_get_files_download_returns_download_url(api_context: APIRequestContext) -> None:
    # Full happy-path: create → complete → download
    create_resp = api_context.post(
        f"{APP_URL}/uploads",
        headers=_JSON_HEADERS,
        data=json.dumps({"tenantId": "team-a", "filename": "photo.jpg", "contentType": "image/jpeg"}),
    )
    assert create_resp.status == 200
    upload_id = create_resp.json()["id"]

    api_context.post(
        f"{APP_URL}/uploads/{upload_id}/complete",
        headers=_JSON_HEADERS,
        data=json.dumps({"size": 512}),
    )

    resp = api_context.get(
        f"{APP_URL}/files/{upload_id}/download",
        headers=_DUMMY_HEADERS,
    )
    assert resp.status == 200
    body = resp.json()
    assert "downloadUrl" in body, "response must include downloadUrl"
    assert "expiresIn" in body, "response must include expiresIn"


def test_get_files_download_returns_404_for_unknown_id(api_context: APIRequestContext) -> None:
    resp = api_context.get(
        f"{APP_URL}/files/nonexistent-id-000/download",
        headers=_DUMMY_HEADERS,
    )
    assert resp.status == 404
