import pandas as pd
import pytest
from fastapi.testclient import TestClient

from server import api


@pytest.fixture
def client(monkeypatch):
    object.__setattr__(api.settings, "weather_poll_seconds", 0)
    return TestClient(api.app)


def test_rejects_flux_injection(client):
    assert client.get("/api/series", params={"station": 'x") |> drop(', "field": "PM2.5"}).status_code == 422
    assert client.get("/api/series", params={"station": "A", "start": "0) |> yield("}).status_code == 422
    assert client.get("/api/series", params={"station": "A", "field": "evil"}).status_code == 422


def test_anomalies_from_queried_series(client, monkeypatch):
    idx = pd.date_range("2026-01-01", periods=60, freq="h", tz="UTC")
    vals = [10.0 + (i % 3) for i in range(60)]
    vals[40] = 90.0
    monkeypatch.setattr(api, "query_df", lambda flux: pd.DataFrame({"_time": idx, "_value": vals}))
    r = client.get("/api/anomalies", params={"station": "Wanliu"}).json()
    assert r["points_scanned"] == 60 and [a["t"] for a in r["anomalies"]] == [idx[40].isoformat()]


def test_weather_collect_failure_records_nothing(client, monkeypatch):
    def boom():
        raise ConnectionError("offline")
    monkeypatch.setattr(api, "fetch_current", boom)
    r = client.post("/api/weather/collect")
    assert r.status_code == 502 and "Nothing was recorded" in r.json()["detail"]


def test_health_degraded_without_influx(client, monkeypatch):
    class Dead:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ping(self): return False
    monkeypatch.setattr(api, "client", lambda: Dead())
    h = client.get("/health").json()
    assert h["status"] == "degraded" and h["air_quality_data"] is None
