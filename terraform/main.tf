terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # GCS backend — bucket and prefix are passed via -backend-config in CI
  # or in a local backend.hcl file (never commit credentials to VCS).
  # See scripts/bootstrap-tf-state.sh to create the state bucket first.
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  app_name = "docstore"
  image_repo = "${var.region}-docker.pkg.dev/${var.project_id}/${local.app_name}-images"

  labels = {
    app         = local.app_name
    environment = var.environment
    managed_by  = "terraform"
  }
}
