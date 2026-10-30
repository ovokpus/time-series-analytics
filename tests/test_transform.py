import datetime as dt

import numpy as np
import pandas as pd

from tsa.transform import (PRSA_FIELDS, open_meteo_to_point, prsa_to_frame, rolling_zscore_anomalies,
                           synthetic_prsa, weatherapi_to_point)


def test_prsa_to_frame_builds_utc_index_and_drops_parts():
    raw = pd.DataFrame({"No": [1, 2], "year": [2013, 2013], "month": [3, 3], "day": [1, 1], "hour": [0, 1],
                        "PM2.5": [4, "NA"], "PM10": [4, 8], "SO2": [4, 4], "NO2": [7, 7], "CO": [300, 300], "O3": [77, 77],
                        "TEMP": [-0.7, -1.1], "PRES": [1023, 1023], "DEWP": [-18.8, -18.2], "RAIN": [0, 0],
                        "wd": ["NNW", None], "WSPM": [4.4, 4.7], "station": ["Aotizhongxin"] * 2})
    f = prsa_to_frame(raw)
    assert str(f.index.tz) == "UTC" and f.index[1] == pd.Timestamp("2013-03-01 01:00", tz="UTC")
    assert not {"No", "year", "hour"} & set(f.columns)
    assert np.isnan(f["PM2.5"].iloc[1]) and f["wd"].tolist() == ["NNW", "NA"]


def test_synthetic_is_deterministic_and_in_schema():
    end = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    a, b = synthetic_prsa(["A", "B"], 48, end), synthetic_prsa(["A", "B"], 48, end)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 96 and set(PRSA_FIELDS) <= set(a.columns) and a.index.max() == pd.Timestamp(end)


def test_weatherapi_point_uses_utc_epoch():
    p = weatherapi_to_point({"location": {"name": "Toronto", "region": "Ontario", "localtime_epoch": 1700000000},
                             "current": {"temp_c": 3.0, "wind_kph": 11}})
    assert p["time"] == dt.datetime(2023, 11, 14, 22, 13, 20, tzinfo=dt.timezone.utc)
    assert p["fields"] == {"temp_c": 3.0, "wind_kph": 11.0} and p["source"] == "weatherapi"


def test_open_meteo_point():
    p = open_meteo_to_point({"current": {"time": "2026-10-30T13:15", "temperature_2m": 8.6, "wind_speed_10m": 11.2}}, "Toronto")
    assert p["tags"]["location"] == "Toronto" and p["fields"]["temp_c"] == 8.6 and p["time"].tzinfo is dt.timezone.utc


def test_zscore_flags_injected_spike_only():
    idx = pd.date_range("2026-01-01", periods=100, freq="h")
    s = pd.Series(50 + np.sin(np.arange(100)), index=idx)
    s.iloc[70] = 200
    a = rolling_zscore_anomalies(s, 24, 3.0)
    assert list(a.index) == [idx[70]] and a["z"].iloc[0] > 3
