"""
Server lifecycle helpers for integration test sessions.

If the app server is not already up, automatically starts the full compose
stack (minio + api) so tests run without any manual setup step.

The module-level APP_URL is exported so test files can build request URLs
without repeating the env-var lookup.
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.request
from pathlib import Path

# ── configuration ─────────────────────────────────────────────────────────────

APP_URL: str = os.getenv("APP_URL", "http://localhost:3000")

# Workspace root: three levels above this file (test/integration/helpers/server.py)
_WORKSPACE_ROOT: str = os.getenv("SERVER_CWD") or str(Path(__file__).resolve().parents[3])

# ── module state ──────────────────────────────────────────────────────────────

_we_started_compose: bool = False

# ── helpers ───────────────────────────────────────────────────────────────────


def is_server_up(timeout_secs: float = 5.0) -> bool:
    """Poll GET /health until it returns HTTP 200 or the deadline passes."""
    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{APP_URL}/health", timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def _is_server_up_now() -> bool:
    """Single non-blocking probe — used to check if the server is already up."""
    try:
        with urllib.request.urlopen(f"{APP_URL}/health", timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


def ensure_server() -> None:
    """Start the compose stack if the app server is not already reachable.

    If the server is already up (e.g. CI pre-started it, or the developer ran
    `docker compose up` manually), this is a no-op.  Otherwise the full stack
    (minio + api and their dependencies) is started via `docker compose up -d
    --wait api` and torn down at the end of the session by stop_server().
    """
    global _we_started_compose

    # Tests PUT directly to MinIO (port 9000), not via the Vite proxy (5173).
    # Always restart just the api service with the test-appropriate value so
    # that presigned URLs are reachable from within the devcontainer regardless
    # of how compose was originally started.
    test_env = os.environ.copy()
    test_env["MINIO_PUBLIC_URL"] = "http://localhost:9000"

    if _is_server_up_now():
        print("[server] App server already running — restarting api with test MINIO_PUBLIC_URL.")
        subprocess.run(
            ["docker", "compose", "up", "-d", "--no-deps", "api"],
            cwd=_WORKSPACE_ROOT,
            env=test_env,
            check=True,
        )
        if not is_server_up(timeout_secs=15.0):
            raise RuntimeError("App server did not become healthy after restart")
        return

    print(f"[server] Starting compose stack from {_WORKSPACE_ROOT} …")
    subprocess.run(
        ["docker", "compose", "up", "-d", "--wait", "api"],
        cwd=_WORKSPACE_ROOT,
        env=test_env,
        check=True,
    )
    _we_started_compose = True

    if not is_server_up(timeout_secs=15.0):
        raise RuntimeError("App server did not become healthy within 15 s after compose up")

    print("[server] Compose stack ready.")


def stop_server() -> None:
    """Tear down the compose stack — only if this session started it.
    If the server was already running when tests began, restore it to the
    browser-facing MINIO_PUBLIC_URL (http://localhost:5173)."""
    global _we_started_compose
    if _we_started_compose:
        print("[server] Stopping compose stack …")
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=_WORKSPACE_ROOT,
            check=False,
        )
        _we_started_compose = False
        print("[server] Compose stack stopped.")
    else:
        # Restore the api to browser-facing presigned URLs.
        # Use --no-deps so only the api container is restarted, leaving
        # minio and ui untouched.
        browser_env = os.environ.copy()
        browser_env["MINIO_PUBLIC_URL"] = os.getenv("UI_URL", "http://localhost:5173")
        subprocess.run(
            ["docker", "compose", "up", "-d", "--no-deps", "api"],
            cwd=_WORKSPACE_ROOT,
            env=browser_env,
            check=False,
        )
        print("[server] Restored api to browser-facing MINIO_PUBLIC_URL.")
