import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class BasePipeline(ABC):
    """
    Template-method pipeline loop shared by WaterPipeline and SnowPipeline.

    Subclasses implement the domain-specific pieces; the shared loop lives here.
    """

    def __init__(self, repo, sentinel_service, visualizer, plots_dir: str):
        self._repo = repo
        self._sentinel = sentinel_service
        self._viz = visualizer
        self._plots_dir = plots_dir

    # ── abstract interface ───────────────────────────────────────────────

    @abstractmethod
    def get_time_windows(self) -> list[tuple[str, str]]:
        """Return available (date_from, date_to) windows."""
        ...

    @abstractmethod
    def fetch_index_array(self, t_from: str, t_to: str, force: bool = False):
        """Fetch raw index array. Returns np.ndarray or None on failure."""
        ...

    @abstractmethod
    def compute_reading(self, t_from: str, t_to: str, index_arr):
        """Apply masks + quality gates. Returns (reading, index_arr) or (None, index_arr)."""
        ...

    @abstractmethod
    def viz_filenames(self) -> list[str]:
        """Expected PNG filenames for per-date viz cache check."""
        ...

    @abstractmethod
    def run_per_date_viz(self, t_from: str, t_to: str, index_arr, date_dir: str) -> None:
        ...

    @abstractmethod
    def run_summary_viz(self, arrays_by_date: list, viz_dates: list, rebuild_manifest: bool = False) -> None:
        ...

    @abstractmethod
    def get_metadata(self) -> dict:
        """Metadata dict merged into the saved JSON (e.g. reservoir name, generated)."""
        ...

    def is_cached_entry_valid(self, entry) -> bool:
        """Override to add re-validation of cached entries (e.g. cloud % check)."""
        return True

    def on_new_array(self, t_from: str, index_arr) -> None:
        """Hook called after a new index array is computed (e.g. for ndsi_cache)."""

    # ── shared loop ──────────────────────────────────────────────────────

    def run(self, visualize: bool = True, force: bool = False, rebuild_manifest: bool = False) -> None:
        print(f"Visualize: {'yes' if visualize else 'no'}")
        print(f"Force:     {'yes' if force else 'no (using cache)'}")
        print(f"Rebuild manifest: {'yes' if rebuild_manifest else 'no'}\n")

        os.makedirs("data", exist_ok=True)
        if visualize:
            os.makedirs(self._plots_dir, exist_ok=True)

        all_existing = self._repo.load_as_cache()
        cached = {} if force else all_existing
        if all_existing:
            print(f"  Cache: {len(all_existing)} existing readings loaded")

        print("Step 1: Catalog search for clear scenes...")
        windows = self.get_time_windows()
        print(f"  → {len(windows)} valid windows found\n")

        if not windows:
            print("ERROR: No scenes found. Try relaxing cloud cover or widening time range.")
            return

        results = []
        arrays = []
        viz_dates = []
        skipped = 0

        for i, (t_from, t_to) in enumerate(windows):
            cache_key = f"{t_from}|{t_to}"
            viz_cached = visualize and self._has_viz_cache(t_from)

            if cache_key in cached and (not visualize or viz_cached):
                entry = cached[cache_key]
                if not self.is_cached_entry_valid(entry):
                    continue
                results.append(entry)
                if viz_cached:
                    viz_dates.append(t_from)
                skipped += 1
                print(f"Step 2 [{i+1}/{len(windows)}]: {t_from} → {t_to}  [cached]")
                continue

            print(f"Step 2 [{i+1}/{len(windows)}]: Fetching {t_from} → {t_to}")

            index_arr = self.fetch_index_array(t_from, t_to, force=force)
            if index_arr is None:
                if cache_key in cached:
                    results.append(cached[cache_key])
                print(f"  → Skipped (fetch failed)")
                continue

            reading, index_arr = self.compute_reading(t_from, t_to, index_arr)
            if reading is None:
                continue

            results.append(reading)
            arrays.append((t_from, index_arr))
            self.on_new_array(t_from, index_arr)

            if visualize:
                date_dir = os.path.join(self._plots_dir, t_from)
                os.makedirs(date_dir, exist_ok=True)
                print(f"    [viz] Generating per-date plots...")
                self.run_per_date_viz(t_from, t_to, index_arr, date_dir)
                viz_dates.append(t_from)

        if skipped:
            print(f"\n  → {skipped} windows from cache, {len(results) - skipped} freshly fetched")

        merged = {**all_existing}
        for r in results:
            merged[r.cache_key()] = r
        final_results = list(merged.values())

        metadata = {
            **self.get_metadata(),
            "generated": datetime.now(timezone.utc).isoformat(),
        }
        self._repo.save_all(final_results, metadata)
        new_count = len(final_results) - len(all_existing)
        print(f"\nDone. {len(final_results)} readings total ({new_count} new).")

        if visualize and viz_dates:
            print(f"\nStep 3: Generating summary visualizations...")
            self.run_summary_viz(arrays, viz_dates, rebuild_manifest)
            print(f"\nAll visualizations saved to {self._plots_dir}/")

    def _has_viz_cache(self, date: str) -> bool:
        date_dir = os.path.join(self._plots_dir, date)
        return all(
            os.path.exists(os.path.join(date_dir, f))
            for f in self.viz_filenames()
        )
