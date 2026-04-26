"""
Backward-compatible shim. Use utils.geo.build_dam_mask going forward.
"""
from utils.geo import build_dam_mask

__all__ = ["build_dam_mask"]
