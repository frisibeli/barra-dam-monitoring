#!/usr/bin/env python3
"""Entry point for the dam water monitoring pipeline.

Usage:
    python scripts/run_water.py                              # data + visualizations
    python scripts/run_water.py --no-viz                     # data only
    python scripts/run_water.py --force                      # ignore cache, re-fetch everything
    python scripts/run_water.py --begin 2024-01-01 --end 2024-06-30  # custom date range
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config
from pipelines.water import WaterPipeline


def _validate_date(date_str: str, flag: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        sys.exit(f"ERROR: invalid date for {flag} '{date_str}': {e}")
    return date_str


def main():
    parser = argparse.ArgumentParser(description="Dam water monitoring pipeline")
    parser.add_argument("--no-viz", action="store_true", help="Skip visualization generation")
    parser.add_argument("--force", action="store_true", help="Ignore cache, re-fetch all dates")
    parser.add_argument("--rebuild-manifest", action="store_true", help="Rebuild viewer manifest from scratch (default: merge with existing)")
    parser.add_argument("--begin", metavar="YYYY-MM-DD", help="Override start date")
    parser.add_argument("--end", metavar="YYYY-MM-DD", help="Override end date")
    args = parser.parse_args()

    cfg = get_config()
    if args.begin:
        cfg.reservoir.time_start = _validate_date(args.begin, "--begin")
    if args.end:
        cfg.reservoir.time_end = _validate_date(args.end, "--end")

    print(f"\n=== Dam Water Monitor Pipeline ===")
    print(f"Reservoir: {cfg.reservoir.name}")
    print(f"Period:    {cfg.reservoir.time_start} → {cfg.reservoir.time_end}")

    WaterPipeline(cfg).run(visualize=not args.no_viz, force=args.force, rebuild_manifest=args.rebuild_manifest)


if __name__ == "__main__":
    main()
