from __future__ import annotations

from shapely.geometry import Polygon as ShapelyPolygon

from ..types import FloorPlan, RoomId, RoomRole
from .contracts import PostProcessingProfile
from .exceptions import ConfigurationError, ValidationError
from .geometry import normalize_polygon, to_shapely


def validate_profile(profile: PostProcessingProfile) -> None:
    if not profile.name.strip():
        raise ConfigurationError("profile name cannot be empty")
    if profile.numeric.tolerance <= 0:
        raise ConfigurationError("geometry tolerance must be positive")
    if profile.numeric.grid_size <= 0:
        raise ConfigurationError("grid size must be positive")
    ids = [use.processor_id for use in profile.processors]
    if len(ids) != len(set(ids)):
        raise ConfigurationError("a profile cannot contain a processor more than once")


def validate_floor_plan(
    floor_plan: FloorPlan,
    *,
    tolerance: float,
    require_no_placeholders: bool = False,
    reject_openings: bool = False,
) -> None:
    if reject_openings and floor_plan.openings:
        raise ValidationError(
            "geometry-changing profiles require a plan without openings"
        )

    if normalize_polygon(floor_plan.boundary, tolerance) != floor_plan.boundary:
        raise ValidationError("floor boundary is not in canonical polygon form")
    floor_shape = to_shapely(floor_plan.boundary)
    ids = [room.id for room in floor_plan.rooms]
    names = [room.name for room in floor_plan.rooms]
    if len(ids) != len(set(ids)):
        raise ValidationError("room IDs must be unique")
    if len(names) != len(set(names)):
        raise ValidationError("room names must be unique")
    id_set = set(ids)

    standard_shapes: list[tuple[RoomId, ShapelyPolygon]] = []
    for room in floor_plan.rooms:
        if normalize_polygon(room.boundary, tolerance) != room.boundary:
            raise ValidationError(f"room {room.id!s} is not in canonical polygon form")
        shape = to_shapely(room.boundary)
        if not floor_shape.buffer(tolerance).covers(shape):
            raise ValidationError(f"room {room.id!s} lies outside the floor boundary")
        if room.parent_room_id is not None and room.parent_room_id not in id_set:
            raise ValidationError(f"room {room.id!s} has an unknown parent room")
        if require_no_placeholders and room.role is RoomRole.SOLVER_PLACEHOLDER:
            raise ValidationError("placeholder rooms remain in the final floor plan")
        if room.role is RoomRole.STANDARD:
            standard_shapes.append((room.id, shape))

    for index, (left_id, left) in enumerate(standard_shapes):
        for right_id, right in standard_shapes[index + 1 :]:
            if left.intersection(right).area > tolerance:
                raise ValidationError(f"rooms {left_id!s} and {right_id!s} overlap")

    for source, target in floor_plan.identity_redirects.items():
        if source in id_set:
            raise ValidationError("an identity redirect source must have been removed")
        if target not in id_set:
            raise ValidationError("identity redirect target does not exist")
        seen = {source}
        cursor = target
        while cursor in floor_plan.identity_redirects:
            if cursor in seen:
                raise ValidationError("identity redirects must be acyclic")
            seen.add(cursor)
            cursor = floor_plan.identity_redirects[cursor]

    for opening in floor_plan.openings:
        if any(room_id not in id_set for room_id in opening.connected_room_ids):
            raise ValidationError(f"opening {opening.id!s} references an unknown room")
