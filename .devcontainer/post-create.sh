#!/usr/bin/env bash
set -euo pipefail

echo "Running devcontainer post-create steps..."

# If Docker socket is mounted, create a group matching its GID and add the `node` user to it
if [ -S /var/run/docker.sock ]; then
  echo "Found docker socket at /var/run/docker.sock"
  DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
  echo "Docker socket GID: $DOCKER_GID"

  # See if a group already has this GID
  EXISTING_GROUP=$(getent group | awk -F: -v gid="$DOCKER_GID" '$3==gid {print $1; exit}') || true
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
      sudo groupadd -g "$DOCKER_GID" "$GROUP_NAME" || true
    else
      groupadd -g "$DOCKER_GID" "$GROUP_NAME" || true
    fi
  fi

  echo "Adding user 'node' to group $GROUP_NAME"
  if command -v sudo >/dev/null 2>&1; then
    sudo usermod -aG "$GROUP_NAME" node || true
  else
    usermod -aG "$GROUP_NAME" node || true
  fi

  echo "Current groups for 'node': $(id -nG node || true)"
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

# If a Node.js project exists, install dependencies as the non-root `node` user
if [ -f "package.json" ]; then
  echo "package.json found — installing npm dependencies as 'node'..."
  if [ "$(id -u)" -eq 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
      sudo -u node npm install --silent --no-audit --no-fund
    else
      su -s /bin/bash node -c "npm install --silent --no-audit --no-fund"
    fi
  else
    npm install --silent --no-audit --no-fund
  fi
else
  echo "No package.json found; skipping npm install."
fi

echo "Devcontainer post-create steps complete."

