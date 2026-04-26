"""
Backward-compatible entry point. Use scripts/run_snow.py going forward.
"""
import argparse

from config import get_config
from pipelines.snow import SnowPipeline


def run_pipeline(visualize: bool = True, force: bool = False):
    SnowPipeline(get_config()).run(visualize=visualize, force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ogosta catchment snow cover pipeline")
    parser.add_argument("--no-viz", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_pipeline(visualize=not args.no_viz, force=args.force)
