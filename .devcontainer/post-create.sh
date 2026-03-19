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

# Activate GCP credentials if the service-account key is present
SA_KEY="${GOOGLE_APPLICATION_CREDENTIALS:-/workspaces/.secrets/gcp-sa-key.json}"
if [ -f "$SA_KEY" ]; then
  echo "Activating GCP service account from $SA_KEY"
  gcloud auth activate-service-account --key-file="$SA_KEY" --quiet

  PROJECT_ID="$(python3 -c "import json; d=json.load(open('$SA_KEY')); print(d['project_id'])")"
  gcloud config set project "$PROJECT_ID" --quiet
  echo "Active project: $PROJECT_ID"

  # Authenticate Docker to push/pull from Artifact Registry in all common regions.
  # Add more region prefixes here if you deploy outside us-central1.
  for region in us-central1 us-east1 europe-west1 asia-east1; do
    gcloud auth configure-docker "${region}-docker.pkg.dev" --quiet 2>/dev/null || true
  done
  echo "Docker configured for Artifact Registry."
else
  echo "⚠️  WARNING: No GCP credentials found at $SA_KEY"
  echo "   Place your service-account key there and run: bash .devcontainer/post-create.sh"
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


