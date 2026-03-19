# ── Static global IP for the CDN load balancer ───────────────────────────────
resource "google_compute_global_address" "ui_ip" {
  project    = var.project_id
  name       = "${local.app_name}-ui-ip"
  depends_on = [google_project_service.apis]
}

# ── Backend bucket — CDN pulls from the GCS UI bucket ────────────────────────
resource "google_compute_backend_bucket" "ui" {
  project     = var.project_id
  name        = "${local.app_name}-ui-backend"
  bucket_name = google_storage_bucket.ui.name
  enable_cdn  = true

  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 3600
    client_ttl        = 3600
    negative_caching  = true
  }
}

# ── URL map: all traffic → UI backend bucket ──────────────────────────────────
resource "google_compute_url_map" "ui" {
  project         = var.project_id
  name            = "${local.app_name}-ui"
  default_service = google_compute_backend_bucket.ui.id
}

# ── HTTP target proxy + global forwarding rule ────────────────────────────────
resource "google_compute_target_http_proxy" "ui" {
  project = var.project_id
  name    = "${local.app_name}-ui-http"
  url_map = google_compute_url_map.ui.id
}

resource "google_compute_global_forwarding_rule" "ui_http" {
  project    = var.project_id
  name       = "${local.app_name}-ui-http"
  target     = google_compute_target_http_proxy.ui.id
  ip_address = google_compute_global_address.ui_ip.address
  port_range = "80"
}
