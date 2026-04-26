#!/usr/bin/env python3
"""Entry point for the inflow prediction pipeline.

Usage:
    python scripts/run_prediction.py              # train & cross-validate
    python scripts/run_prediction.py --forecast   # fetch 7-day forecast & predict
    python scripts/run_prediction.py --forecast --plot  # also generate a plot
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config
from pipelines.prediction import PredictionPipeline


def main():
    parser = argparse.ArgumentParser(description="Baseline dam-inflow predictor")
    parser.add_argument("--forecast", action="store_true", help="Fetch 7-day forecast & predict inflow")
    parser.add_argument("--plot", action="store_true", help="Generate forecast visualization")
    args = parser.parse_args()

    cfg = get_config()
    pipeline = PredictionPipeline(cfg)

    if args.forecast:
        pipeline.run_forecast(days=7, plot=args.plot)
    else:
        pipeline.run_training()


if __name__ == "__main__":
    main()
