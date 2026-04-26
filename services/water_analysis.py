import math

import numpy as np

from models.reading import WaterReading


class WaterAnalysisService:
    """Computes water area statistics from a water-index raster."""

    def __init__(self, reservoir_cfg):
        self._threshold = reservoir_cfg.water_threshold
        self._max_cloud = reservoir_cfg.max_cloud_cover
        self._image_size = reservoir_cfg.image_size
        self._bbox = reservoir_cfg.bbox

    def compute(self, index_arr: np.ndarray, dam_mask: np.ndarray) -> dict | None:
        """
        Returns stats dict or None if a quality gate rejects the scene.
        index_arr must already have non-dam pixels set to -9999.
        """
        dam_pixels = int(np.sum(dam_mask))
        valid_mask = (index_arr > -999) & dam_mask
        water_mask = (index_arr > self._threshold) & valid_mask

        total_valid = int(np.sum(valid_mask))
        water_pixels = int(np.sum(water_mask))

        bbox = self._bbox
        lon_span_deg = bbox.max_x - bbox.min_x
        lat_span_deg = bbox.max_y - bbox.min_y
        mid_lat = (bbox.min_y + bbox.max_y) / 2
        m_per_deg_lat = 111_320
        m_per_deg_lon = 111_320 * math.cos(math.radians(mid_lat))
        pixel_w_m = lon_span_deg * m_per_deg_lon / self._image_size[0]
        pixel_h_m = lat_span_deg * m_per_deg_lat / self._image_size[1]
        water_area_km2 = water_pixels * pixel_w_m * pixel_h_m / 1_000_000

        cloud_pct = round(100 * (1 - total_valid / dam_pixels), 2) if dam_pixels > 0 else 100.0

        if cloud_pct > self._max_cloud:
            print(
                f"  → Rejected: cloud cover over AOI is {cloud_pct}% "
                f"(threshold {self._max_cloud}%) — scene-level metadata was misleading"
            )
            return None

        if water_area_km2 < 2:
            print(
                f"  → Rejected: water area {water_area_km2:.4f} km² "
                f"below minimum threshold (2 km²) — likely a bad scene"
            )
            return None

        return {
            "water_area_km2": round(float(water_area_km2), 4),
            "water_pixels": water_pixels,
            "total_pixels": dam_pixels,
            "valid_pixels": total_valid,
            "cloud_pct": cloud_pct,
        }
