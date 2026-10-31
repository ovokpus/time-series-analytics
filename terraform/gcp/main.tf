provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_secret_manager_secret" "var_influx_token" {
  secret_id = "tsa-var-influx-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "var_influx_token" {
  secret      = google_secret_manager_secret.var_influx_token.id
  secret_data = var.influx_token
}

resource "google_secret_manager_secret" "var_grafana_admin_password" {
  secret_id = "tsa-var-grafana-admin-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "var_grafana_admin_password" {
  secret      = google_secret_manager_secret.var_grafana_admin_password.id
  secret_data = var.grafana_admin_password
}

module "registry" {
  source        = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/gcp/artifact-registry?ref=tf-modules-v0.1.0"
  project_id    = var.project_id
  region        = var.region
  repository_id = "tsa"
}

module "grafana" {
  source      = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/gcp/cloud-run-service?ref=tf-modules-v0.1.0"
  project_id  = var.project_id
  region      = var.region
  name        = "tsa-grafana"
  image       = "${module.registry.repository_url}/grafana:${var.image_tag}"
  port        = 3000
  memory      = "1Gi"
  health_path = "/api/health"
  env = {
    INFLUX_URL                                = var.influx_url
    INFLUX_ORG                                = var.influx_org
    INFLUX_AIR_BUCKET                         = "air-quality"
    GF_AUTH_ANONYMOUS_ENABLED                 = "true"
    GF_AUTH_ANONYMOUS_ORG_ROLE                = "Viewer"
    GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH = "/var/lib/grafana/dashboards/air-quality.json"
  }
  secret_env = {
    INFLUX_TOKEN               = google_secret_manager_secret.var_influx_token.secret_id
    GF_SECURITY_ADMIN_PASSWORD = google_secret_manager_secret.var_grafana_admin_password.secret_id
  }
}

module "api" {
  source      = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/gcp/cloud-run-service?ref=tf-modules-v0.1.0"
  project_id  = var.project_id
  region      = var.region
  name        = "tsa-api"
  image       = "${module.registry.repository_url}/app:${var.image_tag}"
  port        = 8000
  memory      = "512Mi"
  health_path = "/health"
  env = {
    INFLUX_URL            = var.influx_url
    INFLUX_ORG            = var.influx_org
    INFLUX_AIR_BUCKET     = "air-quality"
    INFLUX_WEATHER_BUCKET = "weather"
    GRAFANA_PUBLIC_URL    = module.grafana.url
  }
  secret_env = {
    INFLUX_TOKEN = google_secret_manager_secret.var_influx_token.secret_id
  }
}

module "frontend" {
  source      = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/gcp/cloud-run-service?ref=tf-modules-v0.1.0"
  project_id  = var.project_id
  region      = var.region
  name        = "tsa-frontend"
  image       = "${module.registry.repository_url}/frontend:${var.image_tag}"
  port        = 80
  memory      = "512Mi"
  health_path = "/"
  env = {
    API_UPSTREAM = module.api.url
  }
  secret_env = {}
}

module "seed" {
  source     = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/gcp/cloud-run-job?ref=tf-modules-v0.1.0"
  project_id = var.project_id
  region     = var.region
  name       = "tsa-seed"
  image      = "${module.registry.repository_url}/app:${var.image_tag}"
  memory     = "1Gi"
  command    = ["python", "-m", "tsa.seed"]
  env = {
    INFLUX_URL            = var.influx_url
    INFLUX_ORG            = var.influx_org
    INFLUX_AIR_BUCKET     = "air-quality"
    INFLUX_WEATHER_BUCKET = "weather"
    SYNTH_STATIONS        = "Aotizhongxin,Wanliu,Dongsi"
    SYNTH_HOURS           = "720"
  }
  secret_env = {
    INFLUX_TOKEN = google_secret_manager_secret.var_influx_token.secret_id
  }
}
