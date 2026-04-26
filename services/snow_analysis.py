import numpy as np


class SnowAnalysisService:
    """Computes snow cover statistics from an NDSI raster."""

    def __init__(self, catchment_cfg):
        self._threshold = catchment_cfg.snow_threshold
        self._min_valid_fraction = catchment_cfg.min_valid_fraction

    def compute(self, ndsi_arr: np.ndarray) -> dict | None:
        """
        Returns stats dict or None if the scene is too cloudy.
        ndsi_arr should already have dam pixels set to -9999.
        """
        valid = ndsi_arr > -999
        valid_px = int(np.sum(valid))
        total_px = int(ndsi_arr.size)

        if valid_px < total_px * self._min_valid_fraction:
            cloud_pct = 100 * (1 - valid_px / total_px)
            print(f"  Too much cloud: {cloud_pct:.1f}% masked — skipped")
            return None

        snow = (ndsi_arr > self._threshold) & valid
        snow_px = int(np.sum(snow))
        snow_pct = round(100 * snow_px / valid_px, 2)

        ndsi_valid = np.where(valid, ndsi_arr, np.nan)
        ndsi_mean = round(float(np.nanmean(ndsi_valid)), 4)
        ndsi_max = round(float(np.nanmax(ndsi_valid)), 4)
        cloud_pct = round(100 * (1 - valid_px / total_px), 2)

        return {
            "snow_cover_pct": snow_pct,
            "ndsi_mean": ndsi_mean,
            "ndsi_max": ndsi_max,
            "snow_pixels": snow_px,
            "valid_pixels": valid_px,
            "total_pixels": total_px,
            "cloud_pct": cloud_pct,
        }
