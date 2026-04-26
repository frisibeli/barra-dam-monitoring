import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from dotenv import load_dotenv
from sentinelhub import SHConfig, BBox, CRS, DataCollection, Geometry

load_dotenv()

# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MosvConfig:
    results_path: str
    bulletins_dir: str
    volumes_dir: str
    base_url: str
    default_start: str
    default_delay: float
    request_timeout: int
    download_timeout: int


@dataclass
class InSARConfig:
    job_name: str
    aoi_wkt: str
    relative_orbit: int
    flight_direction: str
    polarization: str
    start_date: str
    end_date: str
    pairing_strategy: str
    min_temporal_baseline_days: int
    max_temporal_baseline_days: int
    max_pairs_per_scene: int
    hyp3_looks: str
    hyp3_include_displacement: bool
    hyp3_include_dem: bool
    hyp3_apply_water_mask: bool
    hyp3_batch_size: int
    hyp3_poll_interval_s: int
    hyp3_timeout_hours: int
    output_dir: str
    coherence_threshold: float
    displacement_threshold_mm: float
    geojson_sample_step: int
    gacos_enabled: bool
    gacos_dir: str
    gacos_ref_point: tuple[float, float] | None
    incidence_angle_deg: float
    reference_normalization: str
    warn_on_atmospheric_noise: bool
    alert_rate_threshold_mm: float
    alert_webhook_url: str | None
    skip_cached_downloads: bool
    skip_cached_submissions: bool
    cache_db: str
    earthdata_user: str | None
    earthdata_password: str | None


@dataclass
class AppConfig:
    sh_client_id: str
    sh_client_secret: str
    reservoir: object    # models.reservoir.ReservoirConfig
    catchment: object    # models.reservoir.CatchmentConfig
    weather_geo_points: dict
    data_collection: object  # sentinelhub.DataCollection
    mosv: MosvConfig
    insar: InSARConfig
    raw_cache_dir: str = ""

    @cached_property
    def sh_config(self) -> SHConfig:
        cfg = SHConfig()
        cfg.sh_client_id = self.sh_client_id
        cfg.sh_client_secret = self.sh_client_secret
        cfg.sh_base_url = "https://sh.dataspace.copernicus.eu"
        cfg.sh_token_url = (
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
            "/protocol/openid-connect/token"
        )
        return cfg


