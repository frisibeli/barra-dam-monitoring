from datetime import datetime, timedelta

import requests

_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_DAILY_VARIABLES = [
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "temperature_2m_max",
    "temperature_2m_min",
]


class WeatherService:
    """Fetches weather data from Open-Meteo for a set of geographic points."""

    def __init__(self, geo_points: dict):
        self._geo_points = geo_points

    def fetch_history(self, start_date: str, end_date: str) -> dict:
        """Fetch historical daily weather for all geo points."""
        results = {}
        for name, (lat, lon) in self._geo_points.items():
            print(f"\n[{name}] ({lat}, {lon})")
            results[name] = self._fetch_point_history(start_date, end_date, lat, lon)
            n = len(results[name]["daily"]["time"])
            print(f"  → {n} days fetched")

        return {
            "query": {
                "start_date": start_date,
                "end_date": end_date,
                "variables": _DAILY_VARIABLES,
                "points": {k: {"lat": v[0], "lon": v[1]} for k, v in self._geo_points.items()},
            },
            "points": results,
        }

    def fetch_forecast(self, forecast_days: int = 7) -> dict:
        """Fetch weather forecast for all geo points."""
        results = {}
        for name, (lat, lon) in self._geo_points.items():
            print(f"\n[{name}] ({lat}, {lon})")
            results[name] = self._fetch_point_forecast(lat, lon, forecast_days)
            n = len(results[name]["daily"]["time"])
            print(f"  → {n} forecast days fetched")

        return {
            "query": {
                "forecast_days": forecast_days,
                "variables": _DAILY_VARIABLES,
                "points": {k: {"lat": v[0], "lon": v[1]} for k, v in self._geo_points.items()},
            },
            "generated": datetime.utcnow().isoformat() + "Z",
            "points": results,
        }

    def _fetch_point_history(self, start_date: str, end_date: str, lat: float, lon: float) -> dict:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        chunk_days = 1825
        all_dates: list = []
        all_daily: dict = {v: [] for v in _DAILY_VARIABLES}

        chunk_start = start_dt
        while chunk_start <= end_dt:
            chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end_dt)
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": chunk_start.strftime("%Y-%m-%d"),
                "end_date": chunk_end.strftime("%Y-%m-%d"),
                "daily": ",".join(_DAILY_VARIABLES),
                "timezone": "Europe/Sofia",
            }
            print(f"  Fetching {params['start_date']} → {params['end_date']} …")
            resp = requests.get(_ARCHIVE_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"API error: {data['error']}")
            daily = data["daily"]
            all_dates.extend(daily["time"])
            for var in _DAILY_VARIABLES:
                all_daily[var].extend(daily[var])
            chunk_start = chunk_end + timedelta(days=1)

        return {
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "timezone": data.get("timezone", "Europe/Sofia"),
            "elevation": data.get("elevation"),
            "daily_units": data.get("daily_units", {}),
            "daily": {"time": all_dates, **all_daily},
        }

    def _fetch_point_forecast(self, lat: float, lon: float, forecast_days: int) -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join(_DAILY_VARIABLES),
            "timezone": "Europe/Sofia",
            "forecast_days": forecast_days,
        }
        resp = requests.get(_FORECAST_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Forecast API error: {data['error']}")
        return {
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "timezone": data.get("timezone", "Europe/Sofia"),
            "elevation": data.get("elevation"),
            "daily_units": data.get("daily_units", {}),
            "daily": data["daily"],
        }
