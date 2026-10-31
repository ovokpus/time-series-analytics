provider "aws" {
  region = var.region
  default_tags {
    tags = { app = "time-series-analytics", managed-by = "terraform" }
  }
}

# Default VPC keeps the example small. Use a dedicated VPC for production.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "app" {
  name_prefix = "tsa-app-"
  description = "time-series-analytics tasks"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "app_80" {
  security_group_id = aws_security_group.app.id
  description       = "load balancer to tasks"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = data.aws_vpc.default.cidr_block
}

resource "aws_vpc_security_group_ingress_rule" "app_3000" {
  security_group_id = aws_security_group.app.id
  description       = "load balancer to tasks"
  ip_protocol       = "tcp"
  from_port         = 3000
  to_port           = 3000
  cidr_ipv4         = data.aws_vpc.default.cidr_block
}

resource "aws_vpc_security_group_ingress_rule" "app_8000" {
  security_group_id = aws_security_group.app.id
  description       = "load balancer to tasks"
  ip_protocol       = "tcp"
  from_port         = 8000
  to_port           = 8000
  cidr_ipv4         = data.aws_vpc.default.cidr_block
}

resource "aws_vpc_security_group_egress_rule" "app_all" {
  security_group_id = aws_security_group.app.id
  description       = "outbound (image pulls, database, external APIs)"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_ecs_cluster" "this" {
  name = "tsa"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_secretsmanager_secret" "var_influx_token" {
  name_prefix = "tsa-var-influx-token-"
}

resource "aws_secretsmanager_secret_version" "var_influx_token" {
  secret_id     = aws_secretsmanager_secret.var_influx_token.id
  secret_string = var.influx_token
}

resource "aws_secretsmanager_secret" "var_grafana_admin_password" {
  name_prefix = "tsa-var-grafana-admin-password-"
}

resource "aws_secretsmanager_secret_version" "var_grafana_admin_password" {
  secret_id     = aws_secretsmanager_secret.var_grafana_admin_password.id
  secret_string = var.grafana_admin_password
}

module "ecr" {
  source = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/aws/ecr?ref=tf-modules-v0.1.0"
  prefix = "tsa"
  names  = ["app", "frontend", "grafana"]
}

module "grafana" {
  source             = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/aws/express-service?ref=tf-modules-v0.1.0"
  name               = "tsa-grafana"
  cluster            = aws_ecs_cluster.this.name
  image              = "${module.ecr.repository_urls["grafana"]}:${var.image_tag}"
  port               = 3000
  health_path        = "/api/health"
  subnet_ids         = data.aws_subnets.default.ids
  security_group_ids = [aws_security_group.app.id]
  env = {
    INFLUX_URL                                = var.influx_url
    INFLUX_ORG                                = var.influx_org
    INFLUX_AIR_BUCKET                         = "air-quality"
    GF_AUTH_ANONYMOUS_ENABLED                 = "true"
    GF_AUTH_ANONYMOUS_ORG_ROLE                = "Viewer"
    GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH = "/var/lib/grafana/dashboards/air-quality.json"
  }
  secret_env = {
    INFLUX_TOKEN               = aws_secretsmanager_secret.var_influx_token.arn
    GF_SECURITY_ADMIN_PASSWORD = aws_secretsmanager_secret.var_grafana_admin_password.arn
  }
}

module "api" {
  source             = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/aws/express-service?ref=tf-modules-v0.1.0"
  name               = "tsa-api"
  cluster            = aws_ecs_cluster.this.name
  image              = "${module.ecr.repository_urls["app"]}:${var.image_tag}"
  port               = 8000
  health_path        = "/health"
  subnet_ids         = data.aws_subnets.default.ids
  security_group_ids = [aws_security_group.app.id]
  env = {
    INFLUX_URL            = var.influx_url
    INFLUX_ORG            = var.influx_org
    INFLUX_AIR_BUCKET     = "air-quality"
    INFLUX_WEATHER_BUCKET = "weather"
    GRAFANA_PUBLIC_URL    = module.grafana.url
  }
  secret_env = {
    INFLUX_TOKEN = aws_secretsmanager_secret.var_influx_token.arn
  }
}

module "frontend" {
  source             = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/aws/express-service?ref=tf-modules-v0.1.0"
  name               = "tsa-frontend"
  cluster            = aws_ecs_cluster.this.name
  image              = "${module.ecr.repository_urls["frontend"]}:${var.image_tag}"
  port               = 80
  health_path        = "/"
  subnet_ids         = data.aws_subnets.default.ids
  security_group_ids = [aws_security_group.app.id]
  env = {
    API_UPSTREAM = module.api.url
  }
  secret_env = {}
}

module "seed" {
  source             = "git::https://github.com/ovokpus/GKE-Cluster-Management.git//terraform/modules/aws/fargate-job?ref=tf-modules-v0.1.0"
  name               = "tsa-seed"
  cluster            = aws_ecs_cluster.this.name
  image              = "${module.ecr.repository_urls["app"]}:${var.image_tag}"
  command            = ["python", "-m", "tsa.seed"]
  subnet_ids         = data.aws_subnets.default.ids
  security_group_ids = [aws_security_group.app.id]
  env = {
    INFLUX_URL            = var.influx_url
    INFLUX_ORG            = var.influx_org
    INFLUX_AIR_BUCKET     = "air-quality"
    INFLUX_WEATHER_BUCKET = "weather"
    SYNTH_STATIONS        = "Aotizhongxin,Wanliu,Dongsi"
    SYNTH_HOURS           = "720"
  }
  secret_env = {
    INFLUX_TOKEN = aws_secretsmanager_secret.var_influx_token.arn
  }
}
