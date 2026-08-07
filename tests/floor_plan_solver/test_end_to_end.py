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
        generate_floor_plan(  # type: ignore[arg-type]
            FloorPlanSolveRequest(generation_spec, _profile()),
            mode="debug",
        )
