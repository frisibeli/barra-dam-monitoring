from pathlib import Path

from config import get_config
from repositories.water_repo import WaterReadingRepo
from repositories.snow_repo import SnowReadingRepo
from repositories.weather_repo import WeatherRepo
from repositories.volume_repo import VolumeRepo
from services.prediction import PredictionService
from services.weather import WeatherService
from visualization.forecast import ForecastVisualizer

_DATA = Path(__file__).resolve().parent.parent / "data"


class PredictionPipeline:
    """Orchestrates inflow prediction: training and 7-day forecast."""

    def __init__(self, app_config):
        cfg = app_config
        weather_repo = WeatherRepo(
            history_path=str(_DATA / "weather_history.json"),
            forecast_path=str(_DATA / "weather_forecast.json"),
        )
        water_repo = WaterReadingRepo(str(_DATA / "results.json"))
        snow_repo = SnowReadingRepo(str(_DATA / "snow" / "snow_results.json"))
        volume_repo = VolumeRepo(get_config().mosv.results_path)

        self._service = PredictionService(volume_repo, water_repo, snow_repo, weather_repo)
        self._weather_service = WeatherService(cfg.weather_geo_points)
        self._weather_repo = weather_repo
        self._viz = ForecastVisualizer(volume_repo)

    def run_training(self) -> None:
        print("═══ Training on historic data ═══\n")
        self._service.train()

    def run_forecast(self, days: int = 7, plot: bool = False) -> list:
        print("═══ Training on historic data ═══\n")
        model = self._service.train(n_splits=5)

        print("\n═══ Fetching weather forecast ═══")
        fc_data = self._weather_service.fetch_forecast(forecast_days=days)

        results = self._service.forecast(model, fc_data, forecast_days=days)

        if plot:
            self._viz.plot_forecast(results)

        return results
