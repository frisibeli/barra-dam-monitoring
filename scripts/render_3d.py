"""
scripts/render_3d.py — CLI for 3D DEM + water renders.

Usage
-----
  # Static render at most recent elevation
  python scripts/render_3d.py --static

  # Static render for a specific date
  python scripts/render_3d.py --static --date 2025-08-01

  # Animated GIF across all dates with elevation data
  python scripts/render_3d.py --animate --output data/plots/animation.gif
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import _build_config
from repositories.water_repo import WaterReadingRepo
from visualization.threed import render_static, generate_animation


def main():
    parser = argparse.ArgumentParser(description="3D reservoir render")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--static", action="store_true", help="Render a single static frame")
    mode.add_argument("--animate", action="store_true", help="Generate animated GIF")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD) for --static (default: latest)")
    parser.add_argument("--output", default=None, help="Output file path")
    parser.add_argument("--fps", type=int, default=4, help="Frames per second for animation")
    args = parser.parse_args()

    cfg = _build_config()
    dem_path = Path(cfg.raw_cache_dir).parent / "dem" / "dem.tif"

    if not dem_path.exists():
        print(f"ERROR: DEM not found at {dem_path}")
        print("Run:  python scripts/fetch_dem.py")
        sys.exit(1)

    repo = WaterReadingRepo(cfg.reservoir.results_path)
    readings = repo.load_all()

    if not readings:
        print("ERROR: No water readings found.")
        sys.exit(1)

    if args.static:
        out = args.output or "data/plots/render_3d.png"
        Path(out).parent.mkdir(parents=True, exist_ok=True)

        if args.date:
            matches = [r for r in readings if r.date == args.date]
            if not matches:
                print(f"ERROR: No reading for date {args.date}")
                sys.exit(1)
            reading = matches[0]
        else:
            # Most recent reading with elevation_m
            with_elev = [r for r in sorted(readings, key=lambda r: r.date) if r.elevation_m is not None]
            reading = with_elev[-1] if with_elev else sorted(readings, key=lambda r: r.date)[-1]

        print(f"Rendering {reading.date}  elevation_m={reading.elevation_m}")
        render_static(
            str(dem_path), cfg.reservoir,
            elevation_m=reading.elevation_m,
            out_path=out,
            title=reading.date,
        )

    else:  # --animate
        out = args.output or "data/plots/animation.gif"
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        print(f"Generating animation with {sum(1 for r in readings if r.elevation_m is not None)} frames")
        generate_animation(str(dem_path), cfg.reservoir, readings, out, fps=args.fps)


if __name__ == "__main__":
    main()
