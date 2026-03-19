# ── Cloud SQL PostgreSQL instance ─────────────────────────────────────────────
#
# Cloud Run connects via the built-in Cloud SQL Auth Proxy (Unix socket at
# /cloudsql/PROJECT:REGION:INSTANCE) — no VPC connector needed.
#
resource "google_sql_database_instance" "main" {
  project          = var.project_id
  name             = "${local.app_name}-db-${var.environment}"
  region           = var.region
  database_version = "POSTGRES_16"

  settings {
    tier              = "db-f1-micro"   # smallest tier — upgrade for sustained load
    availability_type = "ZONAL"

    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 7
      }
    }

    ip_configuration {
      # Public IP is required so the Cloud SQL Auth Proxy can connect from Cloud Run.
      ipv4_enabled = true
    }

    database_flags {
      name  = "max_connections"
      value = "100"
    }
  }

  deletion_protection = var.deletion_protection
  depends_on          = [google_project_service.apis]
}

resource "google_sql_database" "app_db" {
  project  = var.project_id
  instance = google_sql_database_instance.main.name
  name     = "docstore"
}

resource "google_sql_user" "app_user" {
  project  = var.project_id
  instance = google_sql_database_instance.main.name
  name     = "docstore"
  password = var.db_password
}
