from __future__ import annotations

from collections.abc import Iterable

from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


def room_polygon(points: Iterable[tuple[float, float]]) -> Polygon:
    return Polygon(points)


def occupied_footprint(polygons: Iterable[BaseGeometry]) -> BaseGeometry:
    return unary_union(list(polygons))


def shared_boundary(first: BaseGeometry, second: BaseGeometry) -> BaseGeometry:
    return first.boundary.intersection(second.boundary)


def boundary_distance(first: BaseGeometry, second: BaseGeometry) -> float:
    return float(first.boundary.distance(second.boundary))


def is_rectilinear(points: tuple[tuple[float, float], ...], tolerance: float) -> bool:
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx <= tolerance and dy <= tolerance:
            continue
        if dx > tolerance and dy > tolerance:
            return False
    return True


def detect_voids(footprint: BaseGeometry) -> tuple[Polygon, ...]:
    if isinstance(footprint, Polygon):
        polygons = (footprint,)
    elif isinstance(footprint, MultiPolygon):
        polygons = tuple(footprint.geoms)
    else:
        polygons = tuple(
            geometry
            for geometry in getattr(footprint, "geoms", ())
            if isinstance(geometry, Polygon)
        )
    return tuple(
        Polygon(interior) for polygon in polygons for interior in polygon.interiors
    )
