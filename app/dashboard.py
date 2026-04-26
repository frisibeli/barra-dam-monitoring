"""
app/dashboard.py — Ogosta Reservoir Digital Twin dashboard.

Run with:
  cd dam-monitor
  streamlit run app/dashboard.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(
    page_title="Ogosta Dam — Digital Twin",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── data loaders (cached) ─────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_water_readings():
    from repositories.water_repo import WaterReadingRepo
    from config import _build_config
    cfg = _build_config()
    return WaterReadingRepo(cfg.reservoir.results_path).load_all()


@st.cache_data(ttl=300)
def load_volume_readings():
    from repositories.volume_repo import VolumeRepo
    from config import _build_config
    cfg = _build_config()
    mosv_cfg = cfg.mosv
    return VolumeRepo(mosv_cfg.results_path).load_all()


@st.cache_data(ttl=600)
def load_forecast():
    """Load latest precomputed forecast (if present) to avoid live re-training."""
    forecast_dir = ROOT / "data"
    # Find most recent forecast_result_*.txt
    files = sorted(forecast_dir.glob("forecast_result_*.txt"))
    if not files:
        return None, None
    latest = files[-1]
    try:
        lines = latest.read_text().splitlines()
        dates, values = [], []
        for line in lines:
            parts = line.split()
            if len(parts) == 2:
                try:
                    from datetime import date
                    date.fromisoformat(parts[0])
                    dates.append(parts[0])
                    values.append(float(parts[1]))
                except ValueError:
                    pass
        return dates, values
    except Exception:
        return None, None


@st.cache_data(ttl=300)
def compute_anomalies(readings_json: str):
    """Accepts JSON-serialised readings to enable Streamlit caching."""
    import json
    from services.anomaly import flag_anomalies
    from models.reading import WaterReading
    readings = [WaterReading(**r) for r in json.loads(readings_json)]
    return flag_anomalies(readings)


# ── helpers ───────────────────────────────────────────────────────────────

def _status_badge(value: float, mean: float, stdev: float) -> str:
    if stdev < 1e-6:
        return "🟢 Normal"
    dev = abs(value - mean) / stdev
    if dev < 1:
        return "🟢 Normal"
    elif dev < 2:
        return "🟡 Elevated"
    else:
        return "🔴 Anomaly"


def _area_chart_data(water_readings, volume_readings, anomaly_flags):
    import pandas as pd

    w_df = pd.DataFrame([
        {"date": r.date, "area_km2": r.water_area_km2, "elevation_m": r.elevation_m}
        for r in water_readings
    ])
    w_df["date"] = pd.to_datetime(w_df["date"])
    w_df = w_df.sort_values("date")

    v_df = pd.DataFrame([
        {"date": str(r.date)[:10], "pct_total": r.pct_total, "volume_mm3": r.volume_mm3}
        for r in volume_readings
    ])
    v_df["date"] = pd.to_datetime(v_df["date"])
    v_df = v_df.sort_values("date")

    anomaly_dates = {f.date for f in anomaly_flags}

    return w_df, v_df, anomaly_dates


# ── panel helpers ─────────────────────────────────────────────────────────

def panel_current_state(water_readings, volume_readings):
    st.subheader("Current State")

    if not water_readings:
        st.warning("No water readings available.")
        return

    latest_w = sorted(water_readings, key=lambda r: r.date)[-1]
    latest_v = sorted(volume_readings, key=lambda r: str(r.date)[:10])[-1] if volume_readings else None

    import statistics
    areas = [r.water_area_km2 for r in water_readings]
    mean_area = statistics.mean(areas) if areas else 0
    stdev_area = statistics.stdev(areas) if len(areas) > 1 else 0
    badge = _status_badge(latest_w.water_area_km2, mean_area, stdev_area)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Water Area", f"{latest_w.water_area_km2:.2f} km²",
                delta=f"{latest_w.water_area_km2 - mean_area:+.2f} vs mean")
    col2.metric("Surface Elevation",
                f"{latest_w.elevation_m:.1f} m" if latest_w.elevation_m else "—")
    if latest_v:
        col3.metric("Volume", f"{latest_v.volume_mm3:.1f} Mm³",
                    delta=f"{latest_v.pct_total:.1f}% of capacity")
        col4.metric("Inflow", f"{latest_v.inflow_m3s:.1f} m³/s")
    else:
        col3.metric("Volume", "—")
        col4.metric("Inflow", "—")

    st.markdown(f"**Status:** {badge}  ·  Last record: `{latest_w.date}`")

    # Folium map
    try:
        import folium
        from streamlit_folium import st_folium
        from config import _build_config

        cfg = _build_config()
        coords = cfg.reservoir.polygon_coords
        center_lat = sum(c[1] for c in coords) / len(coords)
        center_lon = sum(c[0] for c in coords) / len(coords)

        m = folium.Map(location=[center_lat, center_lon], zoom_start=12,
                       tiles="CartoDB dark_matter")
        folium.Polygon(
            locations=[(c[1], c[0]) for c in coords],
            color="#4fc3f7",
            fill=True,
            fill_color="#4fc3f7",
            fill_opacity=0.25,
            weight=2,
            tooltip="Ogosta Reservoir",
        ).add_to(m)
        st_folium(m, width=900, height=400)
    except ImportError:
        st.info("Install folium + streamlit-folium for the map overlay.")


def panel_timeseries(water_readings, volume_readings):
    st.subheader("Historical Timeseries")
    if not water_readings:
        st.warning("No water readings available.")
        return

    import plotly.graph_objects as go
    import json
    from dataclasses import asdict

    readings_json = json.dumps([asdict(r) for r in water_readings])
    anomaly_flags = compute_anomalies(readings_json)

    w_df, v_df, anomaly_dates = _area_chart_data(water_readings, volume_readings, anomaly_flags)

    fig = go.Figure()

    # Water area trace
    fig.add_trace(go.Scatter(
        x=w_df["date"], y=w_df["area_km2"],
        name="Water Area (km²)",
        line=dict(color="#4fc3f7", width=2),
        mode="lines+markers",
        marker=dict(size=4),
    ))

    # Rolling mean
    import statistics
    rolling_mean = statistics.mean(w_df["area_km2"].tolist())
    fig.add_hline(
        y=rolling_mean,
        line_dash="dash",
        line_color="rgba(255,255,255,0.4)",
        annotation_text=f"Mean {rolling_mean:.2f} km²",
    )

    # Anomaly dots
    anom_w = w_df[w_df["date"].dt.strftime("%Y-%m-%d").isin(anomaly_dates)]
    if not anom_w.empty:
        fig.add_trace(go.Scatter(
            x=anom_w["date"], y=anom_w["area_km2"],
            name="Anomaly",
            mode="markers",
            marker=dict(color="#ff5252", size=10, symbol="x"),
        ))

    # Elevation on secondary axis
    elev_df = w_df.dropna(subset=["elevation_m"])
    if not elev_df.empty:
        fig.add_trace(go.Scatter(
            x=elev_df["date"], y=elev_df["elevation_m"],
            name="Surface Elevation (m)",
            line=dict(color="#ffcc02", width=2, dash="dot"),
            yaxis="y2",
        ))

    # Volume % on secondary axis
    if not v_df.empty:
        fig.add_trace(go.Scatter(
            x=v_df["date"], y=v_df["pct_total"],
            name="Volume % capacity",
            line=dict(color="#69db7c", width=1.5),
            yaxis="y2",
            opacity=0.7,
        ))

    fig.update_layout(
        template="plotly_dark",
        height=450,
        yaxis=dict(title="Water Area (km²)"),
        yaxis2=dict(title="Elevation (m) / Volume %", overlaying="y", side="right"),
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=60, r=60, t=30, b=80),
    )

    st.plotly_chart(fig, use_container_width=True)

    if anomaly_flags:
        with st.expander(f"⚠️ {len(anomaly_flags)} anomalies detected"):
            import pandas as pd
            from dataclasses import asdict
            st.dataframe(pd.DataFrame([asdict(f) for f in anomaly_flags]))


def panel_3d_forecast(water_readings):
    st.subheader("3D View & Inflow Forecast")

    col_left, col_right = st.columns([1, 1])

    # ── Left: animation / static ──────────────────────────────────────────
    with col_left:
        anim_path = ROOT / "data" / "plots" / "animation.gif"
        static_path = ROOT / "data" / "plots" / "render_3d.png"

        if anim_path.exists():
            st.image(str(anim_path), caption="Water elevation animation", use_container_width=True)
        elif static_path.exists():
            st.image(str(static_path), caption="3D render", use_container_width=True)
        else:
            st.info("No 3D render available.\n\n"
                    "Run `python scripts/fetch_dem.py` then `python scripts/render_3d.py --animate`")

        # Date scrub slider
        with_elev = sorted(
            [r for r in water_readings if r.elevation_m is not None],
            key=lambda r: r.date,
        )
        if with_elev:
            dates = [r.date for r in with_elev]
            selected = st.select_slider("Scrub date", options=dates, value=dates[-1])
            selected_r = next(r for r in with_elev if r.date == selected)
            st.metric("Elevation at selected date", f"{selected_r.elevation_m:.1f} m")
            st.metric("Water area at selected date", f"{selected_r.water_area_km2:.2f} km²")

    # ── Right: what-if inflow forecast ───────────────────────────────────
    with col_right:
        st.markdown("**7-day Inflow Forecast**")

        fc_dates, fc_values = load_forecast()
        if fc_dates and fc_values:
            import plotly.graph_objects as go

            fig = go.Figure(go.Bar(
                x=fc_dates,
                y=fc_values,
                marker_color="#4fc3f7",
                name="Forecast inflow",
            ))
            fig.update_layout(
                template="plotly_dark",
                height=300,
                yaxis_title="Inflow (m³/s)",
                margin=dict(l=40, r=20, t=20, b=40),
            )
            st.plotly_chart(fig, use_container_width=True)

            peak_idx = fc_values.index(max(fc_values))
            st.info(f"Peak inflow: **{max(fc_values):.1f} m³/s** on {fc_dates[peak_idx]}")
        else:
            st.info("No precomputed forecast found.\n\n"
                    "Run `python baseline_predictor.py --forecast`")


# ── main ─────────────────────────────────────────────────────────────────

def main():
    st.title("💧 Ogosta Reservoir — Digital Twin")
    st.caption("Satellite-derived water extent · Elevation · Volume · Inflow forecast")

    water_readings = load_water_readings()
    volume_readings = load_volume_readings()

    tab1, tab2, tab3 = st.tabs(["Current State", "Historical Timeseries", "3D & Forecast"])

    with tab1:
        panel_current_state(water_readings, volume_readings)

    with tab2:
        panel_timeseries(water_readings, volume_readings)

    with tab3:
        panel_3d_forecast(water_readings)


if __name__ == "__main__":
    main()
