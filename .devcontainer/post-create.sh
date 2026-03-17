#!/usr/bin/env bash
set -e

if [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
  echo "Found GOOGLE_APPLICATION_CREDENTIALS at $GOOGLE_APPLICATION_CREDENTIALS"
  echo "Run: gcloud auth activate-service-account --key-file=\$GOOGLE_APPLICATION_CREDENTIALS"
else
  echo "⚠️  WARNING: No GCP credentials found at $GOOGLE_APPLICATION_CREDENTIALS"
  echo "   To enable gcloud auth, place your service-account key at /workspaces/.secrets/gcloud-key"
  echo "   and re-open the devcontainer (or uncomment the mounts entry in devcontainer.json)."
fi

echo "Devcontainer post-create steps complete."
