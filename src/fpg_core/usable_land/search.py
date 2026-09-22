from __future__ import annotations

import math
from dataclasses import dataclass

from ..domain import BuildableSpaceErrorCode, FloorWidthAlignment, Point, Polygon
from .config import UsableLandConfig
from .exceptions import UsableLandError
from .geometry import geometry_tolerance


@dataclass(frozen=True, slots=True)
class RectangleCandidate:
    left: int
    bottom: int
    right: int
    top: int
    width: int
    length: int
    area: int
    alignment: FloorWidthAlignment

    @property
    def rank(self) -> tuple[int, int, int, int, int, int, int]:
        return (
            self.area,
            min(self.width, self.length),
            int(self.alignment is FloorWidthAlignment.PARALLEL_TO_ENTRY_ROAD),
            -self.left,
            -self.bottom,
            -self.right,
            -self.top,
        )

    @property
    def polygon(self) -> Polygon:
        return Polygon(
            (
                Point(self.left, self.bottom),
                Point(self.right, self.bottom),
                Point(self.right, self.top),
                Point(self.left, self.top),
            )
        )


def _horizontal_interval(
    polygon: Polygon,
    y_value: float,
    tolerance: float,
) -> tuple[float, float] | None:
    intersections: list[float] = []
    points = polygon.points
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        if abs(start.y - end.y) <= tolerance:
            if abs(y_value - start.y) <= tolerance:
                intersections.extend((start.x, end.x))
            continue
        lower = min(start.y, end.y)
        upper = max(start.y, end.y)
        if y_value < lower - tolerance or y_value > upper + tolerance:
            continue
        ratio = (y_value - start.y) / (end.y - start.y)
        if -tolerance <= ratio <= 1.0 + tolerance:
            intersections.append(start.x + ratio * (end.x - start.x))
    if len(intersections) < 2:
        return None
    return min(intersections), max(intersections)


def find_best_local_rectangle(
    polygon: Polygon,
    config: UsableLandConfig,
) -> tuple[RectangleCandidate, int]:
    tolerance = geometry_tolerance(polygon.points)
    minimum_y = min(point.y for point in polygon.points)
    maximum_y = max(point.y for point in polygon.points)
    resolution = config.search_resolution
    first = math.ceil((minimum_y - tolerance) / resolution)
    last = math.floor((maximum_y + tolerance) / resolution)
    rows = tuple(index * resolution for index in range(first, last + 1))
    if len(rows) > config.maximum_sweep_lines:
        raise UsableLandError(
            BuildableSpaceErrorCode.SEARCH_LIMIT_EXCEEDED,
            "The usable-land search exceeds the configured synchronous limit.",
            details={
                "estimated_sweep_lines": len(rows),
                "maximum_sweep_lines": config.maximum_sweep_lines,
                "search_resolution": resolution,
            },
        )

    intervals = tuple(_horizontal_interval(polygon, row, tolerance) for row in rows)
    best: RectangleCandidate | None = None
    evaluated = 0
    for lower_index, bottom in enumerate(rows):
        lower_interval = intervals[lower_index]
        if lower_interval is None:
            continue
        for upper_index in range(lower_index + 1, len(rows)):
            top = rows[upper_index]
            upper_interval = intervals[upper_index]
            if upper_interval is None:
                continue
            evaluated += 1
            left_value = max(lower_interval[0], upper_interval[0])
            right_value = min(lower_interval[1], upper_interval[1])
            left = math.ceil(left_value - tolerance)
            right = math.floor(right_value + tolerance)
            snapped_bottom = math.ceil(bottom - tolerance)
            snapped_top = math.floor(top + tolerance)
            horizontal = right - left
            vertical = snapped_top - snapped_bottom
            if horizontal <= 0 or vertical <= 0:
                continue

            assignments = (
                (
                    FloorWidthAlignment.PARALLEL_TO_ENTRY_ROAD,
                    horizontal,
                    vertical,
                ),
                (
                    FloorWidthAlignment.PERPENDICULAR_TO_ENTRY_ROAD,
                    vertical,
                    horizontal,
                ),
            )
            for alignment, width, length in assignments:
                if width < config.minimum_width or length < config.minimum_length:
                    continue
                candidate = RectangleCandidate(
                    left=left,
                    bottom=snapped_bottom,
                    right=right,
                    top=snapped_top,
                    width=width,
                    length=length,
                    area=width * length,
                    alignment=alignment,
                )
                if best is None or candidate.rank > best.rank:
                    best = candidate

    if best is None:
        raise UsableLandError(
            BuildableSpaceErrorCode.NO_USABLE_LAND_FOUND,
            "No usable rectangle satisfies the configured minimum dimensions.",
            details={
                "minimum_width": config.minimum_width,
                "minimum_length": config.minimum_length,
            },
        )
    return best, evaluated
