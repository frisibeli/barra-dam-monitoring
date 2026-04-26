from __future__ import annotations

import logging
import shutil
import sys
import importlib.util
import errno
from pathlib import Path
from typing import Callable


class InSARPipeline:
    """
    Dam-monitor wrapper around the existing robust InSAR pipeline logic.

    This class keeps the original step implementation from `insar_pipeline/steps/*`
    and executes it through dam-monitor config and entry points.
    """

    ORDERED_STEPS = [
        "search",
        "pair",
        "prepare",
        "submit",
        "download",
        "process",
        "timeseries",
        "export",
    ]

    def __init__(self, app_config, insar_root: Path | None = None):
        self._app_cfg = app_config
        self._cfg = app_config.insar
        self._project_root = Path(__file__).resolve().parents[2]
        self._insar_root = insar_root or (self._project_root / "insar_pipeline")
        self._log = logging.getLogger("pipelines.insar")

        if not self._insar_root.exists():
            raise FileNotFoundError(
                f"Legacy InSAR source not found at: {self._insar_root}"
            )

        self._prepare_legacy_import_path()

    def _prepare_legacy_import_path(self) -> None:
        path = str(self._insar_root)
        if path not in sys.path:
            sys.path.insert(0, path)
        self._clear_conflicting_legacy_modules()

    @staticmethod
    def _clear_conflicting_legacy_modules() -> None:
        # Legacy InSAR uses top-level names like `utils.cache` and `steps.*`.
        # Remove existing modules with the same prefixes so imports resolve
        # against insar_pipeline first.
        for module_name in list(sys.modules.keys()):
            if module_name == "utils" or module_name.startswith("utils."):
                del sys.modules[module_name]
            if module_name == "steps" or module_name.startswith("steps."):
                del sys.modules[module_name]

    def _load_legacy_module(self, module_name: str, rel_path: str):
        module_path = self._insar_root / rel_path
        if not module_path.exists():
            raise FileNotFoundError(f"Legacy module not found: {module_path}")

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for: {module_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _legacy_config(self) -> dict:
        return {
            "aoi_wkt": self._cfg.aoi_wkt,
            "relative_orbit": self._cfg.relative_orbit,
            "flight_direction": self._cfg.flight_direction,
            "polarization": self._cfg.polarization,
            "start_date": self._cfg.start_date,
            "end_date": self._cfg.end_date,
            "pairing_strategy": self._cfg.pairing_strategy,
            "min_temporal_baseline_days": self._cfg.min_temporal_baseline_days,
            "max_temporal_baseline_days": self._cfg.max_temporal_baseline_days,
            "max_pairs_per_scene": self._cfg.max_pairs_per_scene,
            "hyp3_looks": self._cfg.hyp3_looks,
            "hyp3_include_displacement": self._cfg.hyp3_include_displacement,
            "hyp3_include_dem": self._cfg.hyp3_include_dem,
            "hyp3_apply_water_mask": self._cfg.hyp3_apply_water_mask,
            "hyp3_batch_size": self._cfg.hyp3_batch_size,
            "hyp3_poll_interval_s": self._cfg.hyp3_poll_interval_s,
            "hyp3_timeout_hours": self._cfg.hyp3_timeout_hours,
            "output_dir": self._cfg.output_dir,
            "coherence_threshold": self._cfg.coherence_threshold,
            "displacement_threshold_mm": self._cfg.displacement_threshold_mm,
            "geojson_sample_step": self._cfg.geojson_sample_step,
            "gacos_enabled": self._cfg.gacos_enabled,
            "gacos_dir": self._cfg.gacos_dir,
            "gacos_ref_point": self._cfg.gacos_ref_point,
            "incidence_angle_deg": self._cfg.incidence_angle_deg,
            "reference_normalization": self._cfg.reference_normalization,
            "warn_on_atmospheric_noise": self._cfg.warn_on_atmospheric_noise,
            "alert_rate_threshold_mm": self._cfg.alert_rate_threshold_mm,
            "alert_webhook_url": self._cfg.alert_webhook_url,
            "skip_cached_downloads": self._cfg.skip_cached_downloads,
            "skip_cached_submissions": self._cfg.skip_cached_submissions,
            "cache_db": self._cfg.cache_db,
            "earthdata_user": self._cfg.earthdata_user,
            "earthdata_password": self._cfg.earthdata_password,
        }

    def _get_steps(self) -> dict[str, tuple[str, Callable]]:
        search_scenes = self._load_legacy_module(
            "insar_step1_search_scenes", "steps/step1_search_scenes.py"
        ).run
        pair_scenes = self._load_legacy_module(
            "insar_step2_pair_scenes", "steps/step2_pair_scenes.py"
        ).run
        prepare_batch = self._load_legacy_module(
            "insar_step3_prepare_batch", "steps/step3_prepare_batch.py"
        ).run
        submit_jobs = self._load_legacy_module(
            "insar_step4_submit_jobs", "steps/step4_submit_jobs.py"
        ).run
        download_results = self._load_legacy_module(
            "insar_step5_download", "steps/step5_download.py"
        ).run
        process_stack = self._load_legacy_module(
            "insar_step6_process_stack", "steps/step6_process_stack.py"
        ).run
        build_time_series = self._load_legacy_module(
            "insar_step7_time_series", "steps/step7_time_series.py"
        ).run
        export_geojson = self._load_legacy_module(
            "insar_step8_export_geojson", "steps/step8_export_geojson.py"
        ).run

        return {
            "search": ("Search and filter Sentinel-1 SLC scenes from ASF", search_scenes),
            "pair": ("Build interferometric pairs from discovered scenes", pair_scenes),
            "prepare": ("Validate pairs, check cache, display credit impact", prepare_batch),
            "submit": ("Submit InSAR jobs to HyP3 (uses credits)", submit_jobs),
            "download": (
                "Download and rename completed HyP3 job outputs",
                download_results,
            ),
            "process": ("Apply coherence mask, reference, LOS to vertical", process_stack),
            "timeseries": ("Build cumulative displacement time series", build_time_series),
            "export": ("Export GeoJSON epochs for web visualization", export_geojson),
            "all": ("Run every step end-to-end", None),
        }

    def _ensure_output_dirs(self) -> None:
        output_dir = Path(self._cfg.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "downloads").mkdir(exist_ok=True)
        (output_dir / "processed").mkdir(exist_ok=True)
        (output_dir / "geojson").mkdir(exist_ok=True)
        (output_dir / "gacos").mkdir(exist_ok=True)

    def discover_orbits(self) -> None:
        discover_and_print = self._load_legacy_module(
            "insar_utils_orbit_discover", "utils/orbit_discover.py"
        ).discover_and_print

        discover_and_print(self._legacy_config())

    @staticmethod
    def _safe_remove_path(path: Path) -> None:
        if path.is_symlink() or path.is_file():
            path.unlink()
            return
        if path.exists():
            shutil.rmtree(path)

    def _copy_or_symlink(self, source: Path, target: Path, overwrite: bool) -> str:
        if overwrite and target.exists():
            self._safe_remove_path(target)

        if not target.exists():
            try:
                shutil.copytree(source, target)
                return "copied"
            except shutil.Error as exc:
                # Fall back to symlink when disk is full.
                if "No space left on device" not in str(exc):
                    raise
                self._log.warning(
                    "Insufficient disk space while copying %s -> %s. Falling back to symlink.",
                    source,
                    target,
                )
                if target.exists():
                    self._safe_remove_path(target)
                target.symlink_to(source, target_is_directory=True)
                return "symlinked"
            except OSError as exc:
                if exc.errno != errno.ENOSPC:
                    raise
                self._log.warning(
                    "Insufficient disk space while copying %s -> %s. Falling back to symlink.",
                    source,
                    target,
                )
                if target.exists():
                    self._safe_remove_path(target)
                target.symlink_to(source, target_is_directory=True)
                return "symlinked"

        if target.is_symlink():
            return "symlinked"

        shutil.copytree(source, target, dirs_exist_ok=True)
        return "copied"

    def migrate_existing_data(self, overwrite: bool = False, include_tmp: bool = False) -> dict:
        source_main = self._insar_root / "outputs"
        source_tmp = self._insar_root / "outputs_tmp"
        target_main = Path(self._cfg.output_dir)
        target_tmp = target_main.parent / f"{self._cfg.job_name}_outputs_tmp"

        migrated = {
            "outputs_migrated": False,
            "outputs_tmp_migrated": False,
            "outputs_mode": "none",
            "outputs_tmp_mode": "none",
            "outputs_tmp_skipped": not include_tmp,
            "target_output_dir": str(target_main),
            "target_outputs_tmp_dir": str(target_tmp),
        }

        if source_main.exists():
            migrated["outputs_mode"] = self._copy_or_symlink(source_main, target_main, overwrite)
            migrated["outputs_migrated"] = True

        if include_tmp and source_tmp.exists():
            migrated["outputs_tmp_mode"] = self._copy_or_symlink(source_tmp, target_tmp, overwrite)
            migrated["outputs_tmp_migrated"] = True

        return migrated

    def run(self, step: str = "all", dry_run: bool = False, force: bool = False) -> None:
        self._ensure_output_dirs()
        steps = self._get_steps()
        if step not in steps:
            allowed = ", ".join(steps.keys())
            raise ValueError(f"Invalid step '{step}'. Allowed values: {allowed}")

        ctx = {"config": self._legacy_config(), "dry_run": dry_run, "force": force}

        if step == "all":
            for step_name in self.ORDERED_STEPS:
                self._log.info("%s", "-" * 60)
                self._log.info("Running step: %s", step_name.upper())
                self._log.info("%s", "-" * 60)
                _, fn = steps[step_name]
                fn(ctx)
            return

        _, fn = steps[step]
        fn(ctx)
