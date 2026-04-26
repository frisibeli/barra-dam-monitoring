"""
Backward-compatible entry point. Use scripts/run_water.py going forward.
"""
import argparse

from config import get_config
from pipelines.water import WaterPipeline


def run_pipeline(visualize: bool = True, force: bool = False):
    WaterPipeline(get_config()).run(visualize=visualize, force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dam water monitoring pipeline")
    parser.add_argument("--no-viz", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_pipeline(visualize=not args.no_viz, force=args.force)
