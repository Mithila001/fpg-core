"""Geometry helpers owned by the usable-land feature."""

from __future__ import annotations

import math

from ..domain import Point, Segment

ABS_TOLERANCE = 1e-7
REL_TOLERANCE = 1e-9


def geometry_tolerance(points: tuple[Point, ...]) -> float:
    scale = max(
        (max(abs(point.x), abs(point.y)) for point in points),
        default=1.0,
    )
    return ABS_TOLERANCE + REL_TOLERANCE * max(1.0, scale)


def unit_inward_normal(segment: Segment) -> tuple[float, float]:
    dx = segment.end.x - segment.start.x
    dy = segment.end.y - segment.start.y
    magnitude = math.hypot(dx, dy)
    if magnitude <= ABS_TOLERANCE:
        raise ValueError("A boundary edge has zero length.")
    return -dy / magnitude, dx / magnitude
