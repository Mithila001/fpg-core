"""Shared deterministic room-area allocation and candidate footprints."""

from dataclasses import dataclass
from functools import lru_cache
from math import hypot, isfinite, pi, sqrt

from ..domain import FloorPlanGenerationSpec, RoomType
from .exceptions import ScoringInputError


@dataclass(frozen=True, slots=True)
class Footprint:
    point: object
    allocated_area: float
    radius: float


@lru_cache(maxsize=128)
def allocated_areas(specification: FloorPlanGenerationSpec) -> dict[str, float]:
    if not all(
        isfinite(v) and v > 0
        for v in (specification.floor.width, specification.floor.length)
    ):
        raise ScoringInputError("Floor dimensions must be positive and finite.")
    for room in specification.rooms:
        size = room.size
        if (
            not all(isfinite(v) for v in (size.min_area, size.max_area, size.max_width))
            or size.min_area <= 0
            or size.max_area < size.min_area
            or size.max_width <= 0
        ):
            raise ScoringInputError(
                f"Invalid footprint size specification for room '{room.id}'."
            )
    rooms = [
        room for room in specification.rooms if room.room_type is not RoomType.HALLWAY
    ]
    reserved = sum(
        room.size.min_area
        for room in specification.rooms
        if room.room_type is RoomType.HALLWAY
    )
    available = specification.floor.width * specification.floor.length - reserved
    minimum = sum(room.size.min_area for room in rooms)
    maximum = sum(room.size.max_area for room in rooms)
    if available < minimum - 1e-9:
        raise ScoringInputError(
            "Floor area is insufficient for minimum room areas and full hallway capacity."
        )
    expansion = maximum - minimum
    factor = (
        min(1.0, max(0.0, (available - minimum) / expansion)) if expansion > 0 else 0.0
    )
    return {
        str(room.id): room.size.min_area
        + factor * (room.size.max_area - room.size.min_area)
        for room in rooms
    }


def build_footprints(specification, data):
    areas = allocated_areas(specification)
    rooms = {str(room.id): room for room in specification.rooms}
    result = {}
    for point in data.points:
        room = rooms.get(point.source_room_id)
        if room is None or room.room_type is not point.room_type:
            raise ScoringInputError(
                f"Candidate point '{point.source_room_id}' does not match the specification."
            )
        if room.room_type is RoomType.HALLWAY:
            radius = room.size.max_width / 2
            area = pi * radius * radius
        else:
            area = areas[point.source_room_id]
            radius = sqrt(area / pi)
        result[point.room_id] = Footprint(point, area, radius)
    return result


def boundary_distance(a, b):
    return max(
        0.0, hypot(a.point.x - b.point.x, a.point.y - b.point.y) - a.radius - b.radius
    )


def proximity_score(distance, preferred, zero):
    if (
        not all(isfinite(value) for value in (distance, preferred, zero))
        or preferred < 0
        or zero <= preferred
    ):
        raise ValueError(
            "Proximity zero distance must exceed the nonnegative preferred distance."
        )
    return 100 * max(0.0, min(1.0, (zero - distance) / (zero - preferred)))
