import json
import os
from dataclasses import asdict
from typing import Generic, TypeVar

T = TypeVar("T")


class BaseReadingRepo(Generic[T]):
    """Generic JSON-backed repository for time-windowed satellite readings."""

    def __init__(self, path: str, reading_cls: type):
        self.path = path
        self._cls = reading_cls

    def load_all(self) -> list:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path) as f:
                data = json.load(f)
            return [self._cls(**r) for r in data.get("readings", [])]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

    def load_as_cache(self) -> dict:
        """Returns {cache_key → reading} dict for O(1) lookup."""
        return {r.cache_key(): r for r in self.load_all()}

    def save_all(self, readings: list, metadata: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        payload = {
            **metadata,
            "readings": sorted(
                [asdict(r) for r in readings], key=lambda r: r["date"]
            ),
        }
        with open(self.path, "w") as f:
            json.dump(payload, f, indent=2)
