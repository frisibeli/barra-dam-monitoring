import os
from datetime import datetime, timezone

import numpy as np

from config import AppConfig
from models.reading import SnowReading
from repositories.snow_repo import SnowReadingRepo
from services.sentinel_hub import SentinelHubService
from services.snow_analysis import SnowAnalysisService
from utils.geo import build_dam_mask
from visualization.snow import SnowVisualizer
from .base import BasePipeline


class SnowPipeline(BasePipeline):
    """Monitors upstream catchment snow cover using Sentinel-2 NDSI."""

    def __init__(self, app_config: AppConfig):
        cfg = app_config.catchment
        sh = SentinelHubService(app_config.sh_config, app_config.data_collection, app_config.raw_cache_dir)
        repo = SnowReadingRepo(cfg.results_path)
        dam_mask = build_dam_mask(cfg.bbox, cfg.image_size, cfg.dam_polygon_coords)
        viz = SnowVisualizer(sh, cfg, dam_mask)
        super().__init__(repo, sh, viz, cfg.plots_dir)

        self._cfg = cfg
        self._analysis = SnowAnalysisService(cfg)
        self._evalscript = sh.load_evalscript("ndsi.js")
        self._dam_mask = dam_mask
        self._ndsi_cache: dict = {}
        print(f"  Dam mask: {int(np.sum(dam_mask))} pixels excluded from snow stats")

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
            geometry=self._cfg.geometry,
            image_size=self._cfg.image_size,
            time_from=t_from,
            time_to=t_to,
            cache_name="ndsi",
            force=force,
        )

    def compute_reading(self, t_from: str, t_to: str, ndsi_arr: np.ndarray):
        ndsi_arr[self._dam_mask] = -9999
        stats = self._analysis.compute(ndsi_arr)
        if stats is None:
            return None, ndsi_arr
        reading = SnowReading(
            date=t_from,
            date_to=t_to,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            **stats,
        )
        print(
            f"  → Snow cover: {reading.snow_cover_pct}%  "
            f"| NDSI mean: {reading.ndsi_mean}  "
            f"| Cloud: {reading.cloud_pct}%"
        )
        return reading, ndsi_arr

    def on_new_array(self, t_from: str, ndsi_arr: np.ndarray) -> None:
        self._ndsi_cache[t_from] = ndsi_arr

    def viz_filenames(self) -> list[str]:
        return ["true_color.png", "ndsi.png", "snow_mask.png", "overlay.png"]

    def run_per_date_viz(self, t_from: str, t_to: str, ndsi_arr: np.ndarray, date_dir: str) -> None:
        rgb = self._viz.fetch_true_color(
            self._cfg.geometry, self._cfg.image_size, t_from, t_to
        )
        if rgb is not None:
            self._viz.save_true_color_png(rgb, os.path.join(date_dir, "true_color.png"))
            self._viz.save_overlay_png(rgb, ndsi_arr, os.path.join(date_dir, "overlay.png"))
        self._viz.save_ndsi_png(ndsi_arr, os.path.join(date_dir, "ndsi.png"))
        self._viz.save_snow_mask_png(ndsi_arr, os.path.join(date_dir, "snow_mask.png"))

    def run_summary_viz(self, arrays: list, viz_dates: list, rebuild_manifest: bool = False) -> None:
        results_path = self._cfg.results_path
        plots_dir = self._cfg.plots_dir
        manifest_path = self._cfg.manifest_path

        self._viz.generate_time_series_chart(
            results_path, os.path.join(plots_dir, "time_series_snow.png")
        )
        all_results = self._repo.load_all()
        if len(all_results) >= 2:
            self._viz.generate_comparison_panels(
                all_results, self._ndsi_cache, self.fetch_index_array, plots_dir
            )
        self._viz.generate_multitemporal_grid(
            arrays,
            threshold=self._cfg.snow_threshold,
            pixel_color=(179, 229, 252),
            title="Snow Mask Evolution",
            out_path=os.path.join(plots_dir, "multitemporal.png"),
            dark_theme=True,
        )
        self._viz.write_manifest(viz_dates, results_path, plots_dir, manifest_path, rebuild_manifest=rebuild_manifest)

    def get_metadata(self) -> dict:
        return {"catchment": self._cfg.name}