def _build_config() -> AppConfig:
    # ── Dam polygon ────────────────────────────────────────────────────────
    dam_polygon_coords = [
        [23.191542, 43.347228], [23.189011, 43.348675], [23.189029, 43.35061],
        [23.186099, 43.351064], [23.179011, 43.349789], [23.176346, 43.351393],
        [23.174925, 43.356541], [23.167036, 43.354202], [23.163764, 43.355037],
        [23.164423, 43.357823], [23.173012, 43.368294], [23.171739, 43.3696],
        [23.174735, 43.370545], [23.1754, 43.372253], [23.177178, 43.373451],
        [23.176709, 43.375107], [23.176204, 43.376965], [23.173109, 43.375841],
        [23.173546, 43.377957], [23.166758, 43.380414], [23.16135, 43.378132],
        [23.159862, 43.378741], [23.164204, 43.381828], [23.158477, 43.379807],
        [23.152425, 43.380995], [23.147544, 43.383102], [23.14575, 43.382387],
        [23.145004, 43.38362], [23.142316, 43.383496], [23.132891, 43.379846],
        [23.131601, 43.380668], [23.13471, 43.382808], [23.140958, 43.384047],
        [23.139379, 43.385044], [23.127815, 43.385474], [23.125523, 43.386845],
        [23.121336, 43.385634], [23.119081, 43.386062], [23.116692, 43.389275],
        [23.114925, 43.389343], [23.11301, 43.387994], [23.111677, 43.389198],
        [23.112234, 43.394242], [23.1168, 43.392622], [23.122294, 43.394804],
        [23.127801, 43.394392], [23.129357, 43.393113], [23.153538, 43.388662],
        [23.155276, 43.390248], [23.156652, 43.388329], [23.159751, 43.38866],
        [23.160096, 43.39041], [23.158301, 43.39221], [23.157636, 43.394148],
        [23.15958, 43.395455], [23.160952, 43.393237], [23.163598, 43.392525],
        [23.164802, 43.3939], [23.169258, 43.393754], [23.170139, 43.39481],
        [23.172683, 43.39392], [23.176884, 43.393878], [23.176882, 43.391765],
        [23.183834, 43.395183], [23.209455, 43.401619], [23.211813, 43.401469],
        [23.214589, 43.392928], [23.214054, 43.388854], [23.215464, 43.388309],
        [23.215118, 43.386776], [23.21052, 43.381597], [23.211471, 43.380202],
        [23.210426, 43.379256], [23.210458, 43.37738], [23.207423, 43.373911],
        [23.206119, 43.374511], [23.207562, 43.377006], [23.199641, 43.375615],
        [23.200689, 43.374233], [23.200993, 43.369271], [23.19995, 43.366992],
        [23.200884, 43.364444], [23.200661, 43.361596], [23.202013, 43.36005],
        [23.199935, 43.358742], [23.198767, 43.356343], [23.199013, 43.35427],
        [23.197283, 43.351703], [23.197616, 43.349995], [23.195999, 43.349088],
        [23.193511, 43.349242], [23.191542, 43.347228],
    ]
    _dam_lons = [c[0] for c in dam_polygon_coords]
    _dam_lats = [c[1] for c in dam_polygon_coords]
    dam_bbox = BBox(
        bbox=[min(_dam_lons), min(_dam_lats), max(_dam_lons), max(_dam_lats)],
        crs=CRS.WGS84,
    )
    dam_geometry = Geometry(
        geometry={"type": "Polygon", "coordinates": [dam_polygon_coords]},
        crs=CRS.WGS84,
    )

    # ── Catchment polygon ──────────────────────────────────────────────────
    catchment_polygon_coords = [
        [23.19419, 43.112361], [23.119766, 43.119098], [23.020869, 43.198462],
        [23.004828, 43.190451], [22.98283, 43.202277], [22.942947, 43.203505],
        [22.894912, 43.22594], [22.867523, 43.268177], [22.847505, 43.275655],
        [22.824589, 43.330639], [22.799743, 43.340519], [22.746301, 43.38577],
        [22.837114, 43.516089], [23.006725, 43.480774], [23.094757, 43.431634],
        [23.220973, 43.403937], [23.208649, 43.358924], [23.233357, 43.242254],
        [23.19419, 43.112361],
    ]
    _lons = [c[0] for c in catchment_polygon_coords]
    _lats = [c[1] for c in catchment_polygon_coords]
    catchment_bbox = BBox(
        bbox=[min(_lons), min(_lats), max(_lons), max(_lats)],
        crs=CRS.WGS84,
    )
    catchment_geometry = Geometry(
        geometry={"type": "Polygon", "coordinates": [catchment_polygon_coords]},
        crs=CRS.WGS84,
    )

    data_collection = DataCollection.SENTINEL2_L2A.define_from(
        "SENTINEL2_L2A_CDSE",
        service_url="https://sh.dataspace.copernicus.eu",
    )

    from models.reservoir import ReservoirConfig, CatchmentConfig

    reservoir = ReservoirConfig(
        name="ogosta",
        bbox=dam_bbox,
        geometry=dam_geometry,
        polygon_coords=dam_polygon_coords,
        image_size=(512, 512),
        max_cloud_cover=50,
        water_threshold=0.2,
        time_start="2023-01-01",
        time_end="2026-04-19",
        time_delta=6,
        results_path="data/results.json",
        plots_dir="data/plots",
        manifest_path="data/viewer_manifest.json",
    )

    catchment = CatchmentConfig(
        name="ogosta_upstream",
        bbox=catchment_bbox,
        geometry=catchment_geometry,
        polygon_coords=catchment_polygon_coords,
        dam_polygon_coords=dam_polygon_coords,
        image_size=(512, 512),
        snow_threshold=0.40,
        min_valid_fraction=0.60,
        max_cloud_cover=60,
        time_start="2023-01-01",
        time_end="2026-04-19",
        time_delta=7,
        results_path="data/snow/snow_results.json",
        plots_dir="data/snow/plots",
        manifest_path="data/snow/viewer_manifest.json",
    )

    _data_dir = Path(__file__).resolve().parent / "data"

    mosv = MosvConfig(
        results_path=str(_data_dir / "ogosta_volumes.json"),
        bulletins_dir=str(_data_dir / "bulletins"),
        volumes_dir=str(_data_dir / "volumes"),
        base_url="https://www.moew.government.bg",
        default_start="2023-01-01",
        default_delay=2.0,
        request_timeout=15,
        download_timeout=30,
    )

    insar_output_dir = _data_dir / "insar" / "ogosta_rel80_desc"
    insar = InSARConfig(
        job_name="ogosta_rel80_desc",
        aoi_wkt=(
            "POLYGON((23.102898 43.408826, 23.23636 43.408826, "
            "23.23636 43.343045, 23.102898 43.343045, 23.102898 43.408826))"
        ),
        relative_orbit=80,
        flight_direction="DESCENDING",
        polarization="VV+VH",
        start_date="2024-01-01",
        end_date="2026-04-17",
        pairing_strategy="sequential",
        min_temporal_baseline_days=6,
        max_temporal_baseline_days=36,
        max_pairs_per_scene=2,
        hyp3_looks="10x2",
        hyp3_include_displacement=True,
        hyp3_include_dem=True,
        hyp3_apply_water_mask=True,
        hyp3_batch_size=25,
        hyp3_poll_interval_s=60,
        hyp3_timeout_hours=8,
        output_dir=str(insar_output_dir),
        coherence_threshold=0.4,
        displacement_threshold_mm=1.0,
        geojson_sample_step=1,
        gacos_enabled=True,
        gacos_dir=str(insar_output_dir / "gacos"),
        gacos_ref_point=None,
        incidence_angle_deg=34.0,
        reference_normalization="median",
        warn_on_atmospheric_noise=True,
        alert_rate_threshold_mm=10.0,
        alert_webhook_url=None,
        skip_cached_downloads=True,
        skip_cached_submissions=True,
        cache_db=str(insar_output_dir / "cache.json"),
        earthdata_user=os.getenv("EARTHDATA_USER"),
        earthdata_password=os.getenv("EARTHDATA_PASSWORD"),
    )

    return AppConfig(
        sh_client_id=os.getenv("SH_CLIENT_ID", ""),
        sh_client_secret=os.getenv("SH_CLIENT_SECRET", ""),
        reservoir=reservoir,
        catchment=catchment,
        weather_geo_points={
            "chiprovts": (43.38471, 22.87887),
            "berkovitsa": (43.23831, 23.12950),
            "montana": (43.40719, 23.221595),
        },
        data_collection=data_collection,
        mosv=mosv,
        insar=insar,
        raw_cache_dir=str(_data_dir / "raw"),
    )


