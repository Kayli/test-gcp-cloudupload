#!/usr/bin/env bash
set -euo pipefail

echo "Running devcontainer post-create steps..."

# Source devcontainer .env if present so post-create sees the same env as shells
if [ -f ".devcontainer/.env" ]; then
  set -a                # automatically export all subsequently defined vars
  # shellcheck disable=SC1090
  . ".devcontainer/.env"
  set +a
  echo "Sourced and exported .devcontainer/.env"
fi

# Existing GCP credentials hint
if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
  echo "Found GOOGLE_APPLICATION_CREDENTIALS at $GOOGLE_APPLICATION_CREDENTIALS"
  echo "Run: gcloud auth activate-service-account --key-file=\$GOOGLE_APPLICATION_CREDENTIALS"
else
  echo "⚠️  WARNING: No GCP credentials found at ${GOOGLE_APPLICATION_CREDENTIALS:-<unset>}"
  echo "   To enable gcloud auth, place your service-account key at /workspaces/.secrets/gcloud-key"
  echo "   and re-open the devcontainer (or mount your secrets)."
fi

echo "Dependency installation moved to Dockerfile build (uses pyproject.toml + uv)."
echo "If you rebuild the devcontainer image, dependencies declared in `pyproject.toml` will be installed during the build."

echo "Devcontainer post-create steps complete."

# Ensure interactive shells for the `vscode` user source the .devcontainer/.env file
# and export variables. Append a small idempotent snippet to /home/vscode/.bashrc so
# interactive shells load the same devcontainer environment variables.
cat >> "/home/vscode/.bashrc" <<'BASH'
# Load devcontainer environment and export variables if present
if [ -f "/workspaces/test-gcp-cloudupload/.devcontainer/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "/workspaces/test-gcp-cloudupload/.devcontainer/.env"
  set +a
fi
BASH


