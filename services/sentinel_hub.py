from pathlib import Path

import numpy as np
from sentinelhub import (
    BBox,
    SentinelHubCatalog,
    SentinelHubRequest,
    MimeType,
    MosaickingOrder,
)

_EVALSCRIPTS_DIR = Path(__file__).resolve().parent.parent / "evalscripts"


def _load_evalscript(filename: str) -> str:
    return (_EVALSCRIPTS_DIR / filename).read_text()


class SentinelHubService:
    """Wraps Sentinel Hub catalog search and imagery fetch."""

    def __init__(self, sh_config, data_collection, raw_cache_dir: str | None = None):
        self._sh_config = sh_config
        self._collection = data_collection
        self._raw_cache_dir = raw_cache_dir

    def search_available_windows(
        self,
        bbox,
        time_start: str,
        time_end: str,
        time_delta: int,
        max_cloud_cover: int,
    ) -> list[tuple[str, str]]:
        """Return (date_from, date_to) windows that have at least one clear scene."""
        from datetime import datetime, timedelta

        catalog = SentinelHubCatalog(config=self._sh_config)
        start = datetime.strptime(time_start, "%Y-%m-%d")
        end = datetime.strptime(time_end, "%Y-%m-%d")

        windows = []
        current = start
        while current < end:
            window_end = current + timedelta(days=time_delta)
            windows.append((
                current.strftime("%Y-%m-%d"),
                min(window_end, end).strftime("%Y-%m-%d"),
            ))
            current = window_end

        valid = []
        for t_from, t_to in windows:
            results = list(catalog.search(
                collection=self._collection,
                bbox=bbox,
                time=(t_from, t_to),
                filter=f"eo:cloud_cover < {max_cloud_cover}",
                limit=1,
            ))
            if results:
                valid.append((t_from, t_to))
                print(f"  Found scene: {t_from} → {t_to}")
            else:
                print(f"  No clear scene: {t_from} → {t_to} (skipped)")

        return valid

    def fetch_index_array(
        self,
        evalscript: str,
        geometry,
        image_size: tuple,
        time_from: str,
        time_to: str,
        cache_name: str | None = None,
        force: bool = False,
    ) -> np.ndarray | None:
        """Generic single-band float32 fetch (water index, NDSI, etc.)."""
        cache_path = self._index_cache_path(cache_name, time_from, time_to)
        if cache_path and not force and cache_path.exists():
            print(f"  [raw cache] {time_from} → {time_to}  ({cache_name})")
            return np.load(cache_path)

        area_kwargs = {"bbox": geometry} if isinstance(geometry, BBox) else {"geometry": geometry}
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=self._collection,
                    time_interval=(time_from, time_to),
                    mosaicking_order=MosaickingOrder.LEAST_CC,
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
            **area_kwargs,
            size=image_size,
            config=self._sh_config,
        )
        try:
            data = request.get_data()
            arr = data[0]
            if arr.ndim == 3:
                arr = arr[:, :, 0]
            arr = arr.astype(np.float32)
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                np.save(cache_path, arr)
            return arr
        except Exception as e:
            print(f"  Fetch failed for {time_from}: {e}")
            return None

    def _index_cache_path(
        self, cache_name: str | None, time_from: str, time_to: str
    ) -> "Path | None":
        if not cache_name or not self._raw_cache_dir:
            return None
        return Path(self._raw_cache_dir) / cache_name / f"{time_from}_{time_to}.npy"

    def fetch_true_color(
        self,
        evalscript: str,
        geometry,
        image_size: tuple,
        time_from: str,
        time_to: str,
    ) -> np.ndarray | None:
        """RGBA uint8 true-color fetch."""
        area_kwargs = {"bbox": geometry} if isinstance(geometry, BBox) else {"geometry": geometry}
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=self._collection,
                    time_interval=(time_from, time_to),
                    mosaicking_order=MosaickingOrder.LEAST_CC,
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
            **area_kwargs,
            size=image_size,
            config=self._sh_config,
        )
        try:
            data = request.get_data()
            arr = data[0]
            if arr.ndim == 2:
                arr = np.stack([arr, arr, arr, np.full_like(arr, 255)], axis=-1)
            return arr.astype(np.uint8)
        except Exception as e:
            print(f"    [viz] True color fetch failed for {time_from}: {e}")
            return None

    @staticmethod
    def load_evalscript(filename: str) -> str:
        return _load_evalscript(filename)
