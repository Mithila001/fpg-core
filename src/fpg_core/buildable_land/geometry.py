from __future__ import annotations

import math

from ..types import Point, Polygon, Segment

ABS_TOLERANCE = 1e-7
REL_TOLERANCE = 1e-9


def geometry_tolerance(points: tuple[Point, ...]) -> float:
    scale = max(
        (max(abs(point.x), abs(point.y)) for point in points),
        default=1.0,
    )
    return ABS_TOLERANCE + REL_TOLERANCE * max(1.0, scale)


def signed_area(polygon: Polygon) -> float:
    total = 0.0
    points = polygon.points
    for index, point in enumerate(points):
        following = points[(index + 1) % len(points)]
        total += point.x * following.y - following.x * point.y
    return total / 2.0


def polygon_area(polygon: Polygon) -> float:
    return abs(signed_area(polygon))


def unit_inward_normal(segment: Segment) -> tuple[float, float]:
    dx = segment.end.x - segment.start.x
    dy = segment.end.y - segment.start.y
    magnitude = math.hypot(dx, dy)
    if magnitude <= ABS_TOLERANCE:
        raise ValueError("A boundary edge has zero length.")
    return -dy / magnitude, dx / magnitude


def dot(point: Point, vector: tuple[float, float]) -> float:
    return point.x * vector[0] + point.y * vector[1]


def clip_half_plane(
    points: tuple[Point, ...],
    normal: tuple[float, float],
    constant: float,
    tolerance: float,
) -> tuple[Point, ...]:
    if not points:
        return ()

    output: list[Point] = []
    previous = points[-1]
    previous_value = dot(previous, normal) - constant
    previous_inside = previous_value >= -tolerance

    for current in points:
        current_value = dot(current, normal) - constant
        current_inside = current_value >= -tolerance
        if current_inside != previous_inside:
            denominator = previous_value - current_value
            if abs(denominator) <= tolerance:
                raise ValueError("Could not intersect a shifted boundary reliably.")
            ratio = previous_value / denominator
            output.append(
                Point(
                    previous.x + ratio * (current.x - previous.x),
                    previous.y + ratio * (current.y - previous.y),
                )
            )
        if current_inside:
            output.append(current)
        previous = current
        previous_value = current_value
        previous_inside = current_inside

    deduplicated: list[Point] = []
    for point in output:
        if not deduplicated or math.hypot(
            point.x - deduplicated[-1].x,
            point.y - deduplicated[-1].y,
        ) > tolerance:
            deduplicated.append(point)
    if len(deduplicated) > 1 and math.hypot(
        deduplicated[0].x - deduplicated[-1].x,
        deduplicated[0].y - deduplicated[-1].y,
    ) <= tolerance:
        deduplicated.pop()
    return tuple(deduplicated)
