#!/usr/bin/env bash
# =============================================================================
# scripts/suspend-and-teardown.sh
#
# Suspends Cloud SQL (preserves data cheaply at ~$1.50/mo storage-only) and
# destroys everything else: Cloud Run, LB/CDN, GCS, Secret Manager, IAM,
# WIF, Artifact Registry, Terraform state bucket.
#
# Usage:
#   bash scripts/suspend-and-teardown.sh
# =============================================================================
set -euo pipefail

BOLD='\033[1m'; RESET='\033[0m'
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
log()  { echo -e "${CYAN}[teardown]${RESET} $*"; }
ok()   { echo -e "${GREEN}[teardown]${RESET} ✓ $*"; }
warn() { echo -e "${YELLOW}[teardown]${RESET} ⚠ $*"; }
die()  { echo -e "${RED}[teardown]${RESET} ✗ $*" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SA_KEY="${GOOGLE_APPLICATION_CREDENTIALS:-/workspaces/.secrets/gcp-sa-key.json}"
[[ -f "$SA_KEY" ]] || die "GCP SA key not found at $SA_KEY"
PROJECT_ID="$(python3 -c "import json; print(json.load(open('$SA_KEY'))['project_id'])")"

TF_DIR="$REPO_ROOT/terraform"
TFVARS="$TF_DIR/terraform.tfvars"
[[ -f "$TFVARS" ]] || die "terraform.tfvars not found — needed for destroy"

REGION="us-central1"
SQL_INSTANCE="docstore-db-prod"
TF_STATE_BUCKET="${PROJECT_ID}-terraform-state"
TF_STATE_PREFIX="docstore/prod"
AR_REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/docstore-images"

log "Project: ${BOLD}${PROJECT_ID}${RESET}"
echo ""
warn "This will DESTROY all prod infrastructure except Cloud SQL."
warn "Cloud SQL will be SUSPENDED (data kept, ~\$1.50/mo storage charge remains)."
echo ""
read -r -p "Type 'yes' to continue: " confirm
[[ "$confirm" == "yes" ]] || { warn "Aborted."; exit 0; }

gcloud auth activate-service-account --key-file="$SA_KEY" --quiet
gcloud config set project "$PROJECT_ID" --quiet

# ── 1. Suspend Cloud SQL ──────────────────────────────────────────────────────
log "Suspending Cloud SQL instance '${SQL_INSTANCE}'…"
gcloud sql instances patch "$SQL_INSTANCE" \
  --activation-policy=NEVER \
  --project="$PROJECT_ID" \
  --quiet
ok "Cloud SQL suspended"

# ── 2. Init Terraform ─────────────────────────────────────────────────────────
log "Initialising Terraform…"
terraform -chdir="$TF_DIR" init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="prefix=${TF_STATE_PREFIX}" \
  -input=false -reconfigure 2>&1 | tail -3

# ── 3. Remove SQL + AR resources from state so destroy doesn't touch them ─────
log "Detaching SQL, AR, and uploads bucket from Terraform state…"
for res in \
    google_sql_database_instance.main \
    google_sql_database.app_db \
    google_sql_user.app_user \
    google_artifact_registry_repository.app \
    google_storage_bucket.uploads \
    google_storage_bucket_iam_member.api_storage_admin; do
  terraform -chdir="$TF_DIR" state rm "$res" 2>/dev/null \
    && log "  detached $res" \
    || warn "  $res not in state (skipping)"
done

# ── 4. Delete AR images + repo (outside Terraform, must be empty to delete) ───
log "Deleting Artifact Registry images…"
gcloud artifacts docker images list "$AR_REPO/docstore-api" \
  --include-tags --format="value(version)" --quiet 2>/dev/null \
| while IFS= read -r digest; do
    [[ -z "$digest" ]] && continue
    gcloud artifacts docker images delete \
      "${AR_REPO}/docstore-api@${digest}" \
      --delete-tags --quiet 2>/dev/null || true
  done

log "Deleting Artifact Registry repo…"
gcloud artifacts repositories delete docstore-images \
  --location="$REGION" --project="$PROJECT_ID" --quiet 2>/dev/null \
  && ok "AR repo deleted" || warn "AR repo already gone (skipping)"

# ── 5. Empty UI GCS bucket so Terraform can delete it ────────────────────────
log "Emptying UI GCS bucket…"
gcloud storage rm -r "gs://${PROJECT_ID}-docstore-ui/**" --quiet 2>/dev/null \
  && log "  emptied gs://${PROJECT_ID}-docstore-ui" \
  || warn "  gs://${PROJECT_ID}-docstore-ui already empty (skipping)"

# ── 6. Terraform destroy everything else ─────────────────────────────────────
API_IMAGE="$(terraform -chdir="$TF_DIR" output -raw api_image 2>/dev/null || echo placeholder)"
log "Destroying remaining infrastructure (this may take a few minutes)…"
terraform -chdir="$TF_DIR" destroy \
  -var-file="$TFVARS" \
  -var "api_image=${API_IMAGE}" \
  -var "deletion_protection=false" \
  -auto-approve -input=false
ok "Terraform destroy complete"

# ── 7. Delete Terraform state bucket (bootstrap resource, outside TF state) ───
log "Deleting Terraform state bucket…"
gcloud storage rm -r "gs://${TF_STATE_BUCKET}" --quiet 2>/dev/null \
  && ok "State bucket deleted" || warn "State bucket already gone (skipping)"

echo ""
echo -e "${GREEN}${BOLD}Teardown complete!${RESET}"
echo ""
echo "  Cloud SQL '${SQL_INSTANCE}' is SUSPENDED — data preserved."
echo "  Cost while suspended: ~\$1.50/mo (10 GB SSD storage)."
echo ""
echo "  Uploads bucket 'gs://${PROJECT_ID}-docstore-uploads' is PRESERVED."
echo "  Delete it manually when ready:"
echo "    gcloud storage rm -r gs://${PROJECT_ID}-docstore-uploads"
echo ""
echo "  To delete Cloud SQL permanently when ready:"
echo "    gcloud sql instances delete ${SQL_INSTANCE} --project=${PROJECT_ID}"
echo ""
echo "  To resume Cloud SQL later:"
echo "    gcloud sql instances patch ${SQL_INSTANCE} --activation-policy=ALWAYS --project=${PROJECT_ID}"
