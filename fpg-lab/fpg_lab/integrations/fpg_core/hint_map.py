"""Validation and export of portable cleaned candidate inputs."""

from math import isfinite

from fpg_core.domain import CandidateMap, FloorPlanGenerationSpec
from fpg_core.floor_plan_solver import RoomPlacementHint
from pydantic import TypeAdapter


def validate_export(data: dict) -> FloorPlanGenerationSpec:
    if data.get("version") != 1:
        raise ValueError("Unsupported hint map version")
    from fpg_lab.inputs import FloorPlanRequest

    FloorPlanRequest.model_validate(data["request"])
    units = data["project_units_per_meter"]
    if isinstance(units, bool) or not isinstance(units, int) or units <= 0:
        raise ValueError("Project units per metre must be a positive integer")
    TypeAdapter(CandidateMap).validate_python(data["candidate"])
    spec = TypeAdapter(FloorPlanGenerationSpec).validate_python(data["specification"])
    if not all(isfinite(v) and v > 0 for v in (spec.floor.width, spec.floor.length)):
        raise ValueError("Floor dimensions must be positive and finite")
    ids = [str(room.id) for room in spec.rooms]
    if not ids or len(ids) != len(set(ids)) or any(not i.strip() for i in ids):
        raise ValueError("Room identities must be nonempty and unique")
    for room in spec.rooms:
        size = room.size
        if (
            not all(
                isfinite(v) and v > 0
                for v in (size.min_width, size.max_width, size.min_area, size.max_area)
            )
            or size.min_width > size.max_width
            or size.min_area > size.max_area
        ):
            raise ValueError(f"Invalid size requirements for {room.id}")
    for room in spec.rooms:
        if room.room_type.value == "hallway" and min(room.size.min_width, room.size.max_width) < 10:
            raise ValueError(
                "Hint map has a hallway narrower than 10 units; regenerate the P01A preset"
            )
    for relation in spec.room_relations:
        if (
            relation.source_room_id not in ids
            or not relation.target_room_ids
            or any(target not in ids for target in relation.target_room_ids)
        ):
            raise ValueError("Room relation references unknown identities")
    points = data["candidate"]["points"]
    point_ids = [str(point["room_id"]) for point in points]
    if len(point_ids) != len(set(point_ids)) or set(point_ids) != set(ids):
        raise ValueError("Candidate identities must match the generation specification")
    rooms = {str(room.id): room for room in spec.rooms}
    for point in points:
        x, y = float(point["x"]), float(point["y"])
        if (
            not isfinite(x)
            or not isfinite(y)
            or not 0 <= x <= spec.floor.width
            or not 0 <= y <= spec.floor.length
        ):
            raise ValueError("Hint coordinates must be finite and inside the floor")
        if point.get("room_type") != rooms[str(point["room_id"])].room_type.value:
            raise ValueError("Hint room type does not match its specification")
    return spec


def candidate_hints(document):
    return tuple(
        RoomPlacementHint(
            room_id=point["room_id"], x=point["x"], y=point["y"], position_reference="center"
        )
        for point in document["candidate"]["points"]
    )
