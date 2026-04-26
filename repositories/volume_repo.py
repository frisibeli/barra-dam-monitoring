import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from models.volume import VolumeReading


class VolumeRepo:
    """Repository for MOSV dam volume bulletins."""

    def __init__(self, path: str, bulletins_dir: str | None = None, reservoir_name: str = "ogosta"):
        self.path = path
        self.bulletins_dir = bulletins_dir
        self.reservoir_name = reservoir_name

    @classmethod
    def for_dam(cls, dam_id: str, volumes_dir: str) -> "VolumeRepo":
        """Factory: create a repo that writes to volumes_dir/{dam_id}.json."""
        path = str(Path(volumes_dir) / f"{dam_id}.json")
        return cls(path=path, reservoir_name=dam_id)

    def load_all(self) -> list[VolumeReading]:
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            data = json.load(f)
        return [VolumeReading(**{k: v for k, v in r.items() if k in VolumeReading.__dataclass_fields__})
                for r in data.get("readings", [])]

    def load_as_dataframe(self) -> pd.DataFrame:
        with open(self.path) as f:
            data = json.load(f)
        df = pd.DataFrame(data["readings"])
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").set_index("date")

    def save_all(self, readings: list[VolumeReading], metadata: dict | None = None) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        payload = {
            "reservoir": self.reservoir_name,
            "source": "mosv_bulletin",
            **(metadata or {}),
            "generated": datetime.now(timezone.utc).isoformat(),
            "readings": sorted([asdict(r) for r in readings], key=lambda r: r["date"]),
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def checkpoint_reading(self, reading: VolumeReading) -> None:
        """Upsert a single reading by date and persist immediately."""
        existing = {r.date: r for r in self.load_all()}
        existing[reading.date] = reading
        self.save_all(list(existing.values()))
