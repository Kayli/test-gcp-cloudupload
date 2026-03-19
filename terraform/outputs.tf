output "api_url" {
  value       = google_cloud_run_v2_service.api.uri
  description = "Cloud Run API URL (HTTPS)"
}

output "api_image" {
  value       = var.api_image
  description = "API container image deployed to Cloud Run"
}

output "ui_ip" {
  value       = google_compute_global_address.ui_ip.address
  description = "CDN load balancer public IP"
}

output "ui_url" {
  value       = "http://${google_compute_global_address.ui_ip.address}.nip.io"
  description = "UI URL — nip.io maps <ip>.nip.io → <ip>, no DNS setup needed"
}

output "gcs_uploads_bucket" {
  value       = google_storage_bucket.uploads.name
  description = "GCS bucket for file uploads (private, signed URLs)"
}

output "gcs_ui_bucket" {
  value       = google_storage_bucket.ui.name
  description = "GCS bucket hosting the React UI static files"
}

output "cloud_sql_connection_name" {
  value       = google_sql_database_instance.main.connection_name
  description = "Cloud SQL connection name — use with Cloud SQL Auth Proxy for local access"
}

output "image_repo" {
  value       = local.image_repo
  description = "Artifact Registry Docker repo URL (prefix for image tags)"
}
