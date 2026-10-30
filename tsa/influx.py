from __future__ import annotations

import pandas as pd
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from .config import settings
from .transform import PRSA_FIELDS


def client() -> InfluxDBClient:
    return InfluxDBClient(url=settings.influx_url, token=settings.influx_token, org=settings.influx_org, timeout=20_000)


def write_air(c: InfluxDBClient, frame: pd.DataFrame, measurement: str = "air_quality") -> int:
    fields = [f for f in PRSA_FIELDS if f in frame.columns]
    w = c.write_api(write_options=SYNCHRONOUS)
    for _, chunk in frame.groupby("station"):
        w.write(bucket=settings.air_bucket, record=chunk, data_frame_measurement_name=measurement,
                data_frame_tag_columns=["station", "wd"], data_frame_field_columns=fields)
    return len(frame)


def write_point(c: InfluxDBClient, p: dict) -> None:
    pt = Point(p["measurement"]).time(p["time"]).tag("source", p["source"])
    for k, v in p["tags"].items():
        pt = pt.tag(k, v)
    for k, v in p["fields"].items():
        pt = pt.field(k, v)
    c.write_api(write_options=SYNCHRONOUS).write(bucket=settings.weather_bucket, record=pt)


def ensure_bucket(c: InfluxDBClient, name: str) -> None:
    api = c.buckets_api()
    if not api.find_bucket_by_name(name):
        org = c.organizations_api().find_organizations(org=settings.influx_org)[0]
        api.create_bucket(bucket_name=name, org_id=org.id)
