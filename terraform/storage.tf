# ── GCS bucket for file uploads (private — accessed via signed URLs) ──────────
resource "google_storage_bucket" "uploads" {
  project  = var.project_id
  name     = "${var.project_id}-${local.app_name}-uploads"
  location = var.region

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = false
  }

  # Delete objects after 1 year — adjust per retention policy.
  lifecycle_rule {
    condition { age = 365 }
    action    { type = "Delete" }
  }

  # CORS: browsers PUT directly to GCS using signed URLs.
  cors {
    origin          = ["*"]
    method          = ["PUT", "GET", "HEAD", "OPTIONS"]
    response_header = ["Content-Type", "Content-Length", "Authorization"]
    max_age_seconds = 3600
  }

  labels     = local.labels
  depends_on = [google_project_service.apis]
}

# ── GCS bucket for the React UI static files (public) ────────────────────────
resource "google_storage_bucket" "ui" {
  project  = var.project_id
  name     = "${var.project_id}-${local.app_name}-ui"
  location = var.region

  uniform_bucket_level_access = true

  # SPA routing: both main page and 404s serve index.html.
  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"
  }

  labels     = local.labels
  depends_on = [google_project_service.apis]
}

# Make the UI bucket publicly readable (static website hosting).
resource "google_storage_bucket_iam_member" "ui_public" {
  bucket = google_storage_bucket.ui.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}
