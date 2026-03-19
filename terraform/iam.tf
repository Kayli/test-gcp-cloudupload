# ── Cloud Run service account ─────────────────────────────────────────────────

resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "${local.app_name}-api"
  display_name = "Docstore API runtime (Cloud Run)"
}

# Sign GCS blobs for v4 signed upload/download URLs
resource "google_service_account_iam_member" "api_self_sign" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.api.email}"
}

# Read and write objects in the uploads bucket
resource "google_storage_bucket_iam_member" "api_storage_admin" {
  bucket = google_storage_bucket.uploads.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

# Access secrets from Secret Manager
resource "google_project_iam_member" "api_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Connect to Cloud SQL via the built-in Auth Proxy
resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# ── GitHub Actions Workload Identity Federation ───────────────────────────────
# Lets GitHub Actions authenticate to GCP using short-lived OIDC tokens
# — no long-lived service account keys stored in GitHub secrets.

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
  description               = "WIF pool for GitHub Actions CD deployments"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Actions OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # Only tokens from this specific GitHub repository are accepted.
  attribute_condition = "attribute.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# ── Deployer service account (impersonated by GitHub Actions) ─────────────────

resource "google_service_account" "deployer" {
  project      = var.project_id
  account_id   = "${local.app_name}-deployer"
  display_name = "Docstore CD deployer (impersonated by GitHub Actions WIF)"
}

# Allow the GitHub Actions WIF principal to impersonate the deployer SA
resource "google_service_account_iam_member" "github_wif_impersonate" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# Deployer needs to push images and update the Cloud Run service
resource "google_project_iam_member" "deployer_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Required so the deployer can set the Cloud Run service account on the service
resource "google_service_account_iam_member" "deployer_act_as_api_sa" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
