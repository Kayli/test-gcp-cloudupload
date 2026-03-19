#!/usr/bin/env bash
# bootstrap-tf-state.sh
# ─────────────────────────────────────────────────────────────────────────────
# One-time setup script: creates the GCS bucket that Terraform uses to store
# its state, and enables the minimum APIs needed before `terraform init`.
#
# Run this ONCE before running `terraform init` in a new GCP project.
# After this script succeeds, continue with the Terraform workflow below.
#
# Usage:
#   export GCP_PROJECT_ID=my-gcp-project-id
#   export GCP_REGION=us-central1          # optional, defaults to us-central1
#   bash scripts/bootstrap-tf-state.sh
#
# Prerequisites:
#   - gcloud CLI installed and authenticated: `gcloud auth login`
#   - Owner / Editor role on the GCP project (for API enablement + bucket creation)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID before running this script}"
REGION="${GCP_REGION:-us-central1}"

# State bucket name must be globally unique — use the project ID as prefix.
STATE_BUCKET="${PROJECT}-terraform-state"

echo "==> Bootstrapping Terraform state for project: ${PROJECT}"
echo "    Region  : ${REGION}"
echo "    Bucket  : gs://${STATE_BUCKET}"
echo ""

# ── 1. Set the active project ─────────────────────────────────────────────────
gcloud config set project "${PROJECT}"

# ── 2. Enable APIs needed before Terraform can run ───────────────────────────
# artifactregistry is included here because deploy.sh pushes images BEFORE
# terraform apply (which would otherwise enable it too late).
echo "==> Enabling bootstrap APIs…"
gcloud services enable \
    cloudresourcemanager.googleapis.com \
    storage.googleapis.com \
    artifactregistry.googleapis.com \
    --quiet

# ── 3. Create the Terraform state bucket ─────────────────────────────────────
if gcloud storage buckets describe "gs://${STATE_BUCKET}" &>/dev/null; then
    echo "==> State bucket already exists — skipping creation."
else
    echo "==> Creating state bucket gs://${STATE_BUCKET}…"
    gcloud storage buckets create "gs://${STATE_BUCKET}" \
        --location="${REGION}" \
        --uniform-bucket-level-access \
        --public-access-prevention
fi

# Enable versioning so accidental state corruption can be rolled back.
gcloud storage buckets update "gs://${STATE_BUCKET}" --versioning

# ── 4. Create the Artifact Registry Docker repository ────────────────────────
# deploy.sh pushes the API image before terraform apply runs, so the repo must
# exist beforehand.  This is idempotent — it skips creation if already present.
AR_REPO="docstore-images"
if gcloud artifacts repositories describe "${AR_REPO}" \
      --location="${REGION}" &>/dev/null; then
    echo "==> Artifact Registry repo '${AR_REPO}' already exists — skipping."
else
    echo "==> Creating Artifact Registry repo '${AR_REPO}'…"
    gcloud artifacts repositories create "${AR_REPO}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="Docker images for docstore" \
        --quiet
fi

echo ""
echo "✓ Bootstrap complete.  Next steps:"
echo ""
echo "  1. Copy the example vars file and fill in your values:"
echo "       cp terraform/terraform.tfvars.example terraform/terraform.tfvars"
echo "       \$EDITOR terraform/terraform.tfvars"
echo ""
echo "  2. Initialise Terraform with the remote state bucket:"
echo "       terraform -chdir=terraform init \\"
echo "         -backend-config=\"bucket=${STATE_BUCKET}\" \\"
echo "         -backend-config=\"prefix=docstore/prod\""
echo ""
echo "  3. Preview and apply infrastructure:"
echo "       terraform -chdir=terraform plan"
echo "       terraform -chdir=terraform apply"
echo ""
echo "  4. Copy the outputs into GitHub repository secrets / variables:"
echo "       terraform -chdir=terraform output"
