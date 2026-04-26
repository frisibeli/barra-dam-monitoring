"""
Backward-compatible shim. Use visualization.snow.SnowVisualizer going forward.
"""
from config import get_config
from services.sentinel_hub import SentinelHubService
from utils.geo import build_dam_mask
from visualization.snow import SnowVisualizer

_cfg = get_config()
_sh = SentinelHubService(_cfg.sh_config, _cfg.data_collection)
_dam_mask = build_dam_mask(
    _cfg.catchment.bbox, _cfg.catchment.image_size, _cfg.catchment.dam_polygon_coords
)
_viz = SnowVisualizer(_sh, _cfg.catchment, _dam_mask)


def fetch_true_color(time_from, time_to):
    return _viz.fetch_true_color(_cfg.catchment.geometry, _cfg.catchment.image_size, time_from, time_to)


def save_true_color_png(rgba, path):
    _viz.save_true_color_png(rgba, path)


def save_ndsi_png(ndsi_arr, path):
    _viz.save_ndsi_png(ndsi_arr, path)


def save_snow_mask_png(ndsi_arr, path):
    _viz.save_snow_mask_png(ndsi_arr, path)


def save_overlay_png(rgb_arr, ndsi_arr, path):
    _viz.save_overlay_png(rgb_arr, ndsi_arr, path)


def generate_time_series_chart(results_path, out_path):
    _viz.generate_time_series_chart(results_path, out_path)


def generate_comparison_panels(readings, ndsi_cache, fetch_ndsi_fn, plots_dir):
    _viz.generate_comparison_panels(readings, ndsi_cache, fetch_ndsi_fn, plots_dir)


def generate_multitemporal_grid(masks_by_date, out_path):
    _viz.generate_multitemporal_grid(
        masks_by_date,
        threshold=_cfg.catchment.snow_threshold,
        pixel_color=(179, 229, 252),
        title="Snow Mask Evolution",
        out_path=out_path,
        dark_theme=True,
    )


def write_viewer_manifest(dates, results_path, plots_dir, manifest_path):
    _viz.write_manifest(dates, results_path, plots_dir, manifest_path)
