"""Validation and reconstruction of portable cleaned candidate inputs."""

from math import isfinite

from fpg_core.domain import CandidateMap, FloorPlanGenerationSpec
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


def export_trial(experiment: dict, trial: dict) -> dict:
    circulation = trial.get("circulation_data") or {}
    candidate = (circulation.get("result") or {}).get("candidate")
    specification = circulation.get("lab_generation_specification")
    if candidate and not specification:
        from fpg_core.floor_plan_preprocessing import PreparedGenerationInput

        from fpg_lab.core.serialization import to_jsonable

        prepared_data = (experiment.get("preprocessing_result") or {}).get("result")
        if prepared_data:
            prepared = TypeAdapter(PreparedGenerationInput).validate_python(prepared_data)
            cleaned = TypeAdapter(CandidateMap).validate_python(candidate)
            specification = to_jsonable(prepared.generation_spec_for_candidate(cleaned))
    if not candidate or not specification:
        raise ValueError("Cleaned candidate or its specification was not saved for this trial")
    document = {
        "version": 1,
        "candidate": candidate,
        "specification": specification,
        "request": experiment["floor_plan_request"],
        "project_units_per_meter": experiment["system_configuration_snapshot"][
            "project_units_per_meter"
        ],
        "source": {
            "experiment_id": experiment["id"],
            "trial_no": trial["trial_no"],
            "core_version": experiment["fpg_core_version"],
        },
    }
    validate_export(document)
    return document
