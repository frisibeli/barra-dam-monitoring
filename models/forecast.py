from dataclasses import dataclass


@dataclass
class ForecastReading:
    date: str
    predicted_inflow_m3s: float
