# ── Workload Identity Federation (WIF) for GitHub Actions ────────────────────
#
# Allows GitHub Actions to authenticate to GCP without storing long-lived
# service-account keys.  The CD workflow impersonates the `deployer` service
# account to push images to Artifact Registry, deploy Cloud Run revisions,
# upload the UI bundle to GCS, and invalidate the CDN cache.
#
# One-time setup after `terraform apply`:
#   1.  Run:  terraform output workload_identity_provider
#             terraform output deployer_service_account
#   2.  Add to the GitHub repository (Settings → Secrets and variables):
#         Secrets:    GCP_WIF_PROVIDER  ← workload_identity_provider value
#                     GCP_SA_EMAIL      ← deployer_service_account value
#         Variables:  GCP_PROJECT_ID    ← your GCP project ID
#                     GCP_IMAGE_REPO    ← terraform output image_repo
#                     GCP_UI_BUCKET     ← terraform output gcs_ui_bucket

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "${local.app_name}-github"
  display_name              = "GitHub Actions"
  description               = "WIF pool — GitHub Actions CI/CD for ${local.app_name}"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  # Map GitHub OIDC token claims to Google IAM attributes.
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # Restrict token acceptance to the configured repository.
  # This prevents tokens from other repos from impersonating the deployer SA.
  attribute_condition = "attribute.repository == '${var.github_repo}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# ── Deployer service account ──────────────────────────────────────────────────

resource "google_service_account" "deployer" {
  project      = var.project_id
  account_id   = "${local.app_name}-deployer"
  display_name = "Docstore GitHub Actions deployer"
  description  = "Impersonated by GitHub Actions WIF to build and deploy"
}

# Allow GitHub Actions (via WIF) to impersonate the deployer SA.
resource "google_service_account_iam_member" "deployer_wif_binding" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# Push images to Artifact Registry.
resource "google_project_iam_member" "deployer_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Create and update Cloud Run revisions.
resource "google_project_iam_member" "deployer_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Required so the deployer can specify the API service account when deploying
# Cloud Run (gcloud run deploy --service-account=... checks this binding).
resource "google_service_account_iam_member" "deployer_act_as_api" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

# Upload static UI files and manage objects in the UI bucket.
resource "google_storage_bucket_iam_member" "deployer_ui_writer" {
  bucket = google_storage_bucket.ui.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.deployer.email}"
}

# Invalidate the CDN cache after a UI deploy
# (requires compute.urlMaps.invalidateCache, included in loadBalancingAdmin).
resource "google_project_iam_member" "deployer_lb_admin" {
  project = var.project_id
  role    = "roles/compute.loadBalancingAdmin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}
