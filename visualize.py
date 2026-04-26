"""
Backward-compatible shim. Use visualization.water.WaterVisualizer going forward.
"""
from config import get_config
from services.sentinel_hub import SentinelHubService
from visualization.water import WaterVisualizer

_cfg = get_config()
_sh = SentinelHubService(_cfg.sh_config, _cfg.data_collection)
_viz = WaterVisualizer(_sh, _cfg.reservoir)


def fetch_true_color(time_from, time_to):
    return _viz.fetch_true_color(_cfg.reservoir.geometry, _cfg.reservoir.image_size, time_from, time_to)


def save_true_color_png(rgba, path):
    _viz.save_true_color_png(rgba, path)


def save_water_index_png(index_arr, path):
    _viz.save_water_index_png(index_arr, path)


def save_water_mask_png(index_arr, path):
    _viz.save_water_mask_png(index_arr, path)


def save_overlay_png(rgb_arr, index_arr, path):
    _viz.save_overlay_png(rgb_arr, index_arr, path)


def generate_time_series_chart(results_path, out_path):
    _viz.generate_time_series_chart(results_path, out_path)


def generate_change_map(early_index, late_index, early_date, late_date, out_path):
    _viz.generate_change_map(early_index, late_index, early_date, late_date, out_path)


def generate_multitemporal_grid(masks_by_date, out_path):
    _viz.generate_multitemporal_grid(
        masks_by_date,
        threshold=_cfg.reservoir.water_threshold,
        pixel_color=(30, 100, 220),
        title="Water Mask Evolution",
        out_path=out_path,
    )


def write_viewer_manifest(dates, results_path, plots_dir, manifest_path):
    _viz.write_manifest(dates, results_path, plots_dir, manifest_path)
