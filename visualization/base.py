import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


class BaseVisualizer:
    """Shared rendering utilities: multitemporal grid and viewer manifest."""

    def __init__(self, sentinel_service, evalscript: str):
        self._sentinel = sentinel_service
        self._tc_evalscript = evalscript

    def fetch_true_color(self, geometry, image_size, time_from, time_to):
        return self._sentinel.fetch_true_color(
            self._tc_evalscript, geometry, image_size, time_from, time_to
        )

    @staticmethod
    def save_true_color_png(rgba: np.ndarray, path: str) -> None:
        Image.fromarray(rgba).save(path)

    def generate_multitemporal_grid(
        self,
        arrays_by_date: list,
        threshold: float,
        pixel_color: tuple,
        title: str,
        out_path: str,
        dark_theme: bool = False,
    ) -> None:
        """
        Small-multiples grid for water or snow mask evolution.
        pixel_color: RGB tuple for the detected pixels (water blue or snow ice-blue).
        """
        n = len(arrays_by_date)
        if n == 0:
            return

        cols = min(5, n)
        rows = math.ceil(n / cols)

        fig_kwargs = {"figsize": (3.2 * cols, 3.2 * rows)}
        if dark_theme:
            fig_kwargs["facecolor"] = "#0f1117"

        fig, axes = plt.subplots(rows, cols, **fig_kwargs)
        if rows == 1 and cols == 1:
            axes = np.array([[axes]])
        elif rows == 1:
            axes = axes[np.newaxis, :]
        elif cols == 1:
            axes = axes[:, np.newaxis]

        for idx, (date, arr) in enumerate(arrays_by_date):
            r, c = divmod(idx, cols)
            ax = axes[r, c]

            valid = arr > -999
            detected = (arr > threshold) & valid

            h, w = arr.shape
            rgb = np.full((h, w, 3), 40, dtype=np.uint8)
            rgb[detected] = list(pixel_color)
            rgb[~valid] = [0, 0, 0]

            ax.imshow(rgb)
            title_color = "#ccc" if dark_theme else "black"
            ax.set_title(date, fontsize=9, pad=3, color=title_color)
            ax.axis("off")

        for idx in range(n, rows * cols):
            r, c = divmod(idx, cols)
            axes[r, c].axis("off")

        suptitle_kwargs = {"fontsize": 14, "y": 1.01}
        if dark_theme:
            suptitle_kwargs["color"] = "white"
        fig.suptitle(title, **suptitle_kwargs)
        plt.tight_layout()

        save_kwargs = {"dpi": 150, "bbox_inches": "tight"}
        if dark_theme:
            save_kwargs["facecolor"] = fig.get_facecolor()
        plt.savefig(out_path, **save_kwargs)
        plt.close(fig)
        print(f"    [viz] Saved multi-temporal grid → {out_path}")

    @staticmethod
    def write_viewer_manifest(
        dates: list,
        results_path: str,
        plots_dir: str,
        manifest_path: str,
        bbox,
        image_size: tuple,
        image_kinds: list,
        result_key: str,
        extra_fields: dict | None = None,
        rebuild: bool = False,
    ) -> None:
        """
        Write a JSON manifest consumed by an HTML viewer.
        result_key: the key to look up in results JSON (e.g. "reservoir" or "catchment").
        image_kinds: list of image names (e.g. ["true_color", "water_index", ...]).
        extra_fields: optional extra fields to merge into the manifest root.
        rebuild: if False (default), merges with the existing manifest so prior dates
                 are preserved; if True, rebuilds from scratch with only `dates`.
        """
        manifest = {
            result_key: None,
            "bbox": {
                "south": bbox.min_y,
                "west": bbox.min_x,
                "north": bbox.max_y,
                "east": bbox.max_x,
            },
            "image_size": list(image_size),
            "dates": [],
        }
        if extra_fields:
            manifest.update(extra_fields)

        try:
            with open(results_path) as f:
                manifest[result_key] = json.load(f).get(result_key, "unknown")
        except Exception:
            manifest[result_key] = "unknown"

        # Load existing date entries to preserve history (unless rebuilding).
        existing_by_date: dict = {}
        if not rebuild and os.path.exists(manifest_path):
            try:
                with open(manifest_path) as f:
                    existing_by_date = {
                        e["date"]: e for e in json.load(f).get("dates", [])
                    }
            except Exception:
                pass

        for date in dates:
            date_dir = os.path.join(plots_dir, date)
            entry = {"date": date, "images": {}}
            for kind in image_kinds:
                img_path = os.path.join(date_dir, f"{kind}.png")
                if os.path.exists(img_path):
                    entry["images"][kind] = os.path.relpath(img_path, ".")
            existing_by_date[date] = entry

        manifest["dates"] = sorted(existing_by_date.values(), key=lambda e: e["date"])

        os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"    [viz] Saved viewer manifest → {manifest_path} ({len(manifest['dates'])} dates)")
