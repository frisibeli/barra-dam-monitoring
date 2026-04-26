"""
Backward-compatible entry point. Use scripts/run_prediction.py going forward.
"""
import argparse

from config import get_config
from pipelines.prediction import PredictionPipeline


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baseline dam-inflow predictor.")
    parser.add_argument("--forecast", action="store_true")
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args()

    pipeline = PredictionPipeline(get_config())
    if args.forecast:
        pipeline.run_forecast(days=7, plot=args.plot)
    else:
        pipeline.run_training()
