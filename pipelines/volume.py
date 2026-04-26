import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from models.volume import VolumeReading
from repositories.volume_repo import VolumeRepo
from services.mosv_scraper import MosvScraperService, _HEADERS
from services.mosv_parser import MosvParserService


class VolumePipeline:
    """Scrapes МОСВ daily bulletins and stores Ogosta volume readings."""

    def __init__(self, cfg):
        self._cfg = cfg
        self._repo = VolumeRepo(cfg.results_path, cfg.bulletins_dir)
        self._scraper = MosvScraperService(cfg)
        self._parser = MosvParserService()

    def run(
        self,
        start: date,
        end: date,
        delay: float | None = None,
        force: bool = False,
        download_only: bool = False,
        parse_all: bool = False,
    ) -> None:
        if delay is None:
            delay = self._cfg.default_delay

        session = requests.Session()
        session.headers.update(_HEADERS)

        total_days = (end - start).days + 1
        stats = {"downloaded": 0, "parsed": 0, "skipped": 0, "failed": 0}

        print(f"Scraping МОСВ bulletins: {start} → {end} ({total_days} days)")
        print(f"Delay: {delay}s | Force: {force} | Download-only: {download_only} | Parse-all: {parse_all}")
        print("-" * 60)

        # Per-dam repos cache (only used when parse_all=True)
        _dam_repos: dict[str, VolumeRepo] = {}

        def _get_dam_repo(dam_id: str) -> VolumeRepo:
            if dam_id not in _dam_repos:
                _dam_repos[dam_id] = VolumeRepo.for_dam(dam_id, self._cfg.volumes_dir)
            return _dam_repos[dam_id]

        current = start
        while current <= end:
            day_num = (current - start).days + 1
            print(f"[{day_num}/{total_days}] {current}", end="")

            result = self._scraper.download_bulletin(current, session, force=force)

            if result is None:
                print("  Skipped (no bulletin)")
                stats["skipped"] += 1
                current += timedelta(days=1)
                time.sleep(delay)
                continue

            path, ext = result
            stats["downloaded"] += 1

            if not download_only:
                if parse_all:
                    all_data = self._parser.extract_all_volumes(path)
                    if all_data:
                        for dam_id, volume_data in all_data.items():
                            reading = VolumeReading(
                                date=current.isoformat(),
                                bulletin_ext=ext,
                                fetched_at=datetime.now(timezone.utc).isoformat(),
                                inflow_m3s=volume_data.get("inflow_m3s", 0.0),
                                outflow_m3s=volume_data.get("outflow_m3s", 0.0),
                                volume_mm3=volume_data["volume_mm3"],
                                total_capacity_mm3=volume_data.get("total_capacity_mm3", 0.0),
                                pct_total=volume_data.get("pct_total", 0.0),
                                dead_volume_mm3=volume_data.get("dead_volume_mm3"),
                                useful_volume_mm3=volume_data.get("useful_volume_mm3"),
                                pct_useful=volume_data.get("pct_useful"),
                            )
                            _get_dam_repo(dam_id).checkpoint_reading(reading)
                            # Dual-write Ogosta to legacy path for backward compat
                            if dam_id == "ogosta":
                                self._repo.checkpoint_reading(reading)
                        stats["parsed"] += 1
                        ogosta = all_data.get("ogosta", {})
                        pct = ogosta.get("pct_total")
                        extra = f" (Огоста {pct}%)" if pct else ""
                        print(f"  → {len(all_data)} dams{extra}")
                    else:
                        stats["failed"] += 1
                        print("  → No dam data parsed")
                else:
                    volume_data = self._parser.extract_volume(path)
                    if volume_data:
                        reading = VolumeReading(
                            date=current.isoformat(),
                            bulletin_ext=ext,
                            fetched_at=datetime.now(timezone.utc).isoformat(),
                            inflow_m3s=volume_data.get("inflow_m3s", 0.0),
                            outflow_m3s=volume_data.get("outflow_m3s", 0.0),
                            volume_mm3=volume_data["volume_mm3"],
                            total_capacity_mm3=volume_data.get("total_capacity_mm3", 0.0),
                            pct_total=volume_data.get("pct_total", 0.0),
                            dead_volume_mm3=volume_data.get("dead_volume_mm3"),
                            useful_volume_mm3=volume_data.get("useful_volume_mm3"),
                            pct_useful=volume_data.get("pct_useful"),
                        )
                        self._repo.checkpoint_reading(reading)
                        stats["parsed"] += 1
                        pct = volume_data.get("pct_total")
                        extra = f" ({pct}%)" if pct else ""
                        print(f"  → Ogosta: {volume_data['volume_mm3']} млн.м³{extra}")
                    else:
                        stats["failed"] += 1
                        print("  → Ogosta data not parsed")

            current += timedelta(days=1)
            time.sleep(delay)

        print("-" * 60)
        print(f"Stats: {stats}")
        if not download_only:
            total = len(self._repo.load_all())
            print(f"Total Ogosta readings: {total}")
