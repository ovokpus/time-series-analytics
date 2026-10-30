"""One-shot loader: real UCI PRSA CSVs from DATA_DIR if present, otherwise SYNTHETIC data."""
import glob
import os
import time

import pandas as pd

from .config import settings
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from .influx import client, ensure_bucket, write_air
from .transform import prsa_to_frame, synthetic_prsa

DATA_DIR = os.getenv("DATA_DIR", "/data/PRSA_Data_20130301-20170228")
STATIONS = os.getenv("SYNTH_STATIONS", "Aotizhongxin,Wanliu,Dongsi").split(",")
HOURS = int(os.getenv("SYNTH_HOURS", str(24 * 30)))


def mark(c, mode: str, files: int) -> None:
    c.write_api(write_options=SYNCHRONOUS).write(
        bucket=settings.air_bucket, record=Point("seed_meta").field("mode", mode).field("files", files))


def main() -> None:
    c = client()
    for _ in range(60):
        try:
            if c.ping():
                break
        except Exception:
            pass
        time.sleep(2)
    ensure_bucket(c, settings.air_bucket)
    ensure_bucket(c, settings.weather_bucket)
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
    if files:
        n = sum(write_air(c, prsa_to_frame(pd.read_csv(f)), "air_quality") for f in files)
        mark(c, "real", len(files))
        print(f"loaded {n} REAL PRSA rows from {len(files)} files")
    else:
        q = f'from(bucket:"{settings.air_bucket}") |> range(start:-400d) |> filter(fn:(r)=>r._measurement=="air_quality") |> limit(n:1)'
        if c.query_api().query(q):
            print("air_quality already seeded; skipping")
            return
        n = write_air(c, synthetic_prsa(STATIONS, HOURS), "air_quality")
        mark(c, "synthetic", 0)
        print(f"no PRSA CSVs in {DATA_DIR}; wrote {n} SYNTHETIC rows for {STATIONS}")


if __name__ == "__main__":
    main()
