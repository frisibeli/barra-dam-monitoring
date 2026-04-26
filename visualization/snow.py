import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from .base import BaseVisualizer

_SNOW_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "snow", ["#2C1810", "#8B6358", "#F5F0E8", "#B3E5FC", "#0277BD"], N=512
)


class SnowVisualizer(BaseVisualizer):
    """Generates snow monitoring PNG outputs and summary charts."""

    def __init__(self, sentinel_service, catchment_cfg, dam_mask):
        evalscript = sentinel_service.load_evalscript("true_color_snow.js")
        super().__init__(sentinel_service, evalscript)
        self._cfg = catchment_cfg
        self._dam_mask = dam_mask

    def save_ndsi_png(self, ndsi_arr: np.ndarray, path: str) -> None:
        norm = mcolors.Normalize(vmin=-0.3, vmax=0.9)
        rgba = (_SNOW_CMAP(norm(ndsi_arr)) * 255).astype(np.uint8)
        rgba[ndsi_arr < -999] = [0, 0, 0, 0]
        Image.fromarray(rgba).save(path)

    def save_snow_mask_png(self, ndsi_arr: np.ndarray, path: str) -> None:
        h, w = ndsi_arr.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        valid = ndsi_arr > -999
        snow = (ndsi_arr > self._cfg.snow_threshold) & valid
        rgba[snow] = [179, 229, 252, 160]
        Image.fromarray(rgba).save(path)

    def save_overlay_png(self, rgb_arr: np.ndarray, ndsi_arr: np.ndarray, path: str) -> None:
        base = rgb_arr[:, :, :3].copy() if rgb_arr.shape[2] == 4 else rgb_arr.copy()
        valid = ndsi_arr > -999
        snow = (ndsi_arr > self._cfg.snow_threshold) & valid
        overlay_color = np.array([179, 229, 252], dtype=np.float32)
        base[snow] = (0.6 * base[snow].astype(np.float32) + 0.4 * overlay_color).astype(np.uint8)
        Image.fromarray(base).save(path)

    def generate_time_series_chart(self, results_path: str, out_path: str) -> None:
        with open(results_path) as f:
            data = json.load(f)
        readings = data.get("readings", [])
        if not readings:
            print("    [viz] No readings for time series chart")
            return

        dates = [r["date"] for r in readings]
        snow_pcts = [r["snow_cover_pct"] for r in readings]
        ndsi_means = [r["ndsi_mean"] for r in readings]
        x = range(len(dates))

        fig, ax1 = plt.subplots(figsize=(14, 5), facecolor="#0f1117")
        ax1.set_facecolor("#0f1117")
        ax1.fill_between(x, snow_pcts, alpha=0.15, color="#B3E5FC")
        ax1.plot(x, snow_pcts, color="#B3E5FC", linewidth=2, marker="o", markersize=5, label="Snow cover %")
        for i, pct in enumerate(snow_pcts):
            color = "#FFFFFF" if pct > 50 else "#B3E5FC" if pct > 20 else "#546E7A"
            ax1.plot(i, pct, "o", color=color, markersize=7, zorder=5)

        ax2 = ax1.twinx()
        ax2.plot(x, ndsi_means, color="#78909C", linewidth=1.2, linestyle="--",
                 marker="s", markersize=3, label="NDSI mean", alpha=0.7)
        ax2.set_ylabel("NDSI mean", color="#78909C", fontsize=10)
        ax2.tick_params(colors="#78909C")
        ax2.set_ylim(-0.3, 0.9)

        ax1.set_xticks(list(x))
        ax1.set_xticklabels(dates, rotation=45, ha="right", color="#aaa", fontsize=9)
        ax1.set_ylabel("Snow cover (%)", color="#aaa", fontsize=10)
        ax1.set_ylim(0, 105)
        ax1.tick_params(colors="#aaa")
        for spine in ax1.spines.values():
            spine.set_edgecolor("#333")

        peak_i = snow_pcts.index(max(snow_pcts))
        ax1.annotate(
            f"Peak: {snow_pcts[peak_i]:.1f}%",
            xy=(peak_i, snow_pcts[peak_i]),
            xytext=(peak_i + 0.4, min(snow_pcts[peak_i] + 5, 100)),
            color="white", fontsize=9,
            arrowprops=dict(arrowstyle="->", color="#aaa", lw=0.8),
        )

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, facecolor="#1a1a2e", labelcolor="white", fontsize=9)
        ax1.set_title("Ogosta upstream catchment — snow cover over time", color="white", fontsize=13)

        plt.tight_layout()
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"    [viz] Saved time series chart → {out_path}")

    def generate_comparison_panels(
        self,
        readings: list,
        ndsi_cache: dict,
        fetch_ndsi_fn,
        plots_dir: str,
    ) -> None:
        snow_pcts = [r["snow_cover_pct"] if isinstance(r, dict) else r.snow_cover_pct for r in readings]
        records = [readings[snow_pcts.index(max(snow_pcts))], readings[snow_pcts.index(min(snow_pcts))]]
        paths = [os.path.join(plots_dir, "compare_high.png"), os.path.join(plots_dir, "compare_low.png")]

        for record, path in zip(records, paths):
            t_from = record["date"] if isinstance(record, dict) else record.date
            t_to = record["date_to"] if isinstance(record, dict) else record.date_to
            snow_pct = record["snow_cover_pct"] if isinstance(record, dict) else record.snow_cover_pct

            ndsi_arr = ndsi_cache.get(t_from)
            if ndsi_arr is None:
                ndsi_arr = fetch_ndsi_fn(t_from, t_to)
                if ndsi_arr is not None:
                    ndsi_arr[self._dam_mask] = -9999

            rgb = self._sentinel.fetch_true_color(
                self._tc_evalscript, self._cfg.geometry, self._cfg.image_size, t_from, t_to
            )
            if ndsi_arr is None or rgb is None:
                continue

            valid = ndsi_arr > -999
            snow = (ndsi_arr > self._cfg.snow_threshold) & valid

            fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor="#0f1117")
            for ax in axes:
                ax.set_xticks([])
                ax.set_yticks([])
                ax.set_facecolor("#0f1117")

            axes[0].imshow(rgb)
            axes[0].set_title(f"True color  ·  {t_from}", color="white", fontsize=10)
            axes[1].imshow(rgb)
            overlay = np.zeros((*snow.shape, 4), dtype=np.float32)
            overlay[snow] = [0.70, 0.92, 1.00, 0.65]
            axes[1].imshow(overlay)
            axes[1].set_title(f"Snow mask  ·  {snow_pct:.1f}% covered", color="#B3E5FC", fontsize=10)

            plt.tight_layout()
            fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            print(f"    [viz] Saved comparison → {path}")

    def write_manifest(self, dates: list, results_path: str, plots_dir: str, manifest_path: str, rebuild_manifest: bool = False) -> None:
        self.write_viewer_manifest(
            dates=dates,
            results_path=results_path,
            plots_dir=plots_dir,
            manifest_path=manifest_path,
            bbox=self._cfg.bbox,
            image_size=self._cfg.image_size,
            image_kinds=["true_color", "ndsi", "snow_mask", "overlay"],
            result_key="catchment",
            extra_fields={
                "snow_threshold": self._cfg.snow_threshold,
                "polygon": [[c[1], c[0]] for c in self._cfg.polygon_coords],
            },
            rebuild=rebuild_manifest,
        )
