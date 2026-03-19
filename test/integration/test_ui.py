"""
Full-stack UI integration tests using a real browser.

Mirrors legacy/test/ui.spec.js — loads the page, clicks #fake-login,
then drives the upload and download flows via page.evaluate() so the
browser's own fetch() carries the auth headers set by the JS app.
"""

import os

from playwright.sync_api import Page

from helpers.server import APP_URL

# The Vite dev server — the URL a real user opens in their browser.
# All existing tests bypass Vite and talk to the API directly (APP_URL / :3000).
# Tests below that use UI_URL exercise the full browser path including the
# Vite proxy (/uploads → api:3000, /objstore → minio:9000).
UI_URL: str = os.getenv("UI_URL", "http://localhost:5173")


def test_ui_integration_flows(page: Page) -> None:
    # ── navigate & wait for DOM ───────────────────────────────────────────────
    page.goto(APP_URL)
    page.wait_for_load_state("domcontentloaded")

    # The app sets window._configLoaded after /config resolves; wait for it
    # but don't fail if the page doesn't expose that variable.
    try:
        page.wait_for_function(
            "typeof window._configLoaded !== 'undefined'",
            timeout=5_000,
        )
    except Exception:
        pass

    # ── fetch /config ─────────────────────────────────────────────────────────
    config = page.evaluate(
        "async () => { const r = await fetch('/config'); return r.json(); }"
    )
    assert config is not None
    has_sso = bool(config.get("googleClientId"))

    # ── check initial DOM state ───────────────────────────────────────────────
    init = page.evaluate(
        """() => ({
            signedOutText:     document.getElementById('signed-out')?.innerText,
            uploaderExists:    !!document.getElementById('uploader'),
            gsiScriptLoaded:   !!document.querySelector('script[src*="accounts.google.com/gsi/client"]'),
            idToken:           !!window.idToken,
            dummyUser:         window.dummyUser || null,
        })"""
    )
    assert init["signedOutText"] is not None, "#signed-out element must exist"
    assert not init["uploaderExists"], "#uploader must not be in the DOM before login"
    if has_sso:
        assert init["gsiScriptLoaded"], "GSI client script must be loaded when googleClientId is set"

    # ── click #fake-login ─────────────────────────────────────────────────────
    page.evaluate("() => document.getElementById('fake-login')?.click()")
    page.wait_for_timeout(300)

    after_login = page.evaluate(
        """() => ({
            signedOutText:   document.getElementById('signed-out')?.innerText,
            uploaderExists:  !!document.getElementById('uploader'),
            dummyUser:       window.dummyUser,
        })"""
    )
    assert "tester@example.com" in (after_login["signedOutText"] or ""), (
        "#signed-out must show the dummy email after login"
    )
    assert after_login["uploaderExists"], "#uploader must be in the DOM after login"
    assert after_login["dummyUser"] == "tester@example.com"

    # ── POST /uploads via browser fetch ──────────────────────────────────────
    upload_res = page.evaluate(
        """async () => {
            const h = { 'Content-Type': 'application/json' };
            if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
            if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
            const r = await fetch('/uploads', {
                method: 'POST',
                headers: h,
                body: JSON.stringify({ tenantId: 'team-a', filename: 'test.pdf' }),
            });
            return { status: r.status, body: await r.json() };
        }"""
    )
    assert upload_res["status"] == 200
    assert upload_res["body"]["id"], "upload response must contain id"
    assert upload_res["body"]["uploadUrl"], "upload response must contain uploadUrl"
    assert upload_res["body"]["expiresIn"] > 0, "expiresIn must be positive"

    upload_id = upload_res["body"]["id"]

    # ── POST /uploads/:id/complete (simulate post-upload callback) ────────────
    complete_res = page.evaluate(
        """async (uploadId) => {
            const h = { 'Content-Type': 'application/json' };
            if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
            if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
            const r = await fetch(`/uploads/${uploadId}/complete`, {
                method: 'POST',
                headers: h,
                body: JSON.stringify({ size: 1024 }),
            });
            return { status: r.status, body: await r.json() };
        }""",
        upload_id,
    )
    assert complete_res["status"] == 200
    assert complete_res["body"]["status"] == "complete"

    # ── GET /files/:id/download via browser fetch ─────────────────────────────
    dl_res = page.evaluate(
        """async (uploadId) => {
            const h = {};
            if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
            if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
            const r = await fetch(`/files/${uploadId}/download`, { headers: h });
            return { status: r.status, body: await r.json() };
        }""",
        upload_id,
    )
    assert dl_res["status"] == 200
    assert dl_res["body"]["downloadUrl"], "download response must contain downloadUrl"
    assert dl_res["body"]["expiresIn"] > 0, "expiresIn must be positive"


