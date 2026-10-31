variable "location" {
  type    = string
  default = "canadacentral"
}

variable "name_prefix" {
  description = "Lowercase letters/digits; used for globally unique names (ACR, Postgres)."
  type        = string
  default     = "tsa"
}

variable "image_tag" {
  description = "Tag you pushed for every image (see README: Deploy)."
  type        = string
  default     = "v1"
}

variable "influx_url" {
  description = "InfluxDB 2.x / InfluxDB Cloud URL."
  type        = string
}

variable "influx_token" {
  description = "InfluxDB API token with read/write on the buckets."
  type        = string
  sensitive   = true
}

variable "influx_org" {
  description = "InfluxDB organisation."
  type        = string
  default     = "my-org"
}

variable "grafana_admin_password" {
  description = "Grafana admin password."
  type        = string
  sensitive   = true
}
