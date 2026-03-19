#!/usr/bin/env bash
# =============================================================================
# scripts/deploy.sh — Build and deploy Docstore to GCP
# =============================================================================
#
# Prerequisites (all available inside the devcontainer):
#   - gcloud  (authenticated — GOOGLE_APPLICATION_CREDENTIALS is set)
#   - docker  (logged in to Artifact Registry — run once: gcloud auth configure-docker)
#   - terraform >= 1.6
#   - gsutil  (bundled with gcloud SDK)
#
# Usage:
#   ./scripts/deploy.sh [--skip-terraform] [--skip-api] [--skip-ui]
#
# The script auto-discovers PROJECT_ID from the service-account key file.
# Everything else comes from Terraform outputs after `terraform apply`.
# =============================================================================
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
BOLD='\033[1m'; RESET='\033[0m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
log()  { echo -e "${CYAN}[deploy]${RESET} $*"; }
ok()   { echo -e "${GREEN}[deploy]${RESET} ✓ $*"; }
warn() { echo -e "${YELLOW}[deploy]${RESET} ⚠ $*"; }
die()  { echo -e "${RED}[deploy]${RESET} ✗ $*" >&2; exit 1; }

# ── Flags ─────────────────────────────────────────────────────────────────────
SKIP_TERRAFORM=false
SKIP_API=false
SKIP_UI=false
for arg in "$@"; do
  case "$arg" in
    --skip-terraform) SKIP_TERRAFORM=true ;;
    --skip-api)       SKIP_API=true ;;
    --skip-ui)        SKIP_UI=true ;;
    *) die "Unknown argument: $arg" ;;
  esac
done

# ── Workspace root ────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── Discover project from SA key ─────────────────────────────────────────────
SA_KEY="${GOOGLE_APPLICATION_CREDENTIALS:-/workspaces/.secrets/gcp-sa-key.json}"
[[ -f "$SA_KEY" ]] || die "GCP service-account key not found at $SA_KEY"
PROJECT_ID="$(python3 -c "import json,sys; d=json.load(open('$SA_KEY')); print(d['project_id'])")"
log "Project: ${BOLD}${PROJECT_ID}${RESET}"

# Activate the service account so gcloud / gsutil / docker use it
gcloud auth activate-service-account --key-file="$SA_KEY" --quiet
gcloud config set project "$PROJECT_ID" --quiet

# ── Shared config ─────────────────────────────────────────────────────────────
TF_DIR="$REPO_ROOT/terraform"
TF_STATE_BUCKET="${PROJECT_ID}-terraform-state"
TF_STATE_PREFIX="docstore/prod"
TFVARS="$TF_DIR/terraform.tfvars"
[[ -f "$TFVARS" ]] || die "terraform.tfvars not found at $TFVARS — copy terraform.tfvars.example and fill it in"

# Derive AR host and image repo from tfvars (available before terraform runs)
_region=$(grep -E '^region\s*=' "$TFVARS" | head -1 | sed 's/.*=\s*"//;s/".*//' || echo "us-central1")
_project=$(grep -E '^project_id\s*=' "$TFVARS" | head -1 | sed 's/.*=\s*"//;s/".*//')
AR_HOST="${_region}-docker.pkg.dev"
IMAGE_REPO="${AR_HOST}/${_project}/docstore-images"
log "Image repo: $IMAGE_REPO"

gcloud auth configure-docker "$AR_HOST" --quiet

# ── Build tag ─────────────────────────────────────────────────────────────────
BUILD_TAG="${DEPLOY_TAG:-$(date +%Y%m%d-%H%M%S)}"
log "Build tag: $BUILD_TAG"

# ── Phase 1: Build + push API image (must happen before terraform apply) ──────
API_IMAGE="${IMAGE_REPO}/docstore-api:${BUILD_TAG}"

