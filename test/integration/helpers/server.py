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

    if _is_server_up_now():
        print("[server] App server already running — skipping compose start.")
        return

    print(f"[server] Starting compose stack from {_WORKSPACE_ROOT} …")
    env = os.environ.copy()
    # Presigned URLs must be reachable by the test runner, not via the Vite proxy.
    env.setdefault("MINIO_PUBLIC_URL", "http://localhost:9000")
    subprocess.run(
        ["docker", "compose", "up", "-d", "--wait", "api"],
        cwd=_WORKSPACE_ROOT,
        env=env,
        check=True,
    )
    _we_started_compose = True

    if not is_server_up(timeout_secs=15.0):
        raise RuntimeError("App server did not become healthy within 15 s after compose up")

    print("[server] Compose stack ready.")


def stop_server() -> None:
    """Tear down the compose stack — only if this session started it."""
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
