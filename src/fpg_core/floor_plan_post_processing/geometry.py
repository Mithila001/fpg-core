from __future__ import annotations

from math import isclose

from shapely.geometry import LineString
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.polygon import orient

from ..domain import Point, Polygon
from .exceptions import ProcessorError, ValidationError


def to_shapely(polygon: Polygon) -> ShapelyPolygon:
    return ShapelyPolygon([(point.x, point.y) for point in polygon.points])


def from_shapely(polygon: ShapelyPolygon, tolerance: float) -> Polygon:
    if polygon.is_empty or not polygon.is_valid or polygon.area <= tolerance:
        raise ProcessorError("processor produced an invalid or empty polygon")
    if polygon.interiors:
        raise ProcessorError("polygon holes are unsupported")
    normalized = orient(polygon, sign=1.0)
    points = [
        Point(float(x), float(y)) for x, y in list(normalized.exterior.coords)[:-1]
    ]
    return normalize_polygon(Polygon(tuple(points)), tolerance)


def normalize_polygon(polygon: Polygon, tolerance: float) -> Polygon:
    points = list(polygon.points)
    if len(points) > 1 and points_close(points[0], points[-1], tolerance):
        points.pop()

    deduplicated: list[Point] = []
    for point in points:
        if not deduplicated or not points_close(deduplicated[-1], point, tolerance):
            deduplicated.append(point)
    if len(deduplicated) < 3:
        raise ValidationError("polygon requires at least three distinct points")

    shape = ShapelyPolygon([(point.x, point.y) for point in deduplicated])
    if shape.is_empty or not shape.is_valid or shape.area <= tolerance:
        raise ValidationError("polygon must be simple, valid, and positive-area")
    if shape.interiors:
        raise ValidationError("polygon holes are unsupported")
    shape = orient(shape, sign=1.0)
    return Polygon(
        tuple(Point(float(x), float(y)) for x, y in list(shape.exterior.coords)[:-1])
    )


def points_close(left: Point, right: Point, tolerance: float) -> bool:
    return isclose(left.x, right.x, abs_tol=tolerance) and isclose(
        left.y, right.y, abs_tol=tolerance
    )


def line_strings(geometry: object) -> list[LineString]:
    if isinstance(geometry, LineString):
        return [geometry]
    geoms = getattr(geometry, "geoms", ())
    return [geom for geom in geoms if isinstance(geom, LineString)]
