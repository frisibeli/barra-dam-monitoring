"""3D terrain + water visualizer using PyVista.

Renders the reservoir DEM as a mesh with a translucent water plane at the
measured surface elevation. Can produce static images or animated GIFs.

Requires: pyvista, imageio[ffmpeg]
"""
from pathlib import Path
from typing import Sequence


def _load_dem_as_mesh(dem_path: str, cfg):
    """Load DEM GeoTIFF and return a PyVista StructuredGrid mesh."""
    import numpy as np
    import rasterio
    import pyvista as pv
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_bounds

    bbox = cfg.bbox
    w, h = cfg.image_size

    dst_transform = from_bounds(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, w, h)
    dem_arr = np.empty((h, w), dtype=np.float32)

    with rasterio.open(dem_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=dem_arr,
            dst_transform=dst_transform,
            dst_crs="EPSG:4326",
            resampling=Resampling.bilinear,
        )
        nodata = src.nodata
        if nodata is not None:
            dem_arr[dem_arr == nodata] = np.nan

    # Fill NaN with minimum
    dem_arr = np.nan_to_num(dem_arr, nan=float(np.nanmin(dem_arr)))

    # Build XY coordinates in metres (rough approximation)
    import math
    mid_lat = (bbox.min_y + bbox.max_y) / 2
    m_per_deg_lat = 111_320
    m_per_deg_lon = 111_320 * math.cos(math.radians(mid_lat))
    lon_span_m = (bbox.max_x - bbox.min_x) * m_per_deg_lon
    lat_span_m = (bbox.max_y - bbox.min_y) * m_per_deg_lat

    x = np.linspace(0, lon_span_m, w)
    y = np.linspace(0, lat_span_m, h)
    xx, yy = np.meshgrid(x, y)

    grid = pv.StructuredGrid(xx, yy, dem_arr)
    return grid, dem_arr, lon_span_m, lat_span_m


def render_static(
    dem_path: str,
    cfg,
    elevation_m: float | None,
    out_path: str,
    *,
    title: str = "",
    off_screen: bool = True,
) -> None:
    """Render a single frame: DEM mesh + water plane at *elevation_m*."""
    import pyvista as pv
    import numpy as np

    grid, dem_arr, lon_span_m, lat_span_m = _load_dem_as_mesh(dem_path, cfg)

    pl = pv.Plotter(off_screen=off_screen, window_size=(1200, 800))
    pl.background_color = "#1a1a2e"

    # Terrain mesh colored by elevation
    pl.add_mesh(grid, scalars=dem_arr.ravel(order="F"), cmap="terrain",
                show_scalar_bar=False, opacity=0.9)

    # Water plane
    if elevation_m is not None:
        water = pv.Plane(
            center=(lon_span_m / 2, lat_span_m / 2, elevation_m),
            direction=(0, 0, 1),
            i_size=lon_span_m * 1.1,
            j_size=lat_span_m * 1.1,
        )
        pl.add_mesh(water, color="#4fc3f7", opacity=0.55)

        pl.add_text(
            f"{title}  z = {elevation_m:.1f} m a.s.l.",
            position="upper_edge",
            font_size=14,
            color="white",
        )

    pl.camera_position = "iso"
    pl.screenshot(out_path)
    pl.close()
    print(f"  Saved → {out_path}")


def generate_animation(
    dem_path: str,
    cfg,
    readings,
    out_path: str,
    fps: int = 4,
) -> None:
    """Generate a GIF cycling through water elevation for each reading.

    Parameters
    ----------
    readings : list[WaterReading]
        Only readings with elevation_m != None are included.
    """
    import imageio
    import pyvista as pv
    import numpy as np
    import tempfile

    valid = sorted(
        [r for r in readings if r.elevation_m is not None],
        key=lambda r: r.date,
    )
    if not valid:
        print("No readings with elevation_m — skipping animation.")
        return

    frames = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for reading in valid:
            frame_path = Path(tmpdir) / f"{reading.date}.png"
            render_static(
                dem_path, cfg,
                elevation_m=reading.elevation_m,
                out_path=str(frame_path),
                title=reading.date,
            )
            frames.append(imageio.imread(str(frame_path)))

    # Pad last frame for a longer hold
    frames.extend([frames[-1]] * fps)

    imageio.mimsave(out_path, frames, fps=fps, loop=0)
    print(f"Animation saved → {out_path}  ({len(valid)} frames)")
