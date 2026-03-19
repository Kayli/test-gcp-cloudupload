# ── DATABASE_URL ──────────────────────────────────────────────────────────────
# Full postgresql:// URL injected into Cloud Run at runtime.
# Cloud Run connects to Cloud SQL via the built-in Auth Proxy Unix socket.
resource "google_secret_manager_secret" "database_url" {
  project   = var.project_id
  secret_id = "${local.app_name}-database-url"
  labels    = local.labels

  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id
  # postgresql://user:pass@/dbname?host=/cloudsql/project:region:instance
  secret_data = "postgresql://docstore:${var.db_password}@/docstore?host=/cloudsql/${google_sql_database_instance.main.connection_name}"
}

# ── Google OAuth Client ID ────────────────────────────────────────────────────
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
