"""
Server lifecycle helpers for pytest sessions.

Mirrors the behaviour of legacy/test/helpers/server.js:
  - ensureServer() → ensure_server()  spawns `uvicorn main:app` if the app is
                     not already up, then polls /health until ready (up to 10 s).
  - stopServer()   → stop_server()    kills the spawned process.

The module-level APP_URL is exported so test files can build request URLs
without repeating the env-var lookup.
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.request
from pathlib import Path

# ── configuration ────────────────────────────────────────────────────────────

APP_URL: str = os.getenv("APP_URL", "http://localhost:3000")
_SERVER_PORT: int = int(APP_URL.rstrip("/").rsplit(":", 1)[-1]) if ":" in APP_URL else 3000

# ── module state ─────────────────────────────────────────────────────────────

_server_proc: subprocess.Popen | None = None  # type: ignore[type-arg]

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


def ensure_server() -> None:
    """Start the FastAPI server if it is not already accepting connections."""
    global _server_proc

    if is_server_up():
        print("[server] App server already running.")
        return

    print("[server] Starting app server …")

    # Resolve the workspace root (two levels above this file: test/helpers/server.py)
    cwd = os.getenv("SERVER_CWD") or str(Path(__file__).resolve().parents[2])

    env = os.environ.copy()
    env["ALLOW_DEV_AUTH"] = "1"
    env["PORT"] = str(_SERVER_PORT)

    _server_proc = subprocess.Popen(
        ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(_SERVER_PORT)],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if not is_server_up(timeout_secs=10.0):
        _server_proc.kill()
        raise RuntimeError("App server did not start within 10 s")

    print("[server] App server ready.")


def stop_server() -> None:
    """Kill the spawned server process (no-op if we did not start it)."""
    global _server_proc
    if _server_proc is not None:
        _server_proc.kill()
        _server_proc = None
        print("[server] App server stopped.")
