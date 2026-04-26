"""
scripts/backfill_elevation.py — Backfill elevation_m into existing water readings.

Strategy:
  1. Load all water readings from data/results.json
  2. For each reading without elevation_m:
     a. Check data/raw/water_index/{t_from}_{t_to}.npy — load if present
     b. If no .npy, fetch the water index array from Sentinel Hub and cache it
  3. Compute elevation with ElevationService and upsert into data/results.json

Requires data/dem/dem.tif (run scripts/fetch_dem.py first).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from config import _build_config
from repositories.water_repo import WaterReadingRepo
from services.elevation import ElevationService
from services.sentinel_hub import SentinelHubService
from utils.geo import build_dam_mask


def main():
    parser = argparse.ArgumentParser(description="Backfill elevation_m into water readings")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Skip Sentinel Hub fetch; only process cached .npy files")
    args = parser.parse_args()

    cfg = _build_config()
    res_cfg = cfg.reservoir

    dem_path = Path(cfg.raw_cache_dir).parent / "dem" / "dem.tif"
    if not dem_path.exists():
        print(f"ERROR: DEM not found at {dem_path}")
        print("Run:  python scripts/fetch_dem.py")
        sys.exit(1)

    print(f"Loading ElevationService from {dem_path}")
    elev_svc = ElevationService(str(dem_path), res_cfg)

    dam_mask = build_dam_mask(res_cfg.bbox, res_cfg.image_size, res_cfg.polygon_coords)
    print(f"Dam mask: {int(np.sum(dam_mask))} pixels inside reservoir\n")

    repo = WaterReadingRepo(res_cfg.results_path)
    readings_by_key = repo.load_as_cache()
    if not readings_by_key:
        print("No water readings found — nothing to backfill.")
        sys.exit(0)
    print(f"Loaded {len(readings_by_key)} existing readings from {res_cfg.results_path}\n")

    raw_dir = Path(cfg.raw_cache_dir) / "water_index"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Build Sentinel Hub service for on-demand fetches
    sh_svc = None
    if not args.no_fetch:
        sh_svc = SentinelHubService(cfg.sh_config, cfg.data_collection, cfg.raw_cache_dir)
        evalscript = sh_svc.load_evalscript("water_index.js")

    updated = 0
    skipped = 0
    failed = 0
    fetched = 0

    for cache_key, reading in sorted(readings_by_key.items(), key=lambda x: x[1].date):
        t_from, t_to = reading.date, reading.date_to

        if reading.elevation_m is not None:
            print(f"  [ok]   {t_from}  elevation already set: {reading.elevation_m} m")
            skipped += 1
            continue

        # Check for cached .npy
        npy_path = raw_dir / f"{t_from}_{t_to}.npy"
        arr = None

        if npy_path.exists():
            arr = np.load(npy_path)
            print(f"  [npy]  {t_from} → {t_to}  loaded from cache")
        elif sh_svc is not None:
            print(f"  [api]  {t_from} → {t_to}  fetching from Sentinel Hub...")
            try:
                arr = sh_svc.fetch_index_array(
                    evalscript=evalscript,
                    geometry=res_cfg.geometry,
                    image_size=res_cfg.image_size,
                    time_from=t_from,
                    time_to=t_to,
                    cache_name="water_index",
                    force=False,
                )
                if arr is not None:
                    fetched += 1
            except Exception as exc:
                print(f"  [ERR]  {t_from}: fetch failed — {exc}")
                failed += 1
                continue
        else:
            print(f"  [skip] {t_from}  (no .npy and --no-fetch set)")
            skipped += 1
            continue

        if arr is None:
            print(f"  [skip] {t_from}  (fetch returned None)")
            skipped += 1
            continue

        arr_masked = arr.copy()
        arr_masked[~dam_mask] = -9999

        elev = elev_svc.sample_water_elevation(arr_masked, dam_mask)
        if elev is None:
            print(f"  [null] {t_from}  (insufficient shoreline pixels)")
            failed += 1
            continue

        reading.elevation_m = elev
        print(f"  [set]  {t_from}  elevation_m = {elev} m")
        updated += 1

    print(f"\nSummary: {updated} updated, {skipped} skipped, {failed} null"
          + (f", {fetched} fetched from API" if fetched else ""))

    if args.dry_run:
        print("Dry run — no changes written.")
        return

    if updated > 0:
        try:
            with open(res_cfg.results_path) as f:
                raw = json.load(f)
            metadata = {k: v for k, v in raw.items() if k != "readings"}
        except Exception:
            from datetime import datetime, timezone
            metadata = {"generated": datetime.now(timezone.utc).isoformat()}

        all_readings = list(readings_by_key.values())
        repo.save_all(all_readings, metadata)
        print(f"Saved {len(all_readings)} readings to {res_cfg.results_path}")
    else:
        print("Nothing to write.")


if __name__ == "__main__":
    main()
