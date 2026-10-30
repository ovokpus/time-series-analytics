import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    influx_url: str = os.getenv("INFLUX_URL", "http://localhost:8086")
    influx_token: str = os.getenv("INFLUX_TOKEN", "local-dev-token")
    influx_org: str = os.getenv("INFLUX_ORG", "my-org")
    air_bucket: str = os.getenv("INFLUX_AIR_BUCKET", "air-quality")
    weather_bucket: str = os.getenv("INFLUX_WEATHER_BUCKET", "weather")
    weatherapi_key: str = os.getenv("WEATHERAPI_KEY", "")
    weather_city: str = os.getenv("WEATHER_CITY", "Toronto")
    weather_lat: float = float(os.getenv("WEATHER_LAT", "43.65"))
    weather_lon: float = float(os.getenv("WEATHER_LON", "-79.38"))
    weather_poll_seconds: int = int(os.getenv("WEATHER_POLL_SECONDS", "300"))
    grafana_url: str = os.getenv("GRAFANA_PUBLIC_URL", "http://localhost:3000")


settings = Settings()
