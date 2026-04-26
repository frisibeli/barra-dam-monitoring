from dataclasses import dataclass


@dataclass
class ReservoirConfig:
    """Geometry, thresholds, and paths for the dam/reservoir water pipeline."""
    name: str
    bbox: object          # sentinelhub.BBox
    geometry: object      # sentinelhub.Geometry
    polygon_coords: list
    image_size: tuple
    max_cloud_cover: int
    water_threshold: float
    time_start: str
    time_end: str
    time_delta: int
    results_path: str
    plots_dir: str
    manifest_path: str


@dataclass
class CatchmentConfig:
    """Geometry, thresholds, and paths for the catchment snow pipeline."""
    name: str
    bbox: object          # sentinelhub.BBox
    geometry: object      # sentinelhub.Geometry
    polygon_coords: list
    dam_polygon_coords: list  # used to exclude reservoir pixels from snow stats
    image_size: tuple
    snow_threshold: float
    min_valid_fraction: float
    max_cloud_cover: int
    time_start: str
    time_end: str
    time_delta: int
    results_path: str
    plots_dir: str
    manifest_path: str
