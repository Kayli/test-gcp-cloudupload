# ── Cloud Run service account ─────────────────────────────────────────────────
resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "${local.app_name}-api"
  display_name = "Docstore API runtime (Cloud Run)"
}

# Sign GCS blobs for v4 presigned upload/download URLs.
resource "google_service_account_iam_member" "api_self_sign" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.api.email}"
}

# Read and write objects in the uploads bucket.
resource "google_storage_bucket_iam_member" "api_storage_admin" {
  bucket = google_storage_bucket.uploads.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

# Access secrets from Secret Manager.
resource "google_project_iam_member" "api_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Connect to Cloud SQL via the built-in Auth Proxy.
resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}
