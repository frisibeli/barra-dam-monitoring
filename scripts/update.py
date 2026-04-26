#!/usr/bin/env python3
"""Advance all pipelines from their last stored record to today.

Usage:
    python scripts/update.py                          # all pipelines + visualizations
    python scripts/update.py --no-viz                 # skip visualizations
    python scripts/update.py --skip insar volume      # skip specific pipelines
    python scripts/update.py --dry-run                # print plan, don't execute
    python scripts/update.py --force                  # clear caches, re-fetch everything
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config


# ── helpers: resolve last-record dates ───────────────────────────────────────

def _last_water_date(cfg) -> str | None:
    from repositories.water_repo import WaterReadingRepo
    readings = WaterReadingRepo(cfg.reservoir.results_path).load_all()
    if not readings:
        return None
    return max(readings, key=lambda r: r.date).date_to


def _last_snow_date(cfg) -> str | None:
    from repositories.snow_repo import SnowReadingRepo
    readings = SnowReadingRepo(cfg.catchment.results_path).load_all()
    if not readings:
        return None
    return max(readings, key=lambda r: r.date).date_to


def _last_volume_date(cfg) -> date | None:
    from repositories.volume_repo import VolumeRepo
    readings = VolumeRepo(cfg.mosv.results_path).load_all()
    if not readings:
        return None
    return date.fromisoformat(max(readings, key=lambda r: r.date).date)


def _last_insar_scene_date(cfg) -> str | None:
    scenes_path = os.path.join(cfg.insar.output_dir, "scenes.json")
    if not os.path.exists(scenes_path):
        return None
    scenes = json.load(open(scenes_path))
    if isinstance(scenes, dict):
        scenes = scenes.get("scenes", [])
    dates = [s["date"] for s in scenes if "date" in s]
    return max(dates) if dates else None


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Advance all dam-monitor pipelines from their last record to today.",
    )
    parser.add_argument("--no-viz", action="store_true", help="Skip visualization generation")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    parser.add_argument("--force", action="store_true", help="Ignore caches, re-fetch everything")
    parser.add_argument(
        "--skip",
        nargs="+",
        choices=["water", "snow", "volume", "insar"],
        default=[],
        metavar="PIPELINE",
        help="One or more pipelines to skip: water snow volume insar",
    )
    args = parser.parse_args()

    today = date.today().isoformat()
    cfg = get_config()
    skip = set(args.skip)

    # Resolve resume-from dates for each pipeline
    water_start  = _last_water_date(cfg)       or cfg.reservoir.time_start
    snow_start   = _last_snow_date(cfg)         or cfg.catchment.time_start
    vol_last     = _last_volume_date(cfg)
    vol_start    = (vol_last + timedelta(days=1)).isoformat() if vol_last else cfg.mosv.default_start
    insar_start  = _last_insar_scene_date(cfg)  or cfg.insar.start_date

    plan = [
        ("water",  water_start, today),
        ("snow",   snow_start,  today),
        ("volume", vol_start,   today),
        ("insar",  insar_start, today),
    ]

    # Print summary
    print(f"\n{'='*62}")
    print(f"  Dam Monitor — Update to Today ({today})")
    print(f"{'='*62}")
    for name, start, end in plan:
        tag = "SKIP" if name in skip else "RUN "
        print(f"  [{tag}] {name:8s}  {start} → {end}")
    print(f"  Visualize: {'no' if args.no_viz else 'yes'}"
          f"  |  Force: {'yes' if args.force else 'no'}"
          f"  |  Dry-run: {'yes' if args.dry_run else 'no'}")
    print(f"{'='*62}\n")

    if args.dry_run:
        print("[dry-run] No pipelines executed.")
        return

    errors: list[tuple[str, Exception]] = []

    def _section(name, start, end):
        print(f"\n{'─'*62}")
        print(f"  {name.upper():8s}  {start} → {end}")
        print(f"{'─'*62}")

    # ── Water ─────────────────────────────────────────────────────────────
    if "water" not in skip:
        _section("water", water_start, today)
        try:
            cfg.reservoir.time_start = water_start
            cfg.reservoir.time_end   = today
            from pipelines.water import WaterPipeline
            WaterPipeline(cfg).run(visualize=not args.no_viz, force=args.force)
        except Exception as e:
            print(f"  [ERROR] Water pipeline failed: {e}")
            errors.append(("water", e))

    # ── Snow ──────────────────────────────────────────────────────────────
    if "snow" not in skip:
        _section("snow", snow_start, today)
        try:
            cfg.catchment.time_start = snow_start
            cfg.catchment.time_end   = today
            from pipelines.snow import SnowPipeline
            SnowPipeline(cfg).run(visualize=not args.no_viz, force=args.force)
        except Exception as e:
            print(f"  [ERROR] Snow pipeline failed: {e}")
            errors.append(("snow", e))

    # ── Volume ────────────────────────────────────────────────────────────
    if "volume" not in skip:
        _section("volume", vol_start, today)
        try:
            from pipelines.volume import VolumePipeline
            VolumePipeline(cfg.mosv).run(
                start=date.fromisoformat(vol_start),
                end=date.fromisoformat(today),
                force=args.force,
            )
        except Exception as e:
            print(f"  [ERROR] Volume pipeline failed: {e}")
            errors.append(("volume", e))

    # ── InSAR ─────────────────────────────────────────────────────────────
    if "insar" not in skip:
        _section("insar", insar_start, today)
        try:
            cfg.insar.start_date = insar_start
            cfg.insar.end_date   = today
            from pipelines.insar import InSARPipeline
            InSARPipeline(cfg).run(force=args.force)
        except Exception as e:
            print(f"  [ERROR] InSAR pipeline failed: {e}")
            errors.append(("insar", e))

    # ── Summary ───────────────────────────────────────────────────────────
    ran = [name for name, _, _ in plan if name not in skip]
    failed = [name for name, _ in errors]
    succeeded = [name for name in ran if name not in failed]

    print(f"\n{'='*62}")
    print(f"  Done.  {len(succeeded)}/{len(ran)} pipelines succeeded.")
    if succeeded:
        print(f"  OK:     {', '.join(succeeded)}")
    if failed:
        print(f"  FAILED: {', '.join(failed)}")
    print(f"{'='*62}\n")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