def test_dashboard_visible_after_login_and_shows_uploaded_file(page: Page) -> None:
    """Dashboard must be absent before login, appear after login, and list uploaded files."""
    page.goto(APP_URL)
    page.wait_for_load_state("domcontentloaded")

    # Dashboard must not exist before the user logs in.
    assert not page.evaluate("() => !!document.getElementById('dashboard')"), (
        "#dashboard must not be in the DOM before login"
    )

    # Sign in via the dev fake-login button.
    page.evaluate("() => document.getElementById('fake-login')?.click()")
    page.wait_for_timeout(300)

    # Dashboard must now be mounted.
    assert page.evaluate("() => !!document.getElementById('dashboard')"), (
        "#dashboard must appear after login"
    )

    # Upload a file via the API so the dashboard has something to display.
    upload_res = page.evaluate(
        """async () => {
            const h = { 'Content-Type': 'application/json' };
            if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
            if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
            const r = await fetch('/uploads', {
                method: 'POST',
                headers: h,
                body: JSON.stringify({ tenantId: 'team-a', filename: 'ui-dashboard.pdf' }),
            });
            return { status: r.status, body: await r.json() };
        }"""
    )
    assert upload_res["status"] == 200
    upload_id = upload_res["body"]["id"]

    # Mark the upload as complete.
    page.evaluate(
        """async (uid) => {
            const h = { 'Content-Type': 'application/json' };
            if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
            if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
            await fetch(`/uploads/${uid}/complete`, {
                method: 'POST', headers: h, body: JSON.stringify({ size: 256 }),
            });
        }""",
        upload_id,
    )

    # Click the Refresh button inside the dashboard.
    page.evaluate(
        "() => document.querySelector('#dashboard .refresh-btn')?.click()"
    )
    page.wait_for_timeout(600)

    # The filename must now appear somewhere inside the dashboard.
    dashboard_text = page.evaluate(
        "() => document.getElementById('dashboard')?.innerText ?? ''"
    )
    assert "ui-dashboard.pdf" in dashboard_text, (
        "dashboard must display the filename of the uploaded file"
    )
    assert "complete" in dashboard_text.lower(), (
        "dashboard must show 'complete' status for the finished upload"
    )


def test_file_upload_via_vite_proxy(page: Page, browser_minio_url) -> None:
    """
    End-to-end upload driven through the Vite dev server at :5173.

    This test exercises the full browser UX path that a real user takes:

      1. Browser opens the Vite dev server (UI_URL / :5173).
      2. User signs in via the dev fake-login button.
      3. User picks a file — triggers Uploader.jsx handleFileChange().
      4. JS POSTs to /uploads  →  Vite proxy  →  api:3000   (gets presigned URL)
      5. JS PUTs bytes to the presigned URL  →  localhost:5173/objstore/…
                                              →  Vite proxy  →  minio:9000
      6. JS POSTs to /uploads/:id/complete  →  Vite proxy  →  api:3000
      7. #upload-result shows "Upload complete ✓"

    CURRENTLY FAILS at step 5 with "Upload failed: 404 Not Found"
    because the PUT to the presigned MinIO URL (proxied through Vite
    at /objstore/…) returns 404.  The API-level tests (test_uploads.py)
    never go through the Vite proxy so they do not catch this regression.
    """
    page.goto(UI_URL)
    page.wait_for_load_state("domcontentloaded")

    # Sign in via the dev fake-login button so auth headers are set.
    page.click("#fake-login")
    page.wait_for_selector("#uploader")

    # Inject a small synthetic file directly into the hidden <input type="file">.
    # set_input_files() triggers the onChange handler in Uploader.jsx exactly
    # as if the user had picked the file through the native OS file picker.
    page.set_input_files(
        "#file-input",
        files=[{"name": "e2e-test.txt", "mimeType": "text/plain", "buffer": b"e2e upload payload"}],
    )

    # Wait for the upload flow to settle — the result cycles through several
    # intermediate states before landing on a final success or failure message.
    page.wait_for_function(
        """() => {
            const txt = document.getElementById('upload-result')?.innerText ?? '';
            return txt !== ''
                && txt !== 'Requesting upload URL\u2026'
                && txt !== 'Uploading directly to storage\u2026'
                && txt !== 'Registering upload\u2026';
        }""",
        timeout=15_000,
    )

    result_text = page.inner_text("#upload-result")

    assert "Upload complete" in result_text, (
        f"Expected upload to succeed end-to-end via the Vite proxy, "
        f"but #upload-result shows: {result_text!r}"
    )
