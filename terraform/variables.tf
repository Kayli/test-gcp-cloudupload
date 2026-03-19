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

variable "github_repo" {
  description = "GitHub repository in owner/repo format — used to scope WIF tokens (e.g. myorg/myrepo)"
  type        = string
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
