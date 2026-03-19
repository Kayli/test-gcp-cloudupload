resource "google_storage_bucket" "uploads" {
  project  = var.project_id
  name     = "${var.project_id}-${local.app_name}-uploads"
  location = var.region

  # Uniform bucket-level access (no per-object ACLs)
  uniform_bucket_level_access = true

  # Objects are uploaded directly by clients via signed PUT URLs;
  # they are never publicly readable by default.
  public_access_prevention = "enforced"

  versioning {
    enabled = false
  }

  # Auto-delete objects after 1 year (adjust per retention policy)
  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }

  # CORS: allow browsers to PUT and GET objects using GCS signed URLs.
  # The browser sends the PUT directly to GCS (not through the API), so GCS
  # itself needs to allow cross-origin requests from all origins (the exact
  # origin is embedded in the signed URL).
  cors {
    origin          = ["*"]
    method          = ["PUT", "GET", "HEAD", "OPTIONS"]
    response_header = ["Content-Type", "Content-Length", "Authorization", "x-goog-signature", "x-goog-date"]
    max_age_seconds = 3600
  }

  labels     = local.labels
  depends_on = [google_project_service.apis]
}
