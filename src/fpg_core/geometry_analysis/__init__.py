"""Shared physical geometry measurements, independent of feature policy."""

from .api import (
    Recess,
    Section,
    boundary_distance,
    detect_recesses,
    detect_voids,
    is_rectilinear,
    lines,
    occupied_footprint,
    polygons,
    room_polygon,
    shared_boundary,
)

__all__ = [
    "Recess", "Section", "boundary_distance", "detect_recesses", "detect_voids",
    "is_rectilinear", "lines", "occupied_footprint", "polygons", "room_polygon",
    "shared_boundary",
]
