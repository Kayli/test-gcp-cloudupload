# ── Infrastructure outputs ────────────────────────────────────────────────────
# After running `terraform apply`, copy these values into GitHub repository
# variables/secrets (Settings → Secrets and variables → Actions).

output "api_url" {
  value       = google_cloud_run_v2_service.api.uri
  description = "Cloud Run service URL — set as APP_URL in tests / CORS_ORIGINS in the app"
}

output "gcs_bucket" {
  value       = google_storage_bucket.uploads.name
  description = "GCS bucket name — already set as GCS_BUCKET env var on Cloud Run"
}

output "image_repo" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
  description = "Artifact Registry repo URL — set as GCP_IMAGE_REPO GitHub variable"
}

output "cloud_sql_instance_connection_name" {
  value       = google_sql_database_instance.main.connection_name
  description = "Cloud SQL connection name — already set as CLOUD_SQL_INSTANCE env var on Cloud Run"
}

output "workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "WIF provider resource name — set as GCP_WIF_PROVIDER GitHub secret"
}

output "deployer_service_account" {
  value       = google_service_account.deployer.email
  description = "Deployer SA email — set as GCP_SA_EMAIL GitHub secret"
}

output "cloud_run_service_name" {
  value       = google_cloud_run_v2_service.api.name
  description = "Cloud Run service name — set as GCP_SERVICE_NAME GitHub variable"
}
