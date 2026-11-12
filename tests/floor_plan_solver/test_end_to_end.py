from __future__ import annotations

from dataclasses import replace

import pytest

from fpg_core.domain import (
    ExecutionMode,
    FloorPlanGenerationSpec,
    FloorSpec,
    RoomSizeSpec,
)
from fpg_core.floor_plan_solver import (
    GenerationProfile,
    PreparationConfig,
    SolverConfig,
)
from fpg_core.floor_plan_solver.api import (
    FloorPlanSolveRequest,
    SolverDiagnostics,
    generate_floor_plan,
)


def _profile() -> GenerationProfile:
    return GenerationProfile(
        name="test",
        hard_constraints=(),
        soft_constraints=(),
        solver=SolverConfig(
            max_time_seconds=1,
            num_search_workers=1,
            random_seed=0,
        ),
        preparation=PreparationConfig(coordinate_scale=1),
    )


def test_production_and_debug_execution(generation_spec: FloorPlanGenerationSpec) -> None:
    request = FloorPlanSolveRequest(generation_spec, _profile())

    production = generate_floor_plan(request)
    explicit_production = generate_floor_plan(
        request,
        mode=ExecutionMode.PRODUCTION,
    )
    debug = generate_floor_plan(request, mode=ExecutionMode.DEBUG)

    assert production.result.solved
    assert production.details is None
    assert production.metadata.mode is ExecutionMode.PRODUCTION
    assert explicit_production.result.status is production.result.status
    assert explicit_production.details is None
    assert debug.result.status is production.result.status
    assert debug.result.solved
    assert isinstance(debug.details, SolverDiagnostics)
    assert debug.metadata.mode is ExecutionMode.DEBUG
    assert debug.metadata.duration_seconds >= 0


def test_infeasible_status_is_returned(generation_spec: FloorPlanGenerationSpec) -> None:
    rooms = tuple(
        replace(room, size=RoomSizeSpec(10, 10, 100, 100))
        for room in generation_spec.rooms
    )
    request = FloorPlanSolveRequest(
        replace(generation_spec, floor=FloorSpec(10, 10), rooms=rooms),
        _profile(),
    )

    execution = generate_floor_plan(request)

    assert not execution.result.solved
    assert execution.result.floor_plan is None


def test_invalid_mode_is_rejected(generation_spec: FloorPlanGenerationSpec) -> None:
    with pytest.raises(TypeError, match="ExecutionMode"):
        generate_floor_plan(
            FloorPlanSolveRequest(generation_spec, _profile()),
            mode="debug",  # type: ignore[arg-type]
        )


def test_custom_profiles_control_bathroom_hallway_rule() -> None:
    from fpg_core.domain import RoomId, RoomSpec, RoomType

    bathroom = RoomSpec(
        id=RoomId("bathroom"),
        name="Bathroom",
        room_type=RoomType.BATHROOM,
        size=RoomSizeSpec(10, 20, 100, 400),
    )
    specification = FloorPlanGenerationSpec(
        floor=FloorSpec(30, 30), rooms=(bathroom,), room_relations=()
    )
    execution = generate_floor_plan(
        FloorPlanSolveRequest(specification, _profile()),
        mode=ExecutionMode.DEBUG,
    )

    assert execution.result.solved
    assert execution.details is not None
    assert "bathroom_hallway_shared_wall" not in execution.details.applied_hard_constraints


def test_hallway_minimum_in_project_units_at_nondefault_scale() -> None:
    from fpg_core.domain import RoomId, RoomSpec, RoomType
    from fpg_core.floor_plan_solver import HardConstraintUse
    from fpg_core.floor_plan_solver.exceptions import InvalidProfileError

    room = RoomSpec(id=RoomId("hall"), name="Hall", room_type=RoomType.HALLWAY,
                    size=RoomSizeSpec(5, 15, 50, 400))
    spec = FloorPlanGenerationSpec(floor=FloorSpec(20, 20), rooms=(room,), room_relations=())
    config = replace(_profile(), preparation=PreparationConfig(coordinate_scale=10))
    solved = generate_floor_plan(FloorPlanSolveRequest(spec, config))
    assert solved.result.solved
    points = solved.result.floor_plan.rooms[0].boundary.points
    assert max(p.x for p in points) - min(p.x for p in points) >= 10
    assert max(p.y for p in points) - min(p.y for p in points) >= 10
    invalid = replace(config, hard_constraints=(HardConstraintUse("hallway_dimensions", {"minimum_width": 8}),))
    with pytest.raises(InvalidProfileError, match="at least 10"):
        generate_floor_plan(FloorPlanSolveRequest(spec, invalid))
