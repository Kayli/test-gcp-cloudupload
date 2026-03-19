# ── Secret Manager ────────────────────────────────────────────────────────────
# Sensitive values are stored in Secret Manager and injected into Cloud Run
# as environment variables at runtime (never baked into the container image).

resource "google_secret_manager_secret" "db_password" {
  project   = var.project_id
  secret_id = "${local.app_name}-db-password"
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.db_password
}

resource "google_secret_manager_secret" "oauth_client_id" {
  project   = var.project_id
  secret_id = "${local.app_name}-oauth-client-id"
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "oauth_client_id" {
  secret      = google_secret_manager_secret.oauth_client_id.id
  secret_data = var.google_oauth_client_id
}
