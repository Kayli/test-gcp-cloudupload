# ── Cloud Run service ─────────────────────────────────────────────────────────
#
# Single service that hosts both the FastAPI backend and the pre-built
# React frontend (served as static files by FastAPI's StaticFiles mount).
#
# On first `terraform apply` the placeholder image is deployed.
# Subsequent image updates are done by the CD pipeline via `gcloud run deploy`
# and Terraform ignores the image field thereafter.

resource "google_cloud_run_v2_service" "api" {
  project  = var.project_id
  name     = "${local.app_name}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  labels   = local.labels

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }

    # Mount the Cloud SQL Auth Proxy Unix socket — Cloud Run manages the proxy
    # automatically; the app connects via host="/cloudsql/<instance-name>".
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }

    containers {
      # Placeholder image used only on the very first deploy.
      # The CD pipeline (`gcloud run deploy`) updates this on every push to main.
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        # Free CPU only while handling requests (scale-to-zero friendly)
        cpu_idle          = true
        startup_cpu_boost = true
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      # ── Non-sensitive config ────────────────────────────────────────────────
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.uploads.name
      }

      env {
        name  = "CLOUD_SQL_INSTANCE"
        value = google_sql_database_instance.main.connection_name
      }

      env {
        name  = "DB_USER"
        value = google_sql_user.app_user.name
      }

      env {
        name  = "DB_NAME"
        value = google_sql_database.app_db.name
      }

      # ── Secrets (injected from Secret Manager at runtime) ──────────────────
      env {
        name = "GOOGLE_OAUTH_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.oauth_client_id.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 3000
        }
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 10
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 3000
        }
        period_seconds    = 30
        timeout_seconds   = 5
        failure_threshold = 3
      }
    }
  }

  # Let the CD pipeline update the container image without Terraform reverting
  # it back to the placeholder on the next `terraform apply`.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_project_service.apis,
    google_sql_database_instance.main,
    google_secret_manager_secret_version.db_password,
    google_secret_manager_secret_version.oauth_client_id,
    google_service_account.api,
  ]
}

# Allow unauthenticated (public) traffic — authentication is handled at the app layer
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
