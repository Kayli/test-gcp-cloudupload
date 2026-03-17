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

# If Docker socket is mounted, create a group matching its GID and add the `vscode` user to it
if [ -S /var/run/docker.sock ]; then
  echo "Found docker socket at /var/run/docker.sock"
  DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
  echo "Docker socket GID: $DOCKER_GID"

  # See if a group already has this GID
  EXISTING_GROUP=$(getent group | awk -F: -v gid="$DOCKER_GID" '$3==gid {print $1; exit}')
  if [ -n "$EXISTING_GROUP" ]; then
    echo "Group with GID $DOCKER_GID already exists: $EXISTING_GROUP"
    GROUP_NAME="$EXISTING_GROUP"
  else
    GROUP_NAME="dockerhost"
    # Avoid clobbering an existing group name
    if getent group "$GROUP_NAME" >/dev/null 2>&1; then
      GROUP_NAME="${GROUP_NAME}_$DOCKER_GID"
    fi
    echo "Creating group $GROUP_NAME with GID $DOCKER_GID"
      if command -v sudo >/dev/null 2>&1; then
        sudo groupadd -g "$DOCKER_GID" "$GROUP_NAME"
      else
        groupadd -g "$DOCKER_GID" "$GROUP_NAME"
      fi
  fi

  echo "Adding user 'vscode' to group $GROUP_NAME"
  if command -v sudo >/dev/null 2>&1; then
    sudo usermod -aG "$GROUP_NAME" vscode
  else
    usermod -aG "$GROUP_NAME" vscode
  fi

  echo "Current groups for 'vscode': $(id -nG vscode)"
else
  echo "No docker socket found at /var/run/docker.sock; skipping docker group setup."
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


