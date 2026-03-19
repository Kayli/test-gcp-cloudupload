#!/usr/bin/env bash
# =============================================================================
# scripts/nuke.sh
#
# Full teardown — calls suspend-and-teardown.sh first, then permanently deletes
# the preserved resources: Cloud SQL instance and the uploads GCS bucket.
#
# Usage:
#   bash scripts/nuke.sh
# =============================================================================
set -euo pipefail

BOLD='\033[1m'; RESET='\033[0m'
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
log()  { echo -e "${CYAN}[nuke]${RESET} $*"; }
ok()   { echo -e "${GREEN}[nuke]${RESET} ✓ $*"; }
warn() { echo -e "${YELLOW}[nuke]${RESET} ⚠ $*"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SA_KEY="${GOOGLE_APPLICATION_CREDENTIALS:-/workspaces/.secrets/gcp-sa-key.json}"
PROJECT_ID="$(python3 -c "import json; print(json.load(open('$SA_KEY'))['project_id'])")"
SQL_INSTANCE="docstore-db-prod"

echo -e "${RED}${BOLD}"
echo "  ██████   ██████████   ██   ██  ██████   ████████"
echo "  ██  ███  ██           ██   ██ ██    ██  ██"
echo "  ██   ██  ████████     ████████ ██        ████████"
echo "  ██  ███  ██           ██   ██ ██    ██  ██"
echo "  ██████   ██████████   ██   ██  ██████   ████████"
echo -e "${RESET}"
echo -e "${RED}${BOLD}  !! THIS WILL PERMANENTLY DELETE EVERYTHING, INCLUDING YOUR DATA !!${RESET}"
echo ""
echo "  Uploads bucket:  gs://${PROJECT_ID}-docstore-uploads  (ALL FILES GONE)"
echo "  Cloud SQL:       ${SQL_INSTANCE}  (ALL DATABASE DATA GONE)"
echo ""
warn "There is no undo."
echo ""
read -r -p "Type 'delete everything' to confirm: " confirm
[[ "$confirm" == "delete everything" ]] || { warn "Aborted."; exit 0; }

# ── Step 1: run suspend-and-teardown (handles everything except SQL + uploads) ─
log "Running suspend-and-teardown.sh…"
# Pass "yes" automatically since we already confirmed above
echo "yes" | bash "$REPO_ROOT/scripts/suspend-and-teardown.sh"

# ── Step 2: delete uploads bucket ─────────────────────────────────────────────
log "Deleting uploads bucket gs://${PROJECT_ID}-docstore-uploads…"
gcloud storage rm -r "gs://${PROJECT_ID}-docstore-uploads" --quiet 2>/dev/null \
  && ok "Uploads bucket deleted" || warn "Uploads bucket already gone (skipping)"

# ── Step 3: permanently delete Cloud SQL ──────────────────────────────────────
log "Deleting Cloud SQL instance '${SQL_INSTANCE}'…"
gcloud sql instances delete "$SQL_INSTANCE" \
  --project="$PROJECT_ID" \
  --quiet \
  && ok "Cloud SQL deleted" || warn "Cloud SQL instance already gone (skipping)"

echo ""
echo -e "${GREEN}${BOLD}Everything is gone. GCP project '${PROJECT_ID}' is now empty.${RESET}"
