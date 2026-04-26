#!/usr/bin/env python3
"""Scrape МОСВ daily water bulletins and extract Ogosta volume data.

Usage:
    python scripts/fetch_volume.py
    python scripts/fetch_volume.py --start 2024-06-01 --end 2024-06-30
    python scripts/fetch_volume.py --download-only
    python scripts/fetch_volume.py --force
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config
from pipelines.volume import VolumePipeline


def main():
    cfg = get_config()
    mosv = cfg.mosv

    parser = argparse.ArgumentParser(
        description="Scrape МОСВ daily water bulletins for Ogosta reservoir data.",
    )
    parser.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        default=date.fromisoformat(mosv.default_start),
        help=f"Start date YYYY-MM-DD (default: {mosv.default_start})",
    )
    parser.add_argument(
        "--end",
        type=lambda s: date.fromisoformat(s),
        default=date.today(),
        help="End date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=mosv.default_delay,
        help=f"Seconds between requests (default: {mosv.default_delay})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if already cached on disk",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download bulletin files without parsing them",
    )
    parser.add_argument(
        "--parse-all",
        action="store_true",
        help="Parse all dams from each bulletin (writes to data/volumes/{dam}.json)",
    )
    args = parser.parse_args()

    VolumePipeline(mosv).run(
        start=args.start,
        end=args.end,
        delay=args.delay,
        force=args.force,
        download_only=args.download_only,
        parse_all=args.parse_all,
    )


if __name__ == "__main__":
    main()
