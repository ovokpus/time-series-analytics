"""Pure transforms (no I/O), shared by the seeder, the weather collector and tests."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

PRSA_FIELDS = ["PM2.5", "PM10", "SO2", "NO2", "CO", "O3", "TEMP", "PRES", "DEWP", "RAIN", "WSPM"]
PRSA_TAGS = ["station", "wd"]
WIND_DIRS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def prsa_to_frame(df: pd.DataFrame) -> pd.DataFrame:
    """UCI Beijing PRSA CSV rows -> UTC-indexed frame (fields + station/wd tags).

    The original script built the index as strings and passed the tag list as field columns;
    here the index is a real DatetimeIndex and fields/tags are separated.
    """
    ts = pd.to_datetime(df[["year", "month", "day", "hour"]], utc=True)
    out = df.drop(columns=[c for c in ["No", "year", "month", "day", "hour"] if c in df.columns])
    out.index = pd.DatetimeIndex(ts, name="time")
    for f in PRSA_FIELDS:
        if f in out.columns:
            out[f] = pd.to_numeric(out[f], errors="coerce").astype(float)
    out["wd"] = out["wd"].fillna("NA").astype(str)
    return out


def synthetic_prsa(stations: list[str], hours: int, end: dt.datetime | None = None, seed: int = 7) -> pd.DataFrame:
    """Generate SYNTHETIC hourly rows in the PRSA schema (clearly not real measurements).

    Daily temperature cycle, PM2.5 that builds up on low-wind days, and a few injected
    pollution spikes so the anomaly view has something to find.
    """
    rng = np.random.default_rng(seed)
    end = (end or dt.datetime.now(dt.timezone.utc)).replace(minute=0, second=0, microsecond=0)
    idx = pd.date_range(end=end, periods=hours, freq="h", tz="UTC")
    frames = []
    for i, st in enumerate(stations):
        hod = idx.hour.to_numpy()
        day = np.arange(hours) / 24
        temp = 12 + 8 * np.sin((hod - 9) / 24 * 2 * np.pi) + 3 * np.sin(day / 9) + rng.normal(0, 1, hours)
        wspm = np.clip(2 + 1.5 * np.sin(day / 3 + i) + rng.gamma(1.5, 0.6, hours), 0.1, None)
        base = 40 + 15 * i
        pm25 = np.empty(hours)
        level = base
        for t in range(hours):
            level = 0.92 * level + 0.08 * (base * 2.2 / wspm[t]) + rng.normal(0, 3)
            pm25[t] = max(level, 2)
        for s in rng.choice(np.arange(24, hours), size=max(hours // 200, 2), replace=False):
            pm25[s:s + 3] *= rng.uniform(2.5, 4)
        frames.append(pd.DataFrame({
            "PM2.5": pm25.round(1), "PM10": (pm25 * rng.uniform(1.2, 1.6, hours)).round(1),
            "SO2": np.clip(rng.normal(12, 4, hours), 1, None).round(1),
            "NO2": np.clip(30 + pm25 * 0.3 + rng.normal(0, 6, hours), 2, None).round(1),
            "CO": (600 + pm25 * 9 + rng.normal(0, 80, hours)).round(0),
            "O3": np.clip(55 + 25 * np.sin((hod - 14) / 24 * 2 * np.pi) + rng.normal(0, 6, hours), 1, None).round(1),
            "TEMP": temp.round(1), "PRES": (1012 + rng.normal(0, 3, hours)).round(1),
            "DEWP": (temp - rng.uniform(4, 12, hours)).round(1),
            "RAIN": np.where(rng.random(hours) < 0.04, rng.gamma(1, 1.2, hours), 0).round(1),
            "WSPM": wspm.round(1), "wd": rng.choice(WIND_DIRS, hours), "station": st,
        }, index=pd.DatetimeIndex(idx, name="time")))
    return pd.concat(frames)


def weatherapi_to_point(js: dict) -> dict:
    """weatherapi.com current.json -> one point. Uses the real UTC epoch (the original
    script formatted local time with a hard-coded +12:00 offset)."""
    return {
        "measurement": "api", "source": "weatherapi",
        "tags": {"location": js["location"]["name"], "region": js["location"].get("region", "")},
        "fields": {"temp_c": float(js["current"]["temp_c"]), "wind_kph": float(js["current"]["wind_kph"])},
        "time": dt.datetime.fromtimestamp(js["location"]["localtime_epoch"], dt.timezone.utc),
    }


def open_meteo_to_point(js: dict, city: str) -> dict:
    """Keyless fallback: api.open-meteo.com current temperature/wind -> same point shape."""
    cur = js["current"]
    t = dt.datetime.fromisoformat(cur["time"]).replace(tzinfo=dt.timezone.utc)
    return {
        "measurement": "api", "source": "open-meteo",
        "tags": {"location": city, "region": ""},
        "fields": {"temp_c": float(cur["temperature_2m"]), "wind_kph": float(cur["wind_speed_10m"])},
        "time": t,
    }


def rolling_zscore_anomalies(s: pd.Series, window: int = 24, threshold: float = 3.0) -> pd.DataFrame:
    """Flag points more than `threshold` std devs from the trailing-window mean (window excludes the point)."""
    s = s.dropna().astype(float)
    prev = s.shift(1).rolling(window, min_periods=max(window // 2, 3))
    z = (s - prev.mean()) / prev.std().replace(0, np.nan)
    out = pd.DataFrame({"value": s, "baseline": prev.mean(), "z": z})
    return out[out["z"].abs() >= threshold].dropna()
