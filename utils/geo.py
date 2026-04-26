import numpy as np
from matplotlib.path import Path


def build_dam_mask(catchment_bbox, image_size, dam_polygon_coords):
    """
    Rasterize the dam polygon onto the catchment image grid.

    Returns a boolean (H, W) mask — True where the pixel centre falls
    inside the dam polygon.  Used to exclude dam/reservoir pixels from
    snow detection (water produces false-positive NDSI).

    Parameters
    ----------
    catchment_bbox : sentinelhub.BBox
        Bounding box of the catchment raster.
    image_size : tuple[int, int]
        (width, height) of the raster in pixels.
    dam_polygon_coords : list[list[float]]
        Ring of [lon, lat] coordinate pairs defining the dam boundary.
    """
    w, h = image_size
    min_lon = catchment_bbox.min_x
    min_lat = catchment_bbox.min_y
    max_lon = catchment_bbox.max_x
    max_lat = catchment_bbox.max_y

    poly_pixels = []
    for lon, lat in dam_polygon_coords:
        col = (lon - min_lon) / (max_lon - min_lon) * w
        row = (max_lat - lat) / (max_lat - min_lat) * h  # y-axis inverted
        poly_pixels.append((col, row))

    path = Path(poly_pixels)

    cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    points = np.column_stack([cols.ravel(), rows.ravel()])

    mask = path.contains_points(points).reshape(h, w)
    return mask
