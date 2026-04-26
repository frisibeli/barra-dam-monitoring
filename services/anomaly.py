"""Anomaly detection for water area timeseries.

Uses a rolling 30-day window to detect unusually high or low water extent.
"""
from dataclasses import dataclass
from typing import Literal


@dataclass
class AnomalyFlag:
    date: str
    water_area_km2: float
    rolling_mean_km2: float
    sigma: float
    deviation_sigma: float
    direction: Literal["high", "low"]


def flag_anomalies(
    readings,
    window_days: int = 30,
    sigma_threshold: float = 2.0,
) -> list[AnomalyFlag]:
    """
    Flag water readings where area deviates more than *sigma_threshold* σ
    from the rolling *window_days*-day mean.

    Parameters
    ----------
    readings : list[WaterReading]
        Sorted (or unsorted) list of WaterReading objects.
    window_days : int
        Size of the rolling window (calendar days, not number of observations).
    sigma_threshold : float
        Number of standard deviations beyond which a point is flagged.

    Returns
    -------
    list[AnomalyFlag]
        One entry per anomalous reading, sorted by date.
    """
    from datetime import datetime

    if not readings:
        return []

    # Sort by date ascending
    sorted_readings = sorted(readings, key=lambda r: r.date)

    flags: list[AnomalyFlag] = []

    for i, reading in enumerate(sorted_readings):
        t_end = datetime.fromisoformat(reading.date)

        # Collect window: readings within [t_end - window_days, t_end)
        window_vals = []
        for past in sorted_readings[:i]:
            t_past = datetime.fromisoformat(past.date)
            if (t_end - t_past).days <= window_days:
                window_vals.append(past.water_area_km2)

        if len(window_vals) < 3:
            # Not enough history to compute a stable mean
            continue

        import statistics
        mean = statistics.mean(window_vals)
        stdev = statistics.stdev(window_vals)

        if stdev < 1e-6:
            continue

        deviation = abs(reading.water_area_km2 - mean) / stdev
        if deviation >= sigma_threshold:
            flags.append(
                AnomalyFlag(
                    date=reading.date,
                    water_area_km2=reading.water_area_km2,
                    rolling_mean_km2=round(mean, 4),
                    sigma=round(stdev, 4),
                    deviation_sigma=round(deviation, 2),
                    direction="high" if reading.water_area_km2 > mean else "low",
                )
            )

    return flags