_app_config: AppConfig | None = None


def get_config() -> AppConfig:
    global _app_config
    if _app_config is None:
        _app_config = _build_config()
    return _app_config


# ---------------------------------------------------------------------------
# Backward-compatible module-level aliases
# All existing imports (from config import RESERVOIR_BBOX, etc.) continue to work.
# ---------------------------------------------------------------------------

def __getattr__(name: str):
    _aliases = {
        "config": lambda c: c.sh_config,
        "RESERVOIR_NAME": lambda c: c.reservoir.name,
        "RESERVOIR_BBOX": lambda _: BBox(
            bbox=[23.102898, 43.343045, 23.23636, 43.408826], crs=CRS.WGS84
        ),
        "DAM_BBOX": lambda c: c.reservoir.bbox,
        "DAM_GEOMETRY": lambda c: c.reservoir.geometry,
        "DAM_POLYGON_COORDS": lambda c: c.reservoir.polygon_coords,
        "CATCHMENT_POLYGON_COORDS": lambda c: c.catchment.polygon_coords,
        "CATCHMENT_GEOMETRY": lambda c: c.catchment.geometry,
        "CATCHMENT_BBOX": lambda c: c.catchment.bbox,
        "CATCHMENT_IMAGE_SIZE": lambda c: c.catchment.image_size,
        "DATA_COLLECTION": lambda c: c.data_collection,
        "IMAGE_SIZE": lambda c: c.reservoir.image_size,
        "MAX_CLOUD_COVER": lambda c: c.reservoir.max_cloud_cover,
        "WATER_THRESHOLD": lambda c: c.reservoir.water_threshold,
        "TIME_START": lambda c: c.reservoir.time_start,
        "TIME_END": lambda c: c.reservoir.time_end,
        "TIME_DELTA": lambda c: c.reservoir.time_delta,
        "RESULTS_PATH": lambda c: c.reservoir.results_path,
        "SNOW_THRESHOLD": lambda c: c.catchment.snow_threshold,
        "SNOW_MIN_VALID_FRACTION": lambda c: c.catchment.min_valid_fraction,
        "SNOW_MAX_CLOUD_COVER": lambda c: c.catchment.max_cloud_cover,
        "SNOW_TIME_START": lambda c: c.catchment.time_start,
        "SNOW_TIME_END": lambda c: c.catchment.time_end,
        "SNOW_TIME_DELTA": lambda c: c.catchment.time_delta,
        "SNOW_RESULTS_PATH": lambda c: c.catchment.results_path,
        "SNOW_PLOTS_DIR": lambda c: c.catchment.plots_dir,
        "SNOW_MANIFEST_PATH": lambda c: c.catchment.manifest_path,
        "WEATHER_GEO_POINTS": lambda c: c.weather_geo_points,
    }
    if name in _aliases:
        return _aliases[name](get_config())
    raise AttributeError(f"module 'config' has no attribute {name!r}")
