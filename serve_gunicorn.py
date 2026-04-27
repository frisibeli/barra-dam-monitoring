"""
Gunicorn WSGI entrypoint for dam-monitor.

Usage:
    gunicorn -c gunicorn.conf.py serve_gunicorn:app

Or directly:
    gunicorn -w 2 -b 0.0.0.0:80 --preload serve_gunicorn:app
"""
import os
import sys
import json
import mimetypes
from datetime import date, timedelta
from urllib.parse import urlparse

_BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE)
sys.path.insert(0, _BASE)

from config import get_config
from pipelines.prediction import PredictionPipeline

# ── Load model once at module level — works with gunicorn --preload ──
print("Training prediction model...", flush=True)
_cfg = get_config()
_pipeline = PredictionPipeline(_cfg)
_model = _pipeline._service.train(n_splits=5)
print("Model loaded and ready.", flush=True)


# ── Helpers ───────────────────────────────────────────────────────────

def _cors_headers():
    return [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
    ]


def _json_response(start_response, data, status=200):
    body = json.dumps(data).encode("utf-8")
    phrases = {200: "OK", 404: "Not Found", 500: "Internal Server Error"}
    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ] + _cors_headers()
    start_response(f"{status} {phrases.get(status, 'Error')}", headers)
    return [body]


# ── API handlers ──────────────────────────────────────────────────────

def _handle_forecast(environ, start_response):
    try:
        fc_data = _pipeline._weather_service.fetch_forecast(forecast_days=7)
        results = _pipeline._service.forecast(_model, fc_data, forecast_days=7)
        return _json_response(start_response, [
            {"date": r.date, "predicted_inflow_m3s": r.predicted_inflow_m3s}
            for r in results
        ])
    except Exception as exc:
        return _json_response(start_response, {"error": str(exc)}, status=500)


def _handle_predict(environ, start_response):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        body = json.loads(environ["wsgi.input"].read(length)) if length else {}

        precip     = float(body.get("precipitation_sum", 0))
        temp_max   = float(body.get("temperature_2m_max", 15))
        temp_min   = float(body.get("temperature_2m_min", 5))
        snowfall   = float(body.get("snowfall_sum", 0))
        rain       = float(body.get("rain_sum", precip))
        days       = int(body.get("forecast_days", 7))
        snow_cover = body.get("snow_cover_pct")
        snow_cover = float(snow_cover) if snow_cover is not None else None

        today = date.today()
        times = [(today + timedelta(days=i)).isoformat() for i in range(days)]
        fc_data = {
            "points": {
                "synthetic": {
                    "daily": {
                        "time":               times,
                        "precipitation_sum":  [precip]   * days,
                        "rain_sum":           [rain]     * days,
                        "snowfall_sum":       [snowfall] * days,
                        "temperature_2m_max": [temp_max] * days,
                        "temperature_2m_min": [temp_min] * days,
                    }
                }
            }
        }
        results = _pipeline._service.forecast(
            _model, fc_data, forecast_days=days,
            snow_cover_pct_override=snow_cover,
        )
        return _json_response(start_response, [
            {"date": r.date, "predicted_inflow_m3s": r.predicted_inflow_m3s}
            for r in results
        ])
    except Exception as exc:
        return _json_response(start_response, {"error": str(exc)}, status=500)


# ── Static file handler ───────────────────────────────────────────────

def _serve_static(environ, start_response, path):
    safe = os.path.normpath(path.lstrip("/") or "dam_flood_simulator.html")
    full = os.path.join(_BASE, safe)

    # Prevent directory traversal
    if not os.path.abspath(full).startswith(_BASE):
        start_response("403 Forbidden", [("Content-Type", "text/plain")])
        return [b"Forbidden"]

    if os.path.isdir(full):
        full = os.path.join(full, "dam_flood_simulator.html")

    if not os.path.isfile(full):
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]

    mime, _ = mimetypes.guess_type(full)
    with open(full, "rb") as f:
        body = f.read()

    start_response("200 OK", [
        ("Content-Type", mime or "application/octet-stream"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "public, max-age=3600"),
    ])
    return [body]


# ── WSGI app ──────────────────────────────────────────────────────────

def app(environ, start_response):
    path   = urlparse(environ.get("PATH_INFO", "/")).path
    method = environ.get("REQUEST_METHOD", "GET").upper()

    if method == "OPTIONS":
        start_response("204 No Content", _cors_headers())
        return [b""]

    if path == "/api/forecast" and method == "GET":
        return _handle_forecast(environ, start_response)

    if path == "/api/predict" and method == "POST":
        return _handle_predict(environ, start_response)

    return _serve_static(environ, start_response, path)
