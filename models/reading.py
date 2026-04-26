from dataclasses import dataclass


@dataclass
class WaterReading:
    date: str
    date_to: str
    water_area_km2: float
    water_pixels: int
    total_pixels: int
    valid_pixels: int
    cloud_pct: float
    fetched_at: str
    elevation_m: float | None = None

    def cache_key(self) -> str:
        return f"{self.date}|{self.date_to}"


@dataclass
class SnowReading:
    date: str
    date_to: str
    snow_cover_pct: float
    ndsi_mean: float
    ndsi_max: float
    snow_pixels: int
    valid_pixels: int
    total_pixels: int
    cloud_pct: float
    fetched_at: str

    def cache_key(self) -> str:
        return f"{self.date}|{self.date_to}"
