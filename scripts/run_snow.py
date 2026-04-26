#!/usr/bin/env python3
"""Entry point for the catchment snow monitoring pipeline.

Usage:
    python scripts/run_snow.py                              # data + visualizations
    python scripts/run_snow.py --no-viz                     # data only
    python scripts/run_snow.py --force                      # ignore cache, re-fetch everything
    python scripts/run_snow.py --begin 2024-01-01 --end 2024-06-30  # custom date range
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config
from pipelines.snow import SnowPipeline


def main():
    parser = argparse.ArgumentParser(description="Ogosta catchment snow cover pipeline")
    parser.add_argument("--no-viz", action="store_true", help="Skip visualization generation")
    parser.add_argument("--force", action="store_true", help="Ignore cache, re-fetch all dates")
    parser.add_argument("--rebuild-manifest", action="store_true", help="Rebuild viewer manifest from scratch (default: merge with existing)")
    parser.add_argument("--begin", metavar="YYYY-MM-DD", help="Override start date")
    parser.add_argument("--end", metavar="YYYY-MM-DD", help="Override end date")
    args = parser.parse_args()

    cfg = get_config()
    if args.begin:
        cfg.catchment.time_start = args.begin
    if args.end:
        cfg.catchment.time_end = args.end

    print(f"\n=== Ogosta Catchment Snow Pipeline ===")
    print(f"Catchment: {cfg.catchment.name}")
    print(f"Period:    {cfg.catchment.time_start} → {cfg.catchment.time_end}")

    SnowPipeline(cfg).run(visualize=not args.no_viz, force=args.force, rebuild_manifest=args.rebuild_manifest)


if __name__ == "__main__":
    main()
