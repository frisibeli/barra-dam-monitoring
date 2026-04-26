"""
scripts/fetch_dem.py — Download Copernicus GLO-30 DEM for the reservoir AOI.

Uses the public AWS S3 bucket (no auth required):
  https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/

Saves to data/dem/dem.tif clipped to the reservoir bbox.
Run once; afterwards services/elevation.py picks it up automatically.
"""
import argparse
import math
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.windows import from_bounds
from rasterio import transform as rtransform

from config import _build_config

# ---------------------------------------------------------------------------
# GLO-30 tile URL helpers
# ---------------------------------------------------------------------------

_BASE = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"


def _tile_url(lat: int, lon: int) -> str:
    """Return the direct HTTPS URL for a 1°×1° GLO-30 tile."""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    lat_s = f"{abs(lat):02d}"
    lon_s = f"{abs(lon):03d}"
    name = f"Copernicus_DSM_COG_10_{ns}{lat_s}_00_{ew}{lon_s}_00_DEM"
    return f"{_BASE}/{name}/{name}.tif"


def _tiles_for_bbox(min_lon, min_lat, max_lon, max_lat):
    """Enumerate all 1°×1° tiles that cover the bbox."""
    lats = range(math.floor(min_lat), math.ceil(max_lat))
    lons = range(math.floor(min_lon), math.ceil(max_lon))
    return [(lat, lon) for lat in lats for lon in lons]


# ---------------------------------------------------------------------------
# Download + clip
# ---------------------------------------------------------------------------

def fetch_dem(bbox, out_path: Path, force: bool = False) -> None:
    """Download GLO-30 tiles covering *bbox* and clip to bbox, save to *out_path*."""
    if out_path.exists() and not force:
        print(f"DEM already exists at {out_path}  (use --force to re-download)")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)

    tiles = _tiles_for_bbox(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    print(f"Fetching {len(tiles)} GLO-30 tile(s) for bbox "
          f"[{bbox.min_x:.4f},{bbox.min_y:.4f} → {bbox.max_x:.4f},{bbox.max_y:.4f}]")

    tmp_dir = out_path.parent / "_tmp_tiles"
    tmp_dir.mkdir(exist_ok=True)
    tile_paths = []

    for lat, lon in tiles:
        url = _tile_url(lat, lon)
        tile_path = tmp_dir / f"tile_{lat}_{lon}.tif"
        if not tile_path.exists():
            print(f"  Downloading {url}")
            try:
                urllib.request.urlretrieve(url, tile_path)
            except Exception as exc:
                print(f"  ERROR downloading tile ({lat},{lon}): {exc}")
                continue
        else:
            print(f"  Cached tile: {tile_path.name}")
        tile_paths.append(tile_path)

    if not tile_paths:
        print("ERROR: no tiles downloaded.", file=sys.stderr)
        sys.exit(1)

    # Merge tiles and clip to bbox
    opened = [rasterio.open(p) for p in tile_paths]
    mosaic, mosaic_transform = merge(opened)

    for ds in opened:
        ds.close()

    # Write full merged tile first then window-crop
    merged_path = tmp_dir / "merged.tif"
    profile = rasterio.open(tile_paths[0]).profile.copy()
    profile.update(
        driver="GTiff",
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        transform=mosaic_transform,
        compress="deflate",
    )
    with rasterio.open(merged_path, "w", **profile) as dst:
        dst.write(mosaic)

    # Clip to bbox
    with rasterio.open(merged_path) as src:
        window = from_bounds(
            bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y,
            transform=src.transform,
        )
        clipped = src.read(window=window)
        clip_transform = src.window_transform(window)
        out_profile = src.profile.copy()
        out_profile.update(
            height=clipped.shape[1],
            width=clipped.shape[2],
            transform=clip_transform,
            compress="deflate",
        )
        with rasterio.open(out_path, "w", **out_profile) as dst:
            dst.write(clipped)

    print(f"DEM saved → {out_path}  ({clipped.shape[2]}×{clipped.shape[1]} px)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Download GLO-30 DEM for reservoir AOI")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument("--out", default=None, help="Output path (default: data/dem/dem.tif)")
    args = parser.parse_args()

    cfg = _build_config()
    out_path = Path(args.out) if args.out else ROOT / "data" / "dem" / "dem.tif"

    fetch_dem(cfg.reservoir.bbox, out_path, force=args.force)


if __name__ == "__main__":
    main()
