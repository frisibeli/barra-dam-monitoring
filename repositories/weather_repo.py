import json
import os


class WeatherRepo:
    def __init__(self, history_path: str, forecast_path: str):
        self.history_path = history_path
        self.forecast_path = forecast_path

    def load_history(self) -> dict:
        with open(self.history_path) as f:
            return json.load(f)

    def save_history(self, data: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.history_path)), exist_ok=True)
        with open(self.history_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_forecast(self) -> dict:
        with open(self.forecast_path) as f:
            return json.load(f)

    def save_forecast(self, data: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.forecast_path)), exist_ok=True)
        with open(self.forecast_path, "w") as f:
            json.dump(data, f, indent=2)
