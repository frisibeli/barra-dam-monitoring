import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from PIL import Image

from .base import BaseVisualizer


class WaterVisualizer(BaseVisualizer):
    """Generates water monitoring PNG outputs and summary charts."""

    def __init__(self, sentinel_service, reservoir_cfg):
        evalscript = sentinel_service.load_evalscript("true_color_water.js")
        super().__init__(sentinel_service, evalscript)
        self._cfg = reservoir_cfg

    def save_water_index_png(self, index_arr: np.ndarray, path: str) -> None:
        cmap = plt.cm.RdYlGn
        norm = mcolors.Normalize(vmin=-0.5, vmax=0.8)
        rgba = (cmap(norm(index_arr)) * 255).astype(np.uint8)
        rgba[index_arr < -999] = [0, 0, 0, 0]
        Image.fromarray(rgba).save(path)

    def save_water_mask_png(self, index_arr: np.ndarray, path: str) -> None:
        h, w = index_arr.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        valid = index_arr > -999
        water = (index_arr > self._cfg.water_threshold) & valid
        rgba[water] = [30, 100, 220, 160]
        Image.fromarray(rgba).save(path)

    def save_overlay_png(self, rgb_arr: np.ndarray, index_arr: np.ndarray, path: str) -> None:
        base = rgb_arr[:, :, :3].copy() if rgb_arr.shape[2] == 4 else rgb_arr.copy()
        valid = index_arr > -999
        water = (index_arr > self._cfg.water_threshold) & valid
        overlay_color = np.array([30, 100, 220], dtype=np.float32)
        base[water] = (0.6 * base[water].astype(np.float32) + 0.4 * overlay_color).astype(np.uint8)
        Image.fromarray(base).save(path)

    def generate_time_series_chart(self, results_path: str, out_path: str) -> None:
        with open(results_path) as f:
            data = json.load(f)
        readings = data.get("readings", [])
        if not readings:
            print("    [viz] No readings for time series chart")
            return

        dates = [r["date"] for r in readings]
        areas = [r["water_area_km2"] for r in readings]

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(dates, areas, "o-", color="#1e64dc", linewidth=2, markersize=6)
        ax.fill_between(range(len(dates)), areas, alpha=0.15, color="#1e64dc")
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Water Area (km²)")
        ax.set_title(f"Water Area Time Series — {data.get('reservoir', 'reservoir').title()}")
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)

        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"    [viz] Saved time series chart → {out_path}")

    def generate_change_map(
        self,
        early_index: np.ndarray,
        late_index: np.ndarray,
        early_date: str,
        late_date: str,
        out_path: str,
    ) -> None:
        threshold = self._cfg.water_threshold
        valid_e, valid_l = early_index > -999, late_index > -999
        water_e = (early_index > threshold) & valid_e
        water_l = (late_index > threshold) & valid_l

        h, w = early_index.shape
        rgb = np.full((h, w, 3), 40, dtype=np.uint8)
        rgb[water_e & water_l] = [30, 100, 220]
        rgb[water_e & ~water_l & valid_l] = [220, 60, 60]
        rgb[~water_e & water_l & valid_e] = [60, 200, 80]

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.imshow(rgb)
        ax.set_title(f"Water Change: {early_date} → {late_date}", fontsize=13)
        ax.axis("off")
        ax.legend(handles=[
            Patch(facecolor="#1e64dc", label="Stable water"),
            Patch(facecolor="#dc3c3c", label="Water lost"),
            Patch(facecolor="#3cc850", label="Water gained"),
            Patch(facecolor="#282828", label="Land"),
        ], loc="lower right", fontsize=9)
        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"    [viz] Saved change map → {out_path}")

    def write_manifest(self, dates: list, results_path: str, plots_dir: str, manifest_path: str, rebuild_manifest: bool = False) -> None:
        self.write_viewer_manifest(
            dates=dates,
            results_path=results_path,
            plots_dir=plots_dir,
            manifest_path=manifest_path,
            bbox=self._cfg.bbox,
            image_size=self._cfg.image_size,
            image_kinds=["true_color", "water_index", "water_mask", "overlay"],
            result_key="reservoir",
            extra_fields={"water_threshold": self._cfg.water_threshold},
            rebuild=rebuild_manifest,
        )
