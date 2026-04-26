import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from models.reading import WaterReading
from repositories.water_repo import WaterReadingRepo
from services.elevation import ElevationService
from services.sentinel_hub import SentinelHubService
from services.water_analysis import WaterAnalysisService
from utils.geo import build_dam_mask
from visualization.water import WaterVisualizer
from .base import BasePipeline


class WaterPipeline(BasePipeline):
    """Monitors reservoir water area using Sentinel-2 NDWI/MNDWI."""

    def __init__(self, app_config):
        cfg = app_config.reservoir
        sh = SentinelHubService(app_config.sh_config, app_config.data_collection, app_config.raw_cache_dir)
        repo = WaterReadingRepo(cfg.results_path)
        viz = WaterVisualizer(sh, cfg)
        super().__init__(repo, sh, viz, cfg.plots_dir)

        self._cfg = cfg
        self._app_cfg = app_config
        self._analysis = WaterAnalysisService(cfg)
        self._evalscript = sh.load_evalscript("water_index.js")
        self._dam_mask = build_dam_mask(cfg.bbox, cfg.image_size, cfg.polygon_coords)
        print(f"  Dam mask: {int(np.sum(self._dam_mask))} pixels inside dam, "
              f"{int(np.sum(~self._dam_mask))} outside excluded")

        dem_path = Path(app_config.raw_cache_dir).parent / "dem" / "dem.tif"
        if dem_path.exists():
            self._elevation_svc: ElevationService | None = ElevationService(str(dem_path), cfg)
            print(f"  Elevation service ready (DEM: {dem_path})")
        else:
            self._elevation_svc = None

    def get_time_windows(self) -> list[tuple[str, str]]:
        return self._sentinel.search_available_windows(
            bbox=self._cfg.bbox,
            time_start=self._cfg.time_start,
            time_end=self._cfg.time_end,
            time_delta=self._cfg.time_delta,
            max_cloud_cover=self._cfg.max_cloud_cover,
        )

    def fetch_index_array(self, t_from: str, t_to: str, force: bool = False):
        return self._sentinel.fetch_index_array(
            evalscript=self._evalscript,
            geometry=self._cfg.bbox,
            image_size=self._cfg.image_size,
            time_from=t_from,
            time_to=t_to,
            cache_name="water_index",
            force=force,
        )

    def compute_reading(self, t_from: str, t_to: str, index_arr: np.ndarray):
        index_arr[~self._dam_mask] = -9999
        stats = self._analysis.compute(index_arr, self._dam_mask)
        if stats is None:
            return None, index_arr
        reading = WaterReading(
            date=t_from,
            date_to=t_to,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            **stats,
        )

        if self._elevation_svc is not None:
            reading.elevation_m = self._elevation_svc.sample_water_elevation(
                index_arr, self._dam_mask
            )

        elev_str = f" | Elevation: {reading.elevation_m} m" if reading.elevation_m is not None else ""
        print(
            f"  → Water area: {reading.water_area_km2} km²  "
            f"| Cloud: {reading.cloud_pct}%  "
            f"| Valid pixels: {reading.valid_pixels}/{reading.total_pixels}"
            f"{elev_str}"
        )
        return reading, index_arr

    def viz_filenames(self) -> list[str]:
        return ["true_color.png", "water_index.png", "water_mask.png", "overlay.png"]

    def is_cached_entry_valid(self, entry: WaterReading) -> bool:
        if entry.cloud_pct > self._cfg.max_cloud_cover:
            print(
                f"  [cached — rejected: cloud {entry.cloud_pct}% "
                f"> {self._cfg.max_cloud_cover}%]"
            )
            return False
        return True

    def run_per_date_viz(self, t_from: str, t_to: str, index_arr: np.ndarray, date_dir: str) -> None:
        rgb = self._viz.fetch_true_color(
            self._cfg.bbox, self._cfg.image_size, t_from, t_to
        )
        if rgb is not None:
            self._viz.save_true_color_png(rgb, os.path.join(date_dir, "true_color.png"))
            self._viz.save_overlay_png(rgb, index_arr, os.path.join(date_dir, "overlay.png"))
        self._viz.save_water_index_png(index_arr, os.path.join(date_dir, "water_index.png"))
        self._viz.save_water_mask_png(index_arr, os.path.join(date_dir, "water_mask.png"))

    def run_summary_viz(self, arrays: list, viz_dates: list, rebuild_manifest: bool = False) -> None:
        results_path = self._cfg.results_path
        plots_dir = self._cfg.plots_dir
        manifest_path = self._cfg.manifest_path

        self._viz.generate_time_series_chart(
            results_path, os.path.join(plots_dir, "time_series.png")
        )
        if len(arrays) >= 2:
            self._viz.generate_change_map(
                arrays[0][1], arrays[-1][1],
                arrays[0][0], arrays[-1][0],
                os.path.join(plots_dir, "change_map.png"),
            )
        self._viz.generate_multitemporal_grid(
            arrays,
            threshold=self._cfg.water_threshold,
            pixel_color=(30, 100, 220),
            title="Water Mask Evolution",
            out_path=os.path.join(plots_dir, "multitemporal.png"),
        )
        self._viz.write_manifest(viz_dates, results_path, plots_dir, manifest_path, rebuild_manifest=rebuild_manifest)

    def get_metadata(self) -> dict:
        return {"reservoir": self._cfg.name}
