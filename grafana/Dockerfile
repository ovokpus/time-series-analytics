# Grafana with this repo's datasource and dashboards baked in, for cloud
# deploys (Terraform). docker compose still mounts the same folders.
FROM grafana/grafana-oss:11.6.0
COPY provisioning /etc/grafana/provisioning
COPY dashboards /var/lib/grafana/dashboards
