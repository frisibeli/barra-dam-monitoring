"""Water surface elevation derivation from the Copernicus GLO-30 DEM.

The approach: pixels at the shoreline (water/land boundary) lie on the water
surface elevation contour.  Sample the DEM at those pixels and take the median.
"""
from pathlib import Path

import numpy as np

try:
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_bounds
    _RASTERIO_OK = True
except ImportError:
    _RASTERIO_OK = False


class ElevationService:
    """Derives water surface elevation from a single-band DEM GeoTIFF."""

    MIN_BOUNDARY_PIXELS = 10

    def __init__(self, dem_path: str, reservoir_cfg):
        if not _RASTERIO_OK:
            raise ImportError("rasterio is required for ElevationService")

        self._cfg = reservoir_cfg
        self._dem_arr: np.ndarray | None = None
        self._load_and_resample(dem_path)

    # ── public API ────────────────────────────────────────────────────────

    def sample_water_elevation(
        self,
        water_index_arr: np.ndarray,
        dam_mask: np.ndarray,
    ) -> float | None:
        """
        Estimate the water surface elevation (m) for one date.

        Parameters
        ----------
        water_index_arr : ndarray (H, W) float32
            Raw water index values. Non-dam pixels already set to -9999.
        dam_mask : ndarray (H, W) bool
            True where the pixel is inside the dam / reservoir polygon.

        Returns
        -------
        float | None
            Median DEM elevation at the shoreline, or None if there are too
            few boundary pixels to make a reliable estimate.
        """
        if self._dem_arr is None:
            return None

        threshold = self._cfg.water_threshold
        valid = (water_index_arr > -999) & dam_mask
        water = (water_index_arr > threshold) & valid

        # Shoreline = water pixel that has at least one non-water neighbour
        boundary = self._shoreline_mask(water, valid)
        if int(np.sum(boundary)) < self.MIN_BOUNDARY_PIXELS:
            return None

        elevations = self._dem_arr[boundary]
        elevations = elevations[np.isfinite(elevations)]
        if len(elevations) < self.MIN_BOUNDARY_PIXELS:
            return None

        return float(round(float(np.median(elevations)), 2))

    # ── helpers ───────────────────────────────────────────────────────────

    def _load_and_resample(self, dem_path: str) -> None:
        """Load DEM and resample to match the water mask grid."""
        if not Path(dem_path).exists():
            return

        cfg = self._cfg
        bbox = cfg.bbox
        w, h = cfg.image_size

        with rasterio.open(dem_path) as src:
            dst_transform = from_bounds(
                bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, w, h
            )
            dst_arr = np.empty((h, w), dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=dst_arr,
                dst_transform=dst_transform,
                dst_crs="EPSG:4326",
                resampling=Resampling.bilinear,
            )
            # Mark nodata as NaN
            nodata = src.nodata
            if nodata is not None:
                dst_arr[dst_arr == nodata] = np.nan

        self._dem_arr = dst_arr

    @staticmethod
    def _shoreline_mask(water: np.ndarray, valid: np.ndarray) -> np.ndarray:
        """Return mask of water pixels that neighbour a non-water valid pixel."""
        from numpy.lib.stride_tricks import sliding_window_view

        h, w = water.shape
        # Pad to handle edges
        padded = np.pad(water.astype(np.uint8), 1, mode="edge")
        # 4-neighbour check: up/down/left/right
        neighbours_land = (
            (~water.astype(bool)) |
            (
                (padded[:-2, 1:-1] == 0) |
                (padded[2:,  1:-1] == 0) |
                (padded[1:-1, :-2] == 0) |
                (padded[1:-1, 2:]  == 0)
            )
        )
        return water & neighbours_land & valid
