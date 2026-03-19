variable "project_id" {
  description = "GCP project ID (e.g. my-gcp-project-123)"
  type        = string
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment label (prod, staging, etc.)"
  type        = string
  default     = "prod"
}

variable "google_oauth_client_id" {
  description = "Google OAuth 2.0 Client ID for the web application"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "PostgreSQL password for the application database user"
  type        = string
  sensitive   = true
}

variable "cloud_run_min_instances" {
  description = "Minimum Cloud Run instances (0 = scale to zero)"
  type        = number
  default     = 0
}

variable "cloud_run_max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 10
}

variable "api_image" {
  description = "Full Artifact Registry image URL for the API (e.g. us-central1-docker.pkg.dev/proj/repo/docstore-api:20260101-120000). Passed by deploy.sh after the image is pushed."
  type        = string
}

variable "deletion_protection" {
  description = "Protect the Cloud SQL instance from accidental deletion (set to false to allow terraform destroy)"
  type        = bool
  default     = true
}
