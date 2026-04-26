#!/usr/bin/env python3
"""Entry point for fetching weather data from Open-Meteo.

Usage:
    python scripts/fetch_weather.py history --start 1990-01-01 --end 2024-12-31 --save
    python scripts/fetch_weather.py forecast --days 7 --save
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config
from services.weather import WeatherService

_DATA = Path(__file__).resolve().parent.parent / "data"
_HISTORY_FILE = str(_DATA / "weather_history.json")
_FORECAST_FILE = str(_DATA / "weather_forecast.json")


def main():
    parser = argparse.ArgumentParser(description="Fetch weather data from Open-Meteo.")
    sub = parser.add_subparsers(dest="command")

    hist = sub.add_parser("history", help="Fetch historic weather data.")
    hist.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    hist.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    hist.add_argument("--save", action="store_true", help="Save to JSON file")
    hist.add_argument("--output", default=_HISTORY_FILE)

    fc = sub.add_parser("forecast", help="Fetch weather forecast.")
    fc.add_argument("--days", type=int, default=7, help="Number of forecast days (max 16)")
    fc.add_argument("--save", action="store_true", help="Save to JSON file")
    fc.add_argument("--output", default=_FORECAST_FILE)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    cfg = get_config()
    svc = WeatherService(cfg.weather_geo_points)

    if args.command == "history":
        print(f"Period: {args.start} → {args.end}")
        result = svc.fetch_history(args.start, args.end)
    else:
        print(f"Forecast days: {args.days}")
        result = svc.fetch_forecast(args.days)

    print("\n--- Summary ---")
    for name, data in result["points"].items():
        n = len(data["daily"]["time"])
        elev = data.get("elevation", "?")
        print(f"  {name}: {n} days, elevation {elev} m")

    if args.save:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        size_mb = os.path.getsize(args.output) / (1024 * 1024)
        print(f"\nSaved to {args.output} ({size_mb:.1f} MB)")
    else:
        print("\nDry run — use --save to write the JSON file.")


if __name__ == "__main__":
    main()
