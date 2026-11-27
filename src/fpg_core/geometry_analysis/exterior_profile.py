from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from .recesses import lines, polygons


@dataclass(frozen=True)
class ExteriorWallSegment:
    start: float
    end: float
    position: float
    geometry: LineString

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class ExteriorWallStep:
    location: float
    depth: float
    geometry: LineString
    before: ExteriorWallSegment
    after: ExteriorWallSegment


@dataclass(frozen=True)
class ExteriorProfile:
    direction: str
    segments: tuple[ExteriorWallSegment, ...]
    steps: tuple[ExteriorWallStep, ...]


def exterior_profile(footprint: BaseGeometry, direction: str) -> ExteriorProfile:
    """Measure the outward silhouette of a rectilinear occupied footprint."""
    if direction not in ("front", "back", "left", "right"):
        raise ValueError(f"unknown exterior direction: {direction}")
    horizontal = direction in ("front", "back")
    low_side = direction in ("front", "left")
    parts = polygons(footprint)
    if not parts:
        return ExteriorProfile(direction, (), ())
    coords = sorted(
        {
            (x if horizontal else y)
            for polygon in parts
            for ring in (polygon.exterior, *polygon.interiors)
            for x, y in ring.coords
        }
    )
    left, bottom, right, top = footprint.bounds
    segments: list[ExteriorWallSegment] = []
    for start, end in zip(coords, coords[1:], strict=False):
        mid = (start + end) / 2
        probe = (
            LineString(((mid, bottom), (mid, top)))
            if horizontal
            else LineString(((left, mid), (right, mid)))
        )
        intersections = lines(footprint.intersection(probe))
        if not intersections:
            continue
        values = [
            value
            for part in intersections
            for x, y in part.coords
            for value in ((y if horizontal else x),)
        ]
        position = min(values) if low_side else max(values)
        if segments and segments[-1].end == start and segments[-1].position == position:
            start = segments.pop().start
        geometry = (
            LineString(((start, position), (end, position)))
            if horizontal
            else LineString(((position, start), (position, end)))
        )
        segments.append(ExteriorWallSegment(start, end, position, geometry))
    steps = []
    for before, after in zip(segments, segments[1:], strict=False):
        if before.end != after.start or before.position == after.position:
            continue
        location = before.end
        geometry = (
            LineString(((location, before.position), (location, after.position)))
            if horizontal
            else LineString(((before.position, location), (after.position, location)))
        )
        if not footprint.boundary.covers(geometry):
            continue
        steps.append(
            ExteriorWallStep(
                location, abs(after.position - before.position), geometry, before, after
            )
        )
    return ExteriorProfile(direction, tuple(segments), tuple(steps))
