# ── Cloud SQL PostgreSQL instance ─────────────────────────────────────────────
#
# Cloud Run connects to Cloud SQL via the built-in Cloud SQL Auth Proxy
# (Unix socket at /cloudsql/PROJECT:REGION:INSTANCE) — no VPC connector needed.
# The instance has a public IP so it can also be reached from developer machines
# using the Cloud SQL Auth Proxy or Cloud Shell.

resource "google_sql_database_instance" "main" {
  project          = var.project_id
  name             = "${local.app_name}-db-${var.environment}"
  region           = var.region
  database_version = "POSTGRES_15"

  settings {
    # db-f1-micro is the smallest tier — suitable for low-traffic MVP.
    # Upgrade to db-g1-small or db-n1-standard-1 for sustained production load.
    tier              = "db-f1-micro"
    availability_type = "ZONAL" # change to REGIONAL for multi-zone HA

    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 7
      }
    }

    ip_configuration {
      # Public IP is required for Cloud SQL Auth Proxy connections from Cloud Run.
      # Access is restricted to the built-in proxy; direct TCP is locked down by default.
      ipv4_enabled = true
    }

    database_flags {
      name  = "max_connections"
      value = "100"
    }
  }

  # Prevent accidental deletion in production.
  # Run `terraform state rm google_sql_database_instance.main` before destroy.
  deletion_protection = true

  depends_on = [google_project_service.apis]
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
