"""
pytest configuration and shared fixtures.

Mirrors legacy/test/fixtures.js and the beforeAll/afterAll server lifecycle
used in every legacy spec file.

Fixtures
--------
server         session-scoped, autouse — starts FastAPI server once per session
               (delegates to helpers/server.py → ensure_server / stop_server).

browser        session-scoped — overrides pytest-playwright's default fixture.
               • USE_HOST_BROWSER=1  → connect to a running Chrome via CDP
                 (CHROME_REMOTE_DEBUGGING_URL, default host.docker.internal:9222).
               • default             → launch headless Chromium in the container.

api_context    function-scoped — a standalone Playwright APIRequestContext for
               pure-HTTP tests (analogous to the { request } fixture in Node
               Playwright).
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import subprocess

import pytest
from playwright.sync_api import Playwright

from helpers.server import APP_URL, _WORKSPACE_ROOT, ensure_server, is_server_up, stop_server

# ── env switches ──────────────────────────────────────────────────────────────

USE_HOST_BROWSER: bool = os.getenv("USE_HOST_BROWSER") == "1"
CDP_URL: str = os.getenv("CHROME_REMOTE_DEBUGGING_URL", "http://host.docker.internal:9222")


# ── utilities ─────────────────────────────────────────────────────────────────


def _resolve_cdp_url(url: str) -> str:
    """
    Resolve a hostname in *url* to its IP address.

    Chrome's CDP endpoint rejects HTTP requests whose Host header contains a
    non-IP, non-localhost hostname (returns 500 "Host header is specified and
    is not an IP address or localhost").  Playwright sends the raw hostname as
    the Host header, so we must convert it to an IP first.
    """
    import ipaddress

    parsed = urlparse(url)
    host = parsed.hostname or ""

    # Already an IP — nothing to do.
    try:
        ipaddress.ip_address(host)
        return url
    except ValueError:
        pass

    if host == "localhost":
        return url

    try:
        ip = socket.gethostbyname(host)
        # Simple string replace is safe because the hostname is unique in the URL.
        return url.replace(host, ip, 1)
    except Exception as exc:
        print(f"[conftest] Could not resolve CDP hostname '{host}': {exc} — using original URL")
        return url


# ── server fixture ────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def server() -> None:  # type: ignore[return]
    """Start the FastAPI server once for the entire test session."""
    ensure_server()
    yield  # type: ignore[misc]
    stop_server()


# ── browser fixture (overrides pytest-playwright) ─────────────────────────────


@pytest.fixture(scope="session")
def browser(playwright: Playwright):  # type: ignore[override]
    """
    Override pytest-playwright's browser fixture.

    USE_HOST_BROWSER=1 → connect to already-running Chrome via CDP so tests
    can be watched in the host browser.  The browser is intentionally NOT
    closed so Chrome keeps running after the suite finishes.

    default → launch headless Chromium inside the container.
    """
    if USE_HOST_BROWSER:
        resolved = _resolve_cdp_url(CDP_URL)
        print(f"\n[conftest] USE_HOST_BROWSER=1 → CDP at {resolved} (resolved from {CDP_URL})\n")
        b = playwright.chromium.connect_over_cdp(resolved)
        yield b
        # Intentionally skip browser.close() — keep the host browser running.
    else:
        b = playwright.chromium.launch(headless=True)
        yield b
        b.close()


# ── MINIO_PUBLIC_URL switcher ────────────────────────────────────────────────


@pytest.fixture()
def browser_minio_url():
    """
    Restart the api with MINIO_PUBLIC_URL=UI_URL so presigned URLs are
    reachable from the host browser (which cannot reach minio:9000 under DinD).
    Restored to http://localhost:9000 on teardown so the non-UI upload tests
    (which run inside the devcontainer and PUT directly to MinIO) still work.
    """
    ui_url = os.getenv("UI_URL", "http://localhost:5173")

    def _restart(minio_public_url: str) -> None:
        env = os.environ.copy()
        env["MINIO_PUBLIC_URL"] = minio_public_url
        subprocess.run(
            ["docker", "compose", "up", "-d", "--no-deps", "api"],
            cwd=_WORKSPACE_ROOT,
            env=env,
            check=True,
        )
        if not is_server_up(timeout_secs=15.0):
            raise RuntimeError(f"API did not recover after setting MINIO_PUBLIC_URL={minio_public_url}")

    _restart(ui_url)
    yield
    _restart("http://localhost:9000")


# ── API request context fixture ───────────────────────────────────────────────


@pytest.fixture()
def api_context(playwright: Playwright):
    """
    A standalone Playwright APIRequestContext for pure-HTTP tests.

    Analogous to the { request } fixture provided by @playwright/test in the
    legacy Node test suite.  Disposed automatically after each test.
    """
    ctx = playwright.request.new_context(base_url=APP_URL)
    yield ctx
    ctx.dispose()
