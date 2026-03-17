"""
Full-stack UI integration tests using a real browser.

Mirrors legacy/test/ui.spec.js — loads the page, clicks #fake-login,
then drives the upload and download flows via page.evaluate() so the
browser's own fetch() carries the auth headers set by the JS app.
"""

from helpers.server import APP_URL


def test_ui_integration_flows(page) -> None:
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
            uploaderDisplay:   document.getElementById('uploader')?.style.display,
            downloaderDisplay: document.getElementById('downloader')?.style.display,
            gsiScriptLoaded:   !!document.querySelector('script[src*="accounts.google.com/gsi/client"]'),
            idToken:           !!window.idToken,
            dummyUser:         window.dummyUser || null,
        })"""
    )
    assert init["signedOutText"] is not None, "#signed-out element must exist"
    assert init["uploaderDisplay"] == "none", "#uploader must be hidden before login"
    if has_sso:
        assert init["gsiScriptLoaded"], "GSI client script must be loaded when googleClientId is set"

    # ── click #fake-login ─────────────────────────────────────────────────────
    page.evaluate("() => document.getElementById('fake-login')?.click()")
    page.wait_for_timeout(300)

    after_login = page.evaluate(
        """() => ({
            signedOutText:   document.getElementById('signed-out')?.innerText,
            uploaderDisplay: document.getElementById('uploader')?.style.display,
            dummyUser:       window.dummyUser,
        })"""
    )
    assert "tester@example.com" in (after_login["signedOutText"] or ""), (
        "#signed-out must show the dummy email after login"
    )
    assert after_login["uploaderDisplay"] != "none", "#uploader must be visible after login"
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

    # ── GET /files/:id/download via browser fetch ─────────────────────────────
    dl_res = page.evaluate(
        """async () => {
            const h = {};
            if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
            if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
            const r = await fetch('/files/abc123/download', { headers: h });
            return { status: r.status, body: await r.json() };
        }"""
    )
    assert dl_res["status"] == 200
    assert dl_res["body"]["downloadUrl"], "download response must contain downloadUrl"
    assert dl_res["body"]["expiresIn"] > 0, "expiresIn must be positive"
