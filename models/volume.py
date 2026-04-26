from dataclasses import dataclass


@dataclass
class VolumeReading:
    date: str
    inflow_m3s: float
    outflow_m3s: float
    volume_mm3: float
    total_capacity_mm3: float
    pct_total: float
    dead_volume_mm3: float | None = None
    useful_volume_mm3: float | None = None
    pct_useful: float | None = None
    bulletin_ext: str | None = None
    fetched_at: str | None = None
