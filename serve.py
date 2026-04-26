import http.server
import socketserver
import webbrowser
import os
import sys
import json
from datetime import date, timedelta
from urllib.parse import urlparse

PORT = 80
_BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE)
sys.path.insert(0, _BASE)

from config import get_config
from pipelines.prediction import PredictionPipeline


class DamMonitorHandler(http.server.SimpleHTTPRequestHandler):
    _model = None
    _pipeline = None

    @classmethod
    def load_model(cls):
        print("Training prediction model...", flush=True)
        cfg = get_config()
        cls._pipeline = PredictionPipeline(cfg)
        cls._model = cls._pipeline._service.train(n_splits=5)
        print("Model loaded and ready.", flush=True)

    # ── CORS ──────────────────────────────────────────────────────────

    def _add_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    # ── HTTP verbs ────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self._add_cors_headers()
        self.end_headers()

    def do_GET(self):
        if urlparse(self.path).path == "/api/forecast":
            self._handle_forecast()
        else:
            super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path == "/api/predict":
            self._handle_predict()
        else:
            self.send_response(404)
            self.end_headers()

    # ── Endpoints ─────────────────────────────────────────────────────

    def _handle_forecast(self):
        try:
            fc_data = self._pipeline._weather_service.fetch_forecast(forecast_days=7)
            results = self._pipeline._service.forecast(
                self._model, fc_data, forecast_days=7
            )
            self._send_json(
                [{"date": r.date, "predicted_inflow_m3s": r.predicted_inflow_m3s} for r in results]
            )
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def _handle_predict(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            precip   = float(body.get("precipitation_sum", 0))
            temp_max = float(body.get("temperature_2m_max", 15))
            temp_min = float(body.get("temperature_2m_min", 5))
            snowfall = float(body.get("snowfall_sum", 0))
            rain     = float(body.get("rain_sum", precip))
            days     = int(body.get("forecast_days", 7))
            snow_cover = body.get("snow_cover_pct")
            snow_cover = float(snow_cover) if snow_cover is not None else None

            today = date.today()
            times = [(today + timedelta(days=i)).isoformat() for i in range(days)]
            fc_data = {
                "points": {
                    "synthetic": {
                        "daily": {
                            "time": times,
                            "precipitation_sum": [precip]   * days,
                            "rain_sum":          [rain]      * days,
                            "snowfall_sum":      [snowfall]  * days,
                            "temperature_2m_max": [temp_max] * days,
                            "temperature_2m_min": [temp_min] * days,
                        }
                    }
                }
            }

            results = self._pipeline._service.forecast(
                self._model, fc_data, forecast_days=days,
                snow_cover_pct_override=snow_cover,
            )
            self._send_json(
                [{"date": r.date, "predicted_inflow_m3s": r.predicted_inflow_m3s} for r in results]
            )
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def log_message(self, fmt, *args):  # silence access log for API calls
        if not self.path.startswith("/api/"):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    DamMonitorHandler.load_model()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PORT), DamMonitorHandler) as httpd:
        print(f"Serving at http://localhost:{PORT}", flush=True)
        webbrowser.open(f"http://localhost:{PORT}/dam_flood_simulator.html")
        httpd.serve_forever()
