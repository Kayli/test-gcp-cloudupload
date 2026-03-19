# ── Cloud Run service — FastAPI API only ─────────────────────────────────────
#
# The UI is served separately from GCS + CDN (see cdn.tf / storage.tf).
# deploy.sh builds and pushes the API image first, then passes its digest
# to `terraform apply -var api_image=<url>` so Terraform always owns the
# full resource state — no placeholder image, no lifecycle hacks.
#
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

    # Cloud SQL Auth Proxy socket — Cloud Run manages the proxy automatically.
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }

    containers {
      image = var.api_image

      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      # ── Non-sensitive config ──────────────────────────────────────────────
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.uploads.name
      }

      # Allow CORS from the CDN nip.io address.
      env {
        name  = "CORS_ORIGINS"
        value = "http://${google_compute_global_address.ui_ip.address}.nip.io"
      }

      # ── Secrets injected from Secret Manager ─────────────────────────────
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "GOOGLE_OAUTH_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.oauth_client_id.secret_id
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

  depends_on = [
    google_project_service.apis,
    google_sql_database_instance.main,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_version.oauth_client_id,
    google_service_account.api,
    google_compute_global_address.ui_ip,
  ]
}

# Public (unauthenticated) access — auth is enforced at the app layer.
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
