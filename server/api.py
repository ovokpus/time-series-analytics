"""FastAPI over InfluxDB: series, anomaly detection and live weather, beside the Grafana dashboards."""
from __future__ import annotations

import re
import threading
import time
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from tsa.config import settings
from tsa.influx import client, write_point
from tsa.transform import PRSA_FIELDS, rolling_zscore_anomalies
from tsa.weather import fetch_current

RANGE_RE = re.compile(r"^-\d{1,4}[mhd]$")
EVERY_RE = re.compile(r"^\d{1,4}[mhd]$")
STATE = {"last_weather": None, "last_weather_error": None}


def _check(start: str, every: str | None = None) -> None:
    if not RANGE_RE.match(start) or (every and not EVERY_RE.match(every)):
        raise HTTPException(422, "start must look like -7d / -24h, every like 1h")


def _field(field: str) -> str:
    if field not in PRSA_FIELDS:
        raise HTTPException(422, f"field must be one of {PRSA_FIELDS}")
    return field


def _station_filter(station: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", station):
        raise HTTPException(422, "bad station")
    return f'|> filter(fn:(r)=> r.station == "{station}")'


def query_df(flux: str) -> pd.DataFrame:
    with client() as c:
        df = c.query_api().query_data_frame(flux)
    if isinstance(df, list):
        df = pd.concat(df) if df else pd.DataFrame()
    return df


def collect_weather() -> dict:
    p = fetch_current()
    with client() as c:
        write_point(c, p)
    STATE["last_weather"] = {**p, "time": p["time"].isoformat()}
    STATE["last_weather_error"] = None
    return STATE["last_weather"]


def _poller(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            collect_weather()
        except Exception as e:  # network down etc. -> report, never fabricate
            STATE["last_weather_error"] = f"{type(e).__name__}: {e}"[:300]
        stop.wait(settings.weather_poll_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = threading.Event()
    if settings.weather_poll_seconds > 0:
        threading.Thread(target=_poller, args=(stop,), daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="Time-series analytics API", lifespan=lifespan)


@app.get("/health")
def health():
    try:
        with client() as c:
            ok = c.ping()
    except Exception:
        ok = False
    mode = None
    if ok:
        df = query_df(f'from(bucket:"{settings.air_bucket}") |> range(start:0) '
                      '|> filter(fn:(r)=> r._measurement=="seed_meta" and r._field=="mode") |> last()')
        mode = None if df.empty else str(df["_value"].iloc[0])
    return {"status": "ok" if ok else "degraded", "influxdb": ok, "air_quality_data": mode,
            "weather_source": "weatherapi.com" if settings.weatherapi_key else "open-meteo (keyless)",
            "weather_city": settings.weather_city, "last_weather": STATE["last_weather"],
            "last_weather_error": STATE["last_weather_error"], "grafana_url": settings.grafana_url}


@app.get("/api/stations")
def stations():
    df = query_df(f'import "influxdata/influxdb/schema"\nschema.tagValues(bucket:"{settings.air_bucket}", tag:"station", start:0)')
    return {"stations": sorted(df["_value"].tolist()) if not df.empty else [], "fields": PRSA_FIELDS}


def _series(station: str, field: str, start: str, every: str) -> pd.Series:
    flux = (f'from(bucket:"{settings.air_bucket}") |> range(start:{start}) '
            f'|> filter(fn:(r)=> r._measurement=="air_quality" and r._field=="{field}") {_station_filter(station)} '
            f'|> group() |> aggregateWindow(every:{every}, fn:mean, createEmpty:false) |> keep(columns:["_time","_value"])')
    df = query_df(flux)
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["_value"].to_numpy(dtype=float), index=pd.to_datetime(df["_time"])).sort_index()


@app.get("/api/series")
def series(station: str, field: str = "PM2.5", start: str = "-7d", every: str = "1h"):
    _check(start, every)
    s = _series(station, _field(field), start, every)
    return {"station": station, "field": field, "points": [{"t": t.isoformat(), "v": round(v, 2)} for t, v in s.items()]}


@app.get("/api/anomalies")
def anomalies(station: str, field: str = "PM2.5", start: str = "-30d", window: int = Query(24, ge=3, le=500),
              threshold: float = Query(3.0, ge=1.0, le=10.0)):
    _check(start)
    s = _series(station, _field(field), start, "1h")
    a = rolling_zscore_anomalies(s, window, threshold)
    return {"station": station, "field": field, "window": window, "threshold": threshold, "points_scanned": len(s),
            "anomalies": [{"t": t.isoformat(), "value": round(r.value, 1), "baseline": round(r.baseline, 1), "z": round(r.z, 2)}
                          for t, r in a.iterrows()]}


@app.get("/api/summary")
def summary(field: str = "PM2.5", start: str = "-30d"):
    _check(start)
    base = (f'from(bucket:"{settings.air_bucket}") |> range(start:{start}) '
            f'|> filter(fn:(r)=> r._measurement=="air_quality" and r._field=="{_field(field)}") |> group(columns:["station"])')
    out = {}
    for fn in ["mean", "max", "count"]:
        df = query_df(f"{base} |> {fn}()")
        for _, r in df.iterrows():
            out.setdefault(r["station"], {})[fn] = round(float(r["_value"]), 1)
    return {"field": field, "start": start, "stations": out}


@app.get("/api/weather")
def weather(start: str = "-24h"):
    _check(start)
    df = query_df(f'from(bucket:"{settings.weather_bucket}") |> range(start:{start}) '
                  '|> filter(fn:(r)=> r._measurement=="api") |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")')
    pts = [] if df.empty else [{"t": pd.Timestamp(r["_time"]).isoformat(), "temp_c": r.get("temp_c"), "wind_kph": r.get("wind_kph"),
                                "source": r.get("source"), "location": r.get("location")} for _, r in df.sort_values("_time").iterrows()]
    return {"points": pts}


@app.post("/api/weather/collect")
def weather_collect():
    try:
        return collect_weather()
    except Exception as e:
        STATE["last_weather_error"] = f"{type(e).__name__}: {e}"[:300]
        raise HTTPException(502, f"Weather source unavailable: {STATE['last_weather_error']}. Nothing was recorded.")
