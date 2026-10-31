provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "this" {
  name     = "rg-tsa"
  location = var.location
}

module "acr" {
  source              = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/azure/acr?ref=tf-modules-v0.1.0"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  name                = "${var.name_prefix}acr"
}

module "env" {
  source              = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/azure/container-apps-env?ref=tf-modules-v0.1.0"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  name                = "cae-tsa"
  acr_id              = module.acr.id
}

module "grafana" {
  source              = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/azure/container-app?ref=tf-modules-v0.1.0"
  resource_group_name = azurerm_resource_group.this.name
  name                = "tsa-grafana"
  environment_id      = module.env.id
  identity_id         = module.env.identity_id
  registry_server     = module.acr.login_server
  image               = "${module.acr.login_server}/grafana:${var.image_tag}"
  port                = 3000
  env = {
    INFLUX_URL                                = var.influx_url
    INFLUX_ORG                                = var.influx_org
    INFLUX_AIR_BUCKET                         = "air-quality"
    GF_AUTH_ANONYMOUS_ENABLED                 = "true"
    GF_AUTH_ANONYMOUS_ORG_ROLE                = "Viewer"
    GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH = "/var/lib/grafana/dashboards/air-quality.json"
  }
  secret_env = {
    INFLUX_TOKEN               = var.influx_token
    GF_SECURITY_ADMIN_PASSWORD = var.grafana_admin_password
  }
}

module "api" {
  source              = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/azure/container-app?ref=tf-modules-v0.1.0"
  resource_group_name = azurerm_resource_group.this.name
  name                = "tsa-api"
  environment_id      = module.env.id
  identity_id         = module.env.identity_id
  registry_server     = module.acr.login_server
  image               = "${module.acr.login_server}/app:${var.image_tag}"
  port                = 8000
  env = {
    INFLUX_URL            = var.influx_url
    INFLUX_ORG            = var.influx_org
    INFLUX_AIR_BUCKET     = "air-quality"
    INFLUX_WEATHER_BUCKET = "weather"
    GRAFANA_PUBLIC_URL    = module.grafana.url
  }
  secret_env = {
    INFLUX_TOKEN = var.influx_token
  }
}

module "frontend" {
  source              = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/azure/container-app?ref=tf-modules-v0.1.0"
  resource_group_name = azurerm_resource_group.this.name
  name                = "tsa-frontend"
  environment_id      = module.env.id
  identity_id         = module.env.identity_id
  registry_server     = module.acr.login_server
  image               = "${module.acr.login_server}/frontend:${var.image_tag}"
  port                = 80
  env = {
    API_UPSTREAM = module.api.url
  }
  secret_env = {}
}

module "seed" {
  source              = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/azure/container-app-job?ref=tf-modules-v0.1.0"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  name                = "tsa-seed"
  environment_id      = module.env.id
  identity_id         = module.env.identity_id
  registry_server     = module.acr.login_server
  image               = "${module.acr.login_server}/app:${var.image_tag}"
  command             = ["python", "-m", "tsa.seed"]
  env = {
    INFLUX_URL            = var.influx_url
    INFLUX_ORG            = var.influx_org
    INFLUX_AIR_BUCKET     = "air-quality"
    INFLUX_WEATHER_BUCKET = "weather"
    SYNTH_STATIONS        = "Aotizhongxin,Wanliu,Dongsi"
    SYNTH_HOURS           = "720"
  }
  secret_env = {
    INFLUX_TOKEN = var.influx_token
  }
}
