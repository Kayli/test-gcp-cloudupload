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

    # Actually PUT data through the signed URL — proves MinIO is reachable.
    # boto3 generates presigned URLs locally (no MinIO contact needed), so
    # without this step the test passes even when MinIO is completely down.
    put_resp = api_context.fetch(
        body["uploadUrl"],
        method="PUT",
        data=b"hello from test",
        headers={"content-type": "application/octet-stream"},
    )
    assert put_resp.status in (200, 204), (
        f"PUT to presigned uploadUrl failed ({put_resp.status}) — is MinIO running?"
    )


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
    # Full happy-path: create → PUT → complete → download → verify round-trip.
    # Every step that touches a presigned URL exercises MinIO directly so the
    # test will fail fast when MinIO is down.
    file_content = b"round-trip payload for photo test"
    content_type = "image/jpeg"

    create_resp = api_context.post(
        f"{APP_URL}/uploads",
        headers=_JSON_HEADERS,
        data=json.dumps({"tenantId": "team-a", "filename": "photo.jpg", "contentType": content_type}),
    )
    assert create_resp.status == 200
    create_body = create_resp.json()
    upload_id = create_body["id"]
    upload_url = create_body["uploadUrl"]

    # PUT the actual bytes — fails immediately if MinIO is unreachable.
    put_resp = api_context.fetch(
        upload_url,
        method="PUT",
        data=file_content,
        headers={"content-type": content_type},
    )
    assert put_resp.status in (200, 204), (
        f"PUT to presigned uploadUrl failed ({put_resp.status}) — is MinIO running?"
    )

    api_context.post(
        f"{APP_URL}/uploads/{upload_id}/complete",
        headers=_JSON_HEADERS,
        data=json.dumps({"size": len(file_content)}),
    )

    resp = api_context.get(
        f"{APP_URL}/files/{upload_id}/download",
        headers=_DUMMY_HEADERS,
    )
    assert resp.status == 200
    body = resp.json()
    assert "downloadUrl" in body, "response must include downloadUrl"
    assert "expiresIn" in body, "response must include expiresIn"

    # GET through the signed download URL and verify the exact bytes come back.
    get_resp = api_context.fetch(body["downloadUrl"], method="GET")
    assert get_resp.status == 200, (
        f"GET from presigned downloadUrl failed ({get_resp.status}) — is MinIO running?"
    )
    assert get_resp.body() == file_content, "downloaded content does not match what was uploaded"


def test_get_files_download_returns_404_for_unknown_id(api_context: APIRequestContext) -> None:
    resp = api_context.get(
        f"{APP_URL}/files/nonexistent-id-000/download",
        headers=_DUMMY_HEADERS,
    )
    assert resp.status == 404


# ── GET /files (dashboard list) ───────────────────────────────────────────────


def test_get_files_returns_list_for_authenticated_user(api_context: APIRequestContext) -> None:
    """GET /files returns an array containing every upload made by the user."""
    # Create and complete one upload so there is at least one record.
    create_resp = api_context.post(
        f"{APP_URL}/uploads",
        headers=_JSON_HEADERS,
        data=json.dumps({"tenantId": "team-a", "filename": "dashboard-test.txt"}),
    )
    assert create_resp.status == 200
    upload_id = create_resp.json()["id"]

    api_context.post(
        f"{APP_URL}/uploads/{upload_id}/complete",
        headers=_JSON_HEADERS,
        data=json.dumps({"size": 512}),
    )

    resp = api_context.get(f"{APP_URL}/files", headers=_DUMMY_HEADERS)
    assert resp.status == 200
    body = resp.json()
    assert "files" in body, "response must have a 'files' key"
    assert isinstance(body["files"], list)

    ids = [f["id"] for f in body["files"]]
    assert upload_id in ids, "the upload we just created must appear in the list"

    # Verify the shape of the matching record.
    record = next(f for f in body["files"] if f["id"] == upload_id)
    assert record["filename"] == "dashboard-test.txt"
    assert record["status"] == "complete"
    assert record["size"] == 512
    assert "createdAt" in record
    assert "completedAt" in record


def test_get_files_requires_authentication(api_context: APIRequestContext) -> None:
    """GET /files must reject unauthenticated requests with 401."""
    resp = api_context.get(f"{APP_URL}/files")
    assert resp.status == 401


def test_get_files_does_not_return_other_users_files(api_context: APIRequestContext) -> None:
    """Files uploaded by user A must not appear in user B's dashboard."""
    user_a_headers = {"x-dummy-user": "usera@example.com", "content-type": "application/json"}
    user_b_headers = {"x-dummy-user": "userb@example.com"}

    # Upload a file as user A.
    create_resp = api_context.post(
        f"{APP_URL}/uploads",
        headers=user_a_headers,
        data=json.dumps({"tenantId": "team-x", "filename": "secret-a.pdf"}),
    )
    assert create_resp.status == 200
    upload_id_a = create_resp.json()["id"]

    # Fetch the list as user B — must not see user A's file.
    resp = api_context.get(f"{APP_URL}/files", headers=user_b_headers)
    assert resp.status == 200
    ids = [f["id"] for f in resp.json()["files"]]
    assert upload_id_a not in ids, "user B must not see user A's upload"
