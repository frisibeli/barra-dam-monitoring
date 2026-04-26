from dataclasses import dataclass


@dataclass
class DailyWeather:
    time: list
    precipitation_sum: list
    rain_sum: list
    snowfall_sum: list
    temperature_2m_max: list
    temperature_2m_min: list


@dataclass
class WeatherPoint:
    latitude: float
    longitude: float
    timezone: str
    elevation: float | None
    daily: DailyWeather
