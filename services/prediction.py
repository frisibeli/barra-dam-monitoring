import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

from models.forecast import ForecastReading

_FEATURE_COLS = [
    "prev_inflow_m3s",
    "prev_outflow_m3s",
    "water_area_km2",
    "snow_cover_pct",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "temperature_2m_max",
    "temperature_2m_min",
]
_TARGET = "inflow_m3s"
_WEATHER_VARS = [
    "precipitation_sum", "rain_sum", "snowfall_sum",
    "temperature_2m_max", "temperature_2m_min",
]


class PredictionService:
    """Ridge regression inflow predictor."""

    def __init__(self, volume_repo, water_repo, snow_repo, weather_repo):
        self._vol = volume_repo
        self._water = water_repo
        self._snow = snow_repo
        self._weather = weather_repo

    # ── feature assembly ────────────────────────────────────────────────

    def build_features(self) -> pd.DataFrame:
        vol_df = self._vol.load_as_dataframe()
        volumes = vol_df[["inflow_m3s", "outflow_m3s"]]

        water = self._load_water_series()
        snow = self._load_snow_series()
        weather = self._load_weather()

        idx = pd.date_range(volumes.index.min(), volumes.index.max(), freq="D", name="date")
        df = volumes.reindex(idx)
        df["water_area_km2"] = water.reindex(idx).interpolate(method="time", limit_direction="both")
        df["snow_cover_pct"] = snow.reindex(idx).interpolate(method="time", limit_direction="both")
        df = df.join(weather, how="left")
        df["prev_inflow_m3s"] = df["inflow_m3s"].shift(1)
        df["prev_outflow_m3s"] = df["outflow_m3s"].shift(1)
        return df

    def train(self, n_splits: int = 5) -> Ridge:
        """Train with time-series cross-validation; prints metrics and returns final model."""
        df = self.build_features()
        subset = df.dropna(subset=[_TARGET] + _FEATURE_COLS)
        print(f"Usable rows: {len(subset)}  (of {len(df)} total daily rows)")

        X = subset[_FEATURE_COLS].values
        y = subset[_TARGET].values

        tscv = TimeSeriesSplit(n_splits=n_splits)
        fold_metrics = []
        for fold, (train_idx, test_idx) in enumerate(tscv.split(X), 1):
            model = Ridge(alpha=1.0)
            model.fit(X[train_idx], y[train_idx])
            y_pred = model.predict(X[test_idx])
            mae = mean_absolute_error(y[test_idx], y_pred)
            rmse = float(np.sqrt(mean_squared_error(y[test_idx], y_pred)))
            r2 = r2_score(y[test_idx], y_pred)
            fold_metrics.append({"fold": fold, "MAE": mae, "RMSE": rmse, "R2": r2})
            print(f"  Fold {fold}: MAE={mae:.3f}  RMSE={rmse:.3f}  R²={r2:.3f}")

        model = Ridge(alpha=1.0)
        model.fit(X, y)

        print("\n── Feature coefficients ──")
        for name, coef in zip(_FEATURE_COLS, model.coef_):
            print(f"  {name:>25s}  {coef:+.4f}")
        print(f"  {'intercept':>25s}  {model.intercept_:+.4f}")

        avg = pd.DataFrame(fold_metrics).mean(numeric_only=True)
        print(f"\n── CV average ──  MAE={avg['MAE']:.3f}  RMSE={avg['RMSE']:.3f}  R²={avg['R2']:.3f}")
        return model

    def forecast(
        self,
        model: Ridge,
        weather_forecast: dict,
        forecast_days: int = 7,
        snow_cover_pct_override: float | None = None,
    ) -> list[ForecastReading]:
        """Autoregressive 7-day inflow forecast using pre-trained model."""
        fc_weather = self._weather_from_dict(weather_forecast)

        vol_df = self._vol.load_as_dataframe()
        water = self._load_water_series()
        snow = self._load_snow_series()

        last_water = float(water.iloc[-1])
        last_snow = (
            float(snow_cover_pct_override)
            if snow_cover_pct_override is not None
            else float(snow.iloc[-1])
        )
        last_inflow = float(vol_df["inflow_m3s"].dropna().iloc[-1])
        last_outflow = float(vol_df["outflow_m3s"].dropna().iloc[-1])

        print(f"\n═══ {forecast_days}-day inflow forecast ═══")
        print(f"{'Date':>12s}  {'Predicted inflow (m³/s)':>24s}")
        print("-" * 40)

        results = []
        prev_inflow = last_inflow
        prev_outflow = last_outflow

        for date, row in fc_weather.iterrows():
            features = {
                "prev_inflow_m3s": prev_inflow,
                "prev_outflow_m3s": prev_outflow,
                "water_area_km2": last_water,
                "snow_cover_pct": last_snow,
                **{v: row[v] for v in _WEATHER_VARS},
            }
            X_fc = np.array([[features[c] for c in _FEATURE_COLS]])
            pred = max(float(model.predict(X_fc)[0]), 0.0)

            date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
            print(f"{date_str:>12s}  {pred:>24.3f}")
            results.append(ForecastReading(date=date_str, predicted_inflow_m3s=round(pred, 3)))
            prev_inflow = pred

        return results

    # ── helpers ─────────────────────────────────────────────────────────

    def _load_water_series(self) -> pd.Series:
        readings = self._water.load_all()
        df = pd.DataFrame([{"date": r.date, "water_area_km2": r.water_area_km2} for r in readings])
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").groupby("date")["water_area_km2"].mean()

    def _load_snow_series(self) -> pd.Series:
        readings = self._snow.load_all()
        df = pd.DataFrame([{"date": r.date, "snow_cover_pct": r.snow_cover_pct} for r in readings])
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").groupby("date")["snow_cover_pct"].mean()

    def _load_weather(self) -> pd.DataFrame:
        return self._weather_from_dict(self._weather.load_history())

    @staticmethod
    def _weather_from_dict(data: dict) -> pd.DataFrame:
        frames = []
        for _name, point in data["points"].items():
            times = pd.to_datetime(point["daily"]["time"])
            cols = {v: point["daily"][v] for v in _WEATHER_VARS}
            frames.append(pd.DataFrame(cols, index=times))
        weather = pd.concat(frames).groupby(level=0).mean()
        weather.index.name = "date"
        return weather
