from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from shapely.geometry import LineString, Polygon

from .exterior_profile import exterior_profile
from .recesses import lines


@dataclass(frozen=True)
class DirectionalExposure:
    exposed_length: float
    longest_exposed_segment: float
    exposed: tuple[LineString, ...]
    obstructed: tuple[LineString, ...]
    obstructing_room_ids: tuple[str, ...]
    full_exposure: bool


def directional_exposure(
    room: Polygon, others: Mapping[str, Polygon], direction: str
) -> DirectionalExposure:
    """Measure outward-visible walls, subtracting blockers at any distance."""
    profile = exterior_profile(room, direction)
    horizontal = direction in ("front", "back")
    low_side = direction in ("front", "left")
    exposed: list[LineString] = []
    obstructed: list[LineString] = []
    blockers: set[str] = set()
    for segment in profile.segments:
        coordinates = {segment.start, segment.end}
        for other in others.values():
            for ring in (other.exterior, *other.interiors):
                for x, y in ring.coords:
                    value = x if horizontal else y
                    if segment.start < value < segment.end:
                        coordinates.add(value)
        ordered = sorted(coordinates)
        # Merge only pieces on the same physical wall, never disconnected walls.
        previous_blocked = None
        for start, end in zip(ordered, ordered[1:], strict=False):
            mid = (start + end) / 2
            found = set()
            for room_id, other in others.items():
                left, bottom, right, top = other.bounds
                probe = (
                    LineString(((mid, bottom), (mid, top)))
                    if horizontal
                    else LineString(((left, mid), (right, mid)))
                )
                for part in lines(other.intersection(probe)):
                    values = [y if horizontal else x for x, y in part.coords]
                    if (
                        min(values) < segment.position
                        if low_side
                        else max(values) > segment.position
                    ):
                        found.add(room_id)
                        break
            blocked = bool(found)
            blockers.update(found)
            result = obstructed if blocked else exposed
            if previous_blocked == blocked:
                start = result.pop().coords[0][0 if horizontal else 1]
            result.append(
                LineString(((start, segment.position), (end, segment.position)))
                if horizontal
                else LineString(((segment.position, start), (segment.position, end)))
            )
            previous_blocked = blocked
    return DirectionalExposure(
        sum(part.length for part in exposed),
        max((part.length for part in exposed), default=0.0),
        tuple(exposed),
        tuple(obstructed),
        tuple(sorted(blockers)),
        not obstructed and bool(profile.segments),
    )
