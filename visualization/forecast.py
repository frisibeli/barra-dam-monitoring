import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

_VOLUME_COLORS = [
    (30, "#d32f2f", "Critical (<30%)"),
    (50, "#f57c00", "Low (30–50%)"),
    (65, "#fbc02d", "Moderate (50–65%)"),
    (100, "#388e3c", "Good (>65%)"),
]


def _volume_color(pct: float) -> tuple:
    for threshold, color, label in _VOLUME_COLORS:
        if pct < threshold:
            return color, label
    return _VOLUME_COLORS[-1][1], _VOLUME_COLORS[-1][2]


class ForecastVisualizer:
    """Creates the combined historical + 7-day inflow forecast chart."""

    def __init__(self, volume_repo):
        self._vol = volume_repo

    def plot_forecast(self, forecast_results, lookback_days: int = 60, out_path: str | None = None) -> str:
        vol_df = self._vol.load_as_dataframe()
        latest = vol_df.iloc[-1]
        pct = float(latest["pct_total"])
        vol_color, vol_label = _volume_color(pct)

        cutoff = vol_df.index.max() - pd.Timedelta(days=lookback_days)
        hist = vol_df.loc[cutoff:]

        fc_dates = pd.to_datetime([r.date if hasattr(r, "date") else r["date"] for r in forecast_results])
        fc_values = [r.predicted_inflow_m3s if hasattr(r, "predicted_inflow_m3s") else r["predicted_inflow_m3s"]
                     for r in forecast_results]

        bridge_dates = [hist.index[-1], fc_dates[0]]
        bridge_inflow = [float(hist["inflow_m3s"].dropna().iloc[-1]), fc_values[0]]

        fig = plt.figure(figsize=(14, 7), dpi=150)
        gs = fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.25)
        ax_main = fig.add_subplot(gs[0])
        ax_vol = fig.add_subplot(gs[1])

        ax_main.axvspan(fc_dates[0], fc_dates[-1], color=vol_color, alpha=0.08, zorder=0)
        ax_main.axvline(fc_dates[0], color="#888", ls="--", lw=0.8, alpha=0.6)
        ax_main.plot(hist.index, hist["inflow_m3s"], "o-",
                     color="#1565c0", ms=3, lw=1.4, label="Inflow (observed)", zorder=3)
        ax_main.plot(hist.index, hist["outflow_m3s"], "s-",
                     color="#6a1b9a", ms=2.5, lw=1.2, alpha=0.7, label="Outflow (observed)", zorder=3)
        ax_main.plot(bridge_dates, bridge_inflow, "--", color="#1565c0", lw=1, alpha=0.4, zorder=2)
        ax_main.plot(fc_dates, fc_values, "D--",
                     color="#e65100", ms=5, lw=2, label="Inflow (forecast)", zorder=4)
        ax_main.fill_between(fc_dates, fc_values, alpha=0.12, color="#e65100", zorder=1)
        ax_main.set_ylabel("Flow (m³/s)", fontsize=11)
        ax_main.legend(loc="upper left", fontsize=9, framealpha=0.9)
        ax_main.grid(True, alpha=0.3)
        ax_main.set_title("Ogosta Dam — Inflow Forecast (7 days)", fontsize=13, fontweight="bold")
        ax_main.annotate(
            f"Last observed: {latest.name.strftime('%Y-%m-%d')}\n"
            f"  Inflow {latest['inflow_m3s']:.1f} m³/s\n"
            f"  Outflow {latest['outflow_m3s']:.1f} m³/s",
            xy=(0.98, 0.97), xycoords="axes fraction",
            ha="right", va="top", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#ccc", alpha=0.9),
        )

        ax_vol.barh(0, pct, height=0.6, color=vol_color, alpha=0.85, zorder=2)
        ax_vol.barh(0, 100, height=0.6, color="#e0e0e0", alpha=0.4, zorder=1)
        ax_vol.set_xlim(0, 100)
        ax_vol.set_yticks([])
        ax_vol.set_xlabel("Volume (% of total capacity)", fontsize=10)
        for x_line, x_color in [(30, "#d32f2f"), (50, "#f57c00"), (65, "#fbc02d")]:
            ax_vol.axvline(x_line, color=x_color, ls=":", lw=0.8, alpha=0.5)
        ax_vol.text(pct - 1, 0, f"{pct:.1f}%", va="center", ha="right",
                    fontsize=10, fontweight="bold", color="white", zorder=3)
        ax_vol.text(50, -0.55,
                    f"{vol_label}  ·  {latest['volume_mm3']:.0f} / {latest['total_capacity_mm3']:.0f} Mm³",
                    ha="center", va="top", fontsize=9, color="#555")

        ax_main.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        ax_main.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        plt.setp(ax_main.get_xticklabels(), rotation=30, ha="right", fontsize=8)
        ax_vol.tick_params(axis="x", labelbottom=False)

        from pathlib import Path
        out = out_path or str(Path(__file__).resolve().parent.parent / "data" / "forecast_plot.png")
        fig.savefig(out, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"\nPlot saved to {out}")
        return out
