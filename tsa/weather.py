"""Live weather: weatherapi.com when WEATHERAPI_KEY is set (original source), else keyless Open-Meteo."""
import requests

from .config import settings
from .transform import open_meteo_to_point, weatherapi_to_point


def fetch_current() -> dict:
    if settings.weatherapi_key:
        r = requests.get("https://api.weatherapi.com/v1/current.json",
                         params={"key": settings.weatherapi_key, "q": settings.weather_city, "aqi": "no"}, timeout=15)
        r.raise_for_status()
        return weatherapi_to_point(r.json())
    r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=15, params={
        "latitude": settings.weather_lat, "longitude": settings.weather_lon,
        "current": "temperature_2m,wind_speed_10m", "wind_speed_unit": "kmh"})
    r.raise_for_status()
    return open_meteo_to_point(r.json(), settings.weather_city)