if [[ "$SKIP_API" == true ]]; then
  warn "Skipping API build (--skip-api) — reusing image from Terraform state…"
  API_IMAGE="$(terraform -chdir="$TF_DIR" output -raw api_image 2>/dev/null || echo "${IMAGE_REPO}/docstore-api:latest")"
else
  log "Building API image…"
  docker build \
    --file backend/Dockerfile.api \
    --tag "$API_IMAGE" \
    --tag "${IMAGE_REPO}/docstore-api:latest" \
    .

  log "Pushing API image…"
  docker push "$API_IMAGE"
  docker push "${IMAGE_REPO}/docstore-api:latest"
  ok "API image pushed → $API_IMAGE"
fi

# ── Terraform init + apply (image URL is now known) ───────────────────────────
if [[ "$SKIP_TERRAFORM" == true ]]; then
  warn "Skipping Terraform (--skip-terraform)"
else
  log "Running Terraform (api_image=${API_IMAGE})…"

  terraform -chdir="$TF_DIR" init \
    -backend-config="bucket=${TF_STATE_BUCKET}" \
    -backend-config="prefix=${TF_STATE_PREFIX}" \
    -input=false -reconfigure

  terraform -chdir="$TF_DIR" apply \
    -var-file="$TFVARS" \
    -var "api_image=${API_IMAGE}" \
    -auto-approve \
    -input=false

  ok "Terraform apply complete"
fi

# ── Read Terraform outputs ────────────────────────────────────────────────────
log "Reading Terraform outputs…"
tf_output() { terraform -chdir="$TF_DIR" output -raw "$1" 2>/dev/null; }

API_URL="$(tf_output api_url)"
UI_URL="$(tf_output ui_url)"
UI_BUCKET="$(tf_output gcs_ui_bucket)"

log "  API URL   : $API_URL"
log "  UI URL    : $UI_URL"
log "  UI bucket : $UI_BUCKET"

# ── Phase 2: Build UI and upload to GCS ──────────────────────────────────────
if [[ "$SKIP_UI" == true ]]; then
  warn "Skipping UI build + upload (--skip-ui)"
else
  log "Building UI image (VITE_API_URL=${API_URL})…"
  UI_IMAGE="${IMAGE_REPO}/docstore-ui:${BUILD_TAG}"

  docker build \
    --file frontend/Dockerfile.ui \
    --build-arg VITE_API_URL="$API_URL" \
    --tag "$UI_IMAGE" \
    .

  log "Extracting built static files from UI image…"
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"; docker rm -f tmp-ui-extract 2>/dev/null || true' EXIT

  docker create --name tmp-ui-extract "$UI_IMAGE"
  docker cp tmp-ui-extract:/app/public/. "$TMP_DIR/"
  docker rm -f tmp-ui-extract

  log "Uploading static files to gs://${UI_BUCKET}/…"
  gsutil -m rsync -R -d "$TMP_DIR/" "gs://${UI_BUCKET}/"

  # Set cache-control headers: HTML no-cache, assets long-lived
  gsutil -m setmeta -h "Cache-Control:no-cache, no-store, must-revalidate" \
    "gs://${UI_BUCKET}/**/*.html" 2>/dev/null || true
  gsutil -m setmeta -h "Cache-Control:public, max-age=31536000, immutable" \
    "gs://${UI_BUCKET}/assets/**" 2>/dev/null || true

  log "Invalidating CDN cache…"
  gcloud compute url-maps invalidate-cdn-cache docstore-ui \
    --path "/*" \
    --project "$PROJECT_ID" \
    --async \
    --quiet 2>/dev/null || warn "CDN invalidation skipped (CDN may still be warming up)"

  ok "UI deployed → gs://${UI_BUCKET}/"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║           Deployment complete! 🚀             ║${RESET}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${BOLD}UI (nip.io):${RESET}  ${CYAN}${UI_URL}${RESET}"
echo -e "  ${BOLD}API:${RESET}          ${CYAN}${API_URL}${RESET}"
echo ""
warn "CDN propagation may take 1-2 min. If the page is blank, wait a moment and refresh."
