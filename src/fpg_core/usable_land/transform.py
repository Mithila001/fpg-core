from __future__ import annotations

from dataclasses import dataclass

from .geometry import unit_inward_normal
from ..domain import NormalizedLand, Point, Polygon


@dataclass(frozen=True, slots=True)
class RoadAlignedTransform:
    origin: Point
    x_axis: tuple[float, float]
    y_axis: tuple[float, float]

    def to_local_point(self, point: Point) -> Point:
        dx = point.x - self.origin.x
        dy = point.y - self.origin.y
        return Point(
            dx * self.x_axis[0] + dy * self.x_axis[1],
            dx * self.y_axis[0] + dy * self.y_axis[1],
        )

    def to_world_point(self, point: Point) -> Point:
        return Point(
            self.origin.x
            + point.x * self.x_axis[0]
            + point.y * self.y_axis[0],
            self.origin.y
            + point.x * self.x_axis[1]
            + point.y * self.y_axis[1],
        )

    def to_local_polygon(self, polygon: Polygon) -> Polygon:
        return Polygon(tuple(self.to_local_point(point) for point in polygon.points))

    def to_world_polygon(self, polygon: Polygon) -> Polygon:
        return Polygon(tuple(self.to_world_point(point) for point in polygon.points))


def build_road_aligned_transform(land: NormalizedLand) -> RoadAlignedTransform:
    entry = next(
        edge
        for edge in land.edges
        if edge.source_edge_index == land.main_entry_road.boundary_edge_index
    )
    endpoints = sorted(
        (entry.segment.start, entry.segment.end),
        key=lambda point: (point.x, point.y),
    )
    origin, other = endpoints
    dx = other.x - origin.x
    dy = other.y - origin.y
    magnitude = (dx * dx + dy * dy) ** 0.5
    x_axis = (dx / magnitude, dy / magnitude)
    y_axis = unit_inward_normal(entry.segment)
    return RoadAlignedTransform(origin=origin, x_axis=x_axis, y_axis=y_axis)
