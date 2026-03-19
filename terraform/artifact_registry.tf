resource "google_artifact_registry_repository" "app" {
  project       = var.project_id
  location      = var.region
  repository_id = "${local.app_name}-images"
  format        = "DOCKER"
  description   = "Docker images for ${local.app_name}"
  labels        = local.labels

  depends_on = [google_project_service.apis]
}
