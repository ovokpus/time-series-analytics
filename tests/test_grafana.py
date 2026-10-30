import json
from pathlib import Path

import yaml  # noqa: F401  (pyyaml via dev deps)

ROOT = Path(__file__).resolve().parent.parent


def test_dashboards_use_provisioned_datasource():
    for f in (ROOT / "grafana/dashboards").glob("*.json"):
        d = json.loads(f.read_text())
        assert d["uid"] and d["panels"]
        for p in d["panels"]:
            assert p["datasource"]["uid"] == "influxdb"
            assert all("from(bucket:" in t["query"] for t in p["targets"])


def test_datasource_provisioning_is_flux():
    ds = yaml.safe_load((ROOT / "grafana/provisioning/datasources/influxdb.yml").read_text())["datasources"][0]
    assert ds["uid"] == "influxdb" and ds["jsonData"]["version"] == "Flux"
