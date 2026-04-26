#!/usr/bin/env python3
"""Entry point for the InSAR deformation monitoring pipeline.

This runs the validated legacy InSAR step logic through dam-monitor structure.

Usage:
    python scripts/run_insar.py
    python scripts/run_insar.py --step search
    python scripts/run_insar.py --dry-run
    python scripts/run_insar.py --force
    python scripts/run_insar.py --migrate-data
    python scripts/run_insar.py --orbit-discover
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config
from pipelines.insar import InSARPipeline


def main():
    parser = argparse.ArgumentParser(description="InSAR deformation monitoring pipeline")
    parser.add_argument(
        "--step",
        default="all",
        choices=[
            "all",
            "search",
            "pair",
            "prepare",
            "submit",
            "download",
            "process",
            "timeseries",
            "export",
        ],
        help="Which pipeline step to run (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without submitting jobs or downloading",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached outputs and reprocess from scratch",
    )
    parser.add_argument(
        "--orbit-discover",
        action="store_true",
        help="Auto-discover available relative orbits for AOI and exit",
    )
    parser.add_argument(
        "--migrate-data",
        action="store_true",
        help="Copy existing insar_pipeline outputs into dam-monitor data area",
    )
    parser.add_argument(
        "--migrate-overwrite",
        action="store_true",
        help="When used with --migrate-data, replace existing migrated folders",
    )
    parser.add_argument(
        "--include-tmp",
        action="store_true",
        help="When used with --migrate-data, also migrate outputs_tmp",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cfg = get_config()
    print("\n=== InSAR Pipeline (dam-monitor) ===")
    print(f"Job:      {cfg.insar.job_name}")
    print(f"Orbit:    {cfg.insar.relative_orbit} {cfg.insar.flight_direction}")
    print(f"Period:   {cfg.insar.start_date} -> {cfg.insar.end_date}")
    print(f"Output:   {cfg.insar.output_dir}")

    pipeline = InSARPipeline(cfg)

    if args.migrate_data:
        summary = pipeline.migrate_existing_data(
            overwrite=args.migrate_overwrite,
            include_tmp=args.include_tmp,
        )
        print("\nData migration summary:")
        print(f"  outputs migrated:      {summary['outputs_migrated']}")
        print(f"  outputs mode:          {summary['outputs_mode']}")
        print(f"  outputs_tmp migrated:  {summary['outputs_tmp_migrated']}")
        print(f"  outputs_tmp mode:      {summary['outputs_tmp_mode']}")
        print(f"  outputs_tmp skipped:   {summary['outputs_tmp_skipped']}")
        print(f"  target output dir:     {summary['target_output_dir']}")
        print(f"  target outputs_tmp dir:{summary['target_outputs_tmp_dir']}")

    if args.orbit_discover:
        pipeline.discover_orbits()
        return

    pipeline.run(step=args.step, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
