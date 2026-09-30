from __future__ import annotations

from fpg_core.domain import (
    ExecutionMode,
    FloorPlanGenerationSpec,
    FloorSpec,
    RoomId,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)
from fpg_core.floor_plan_openings import (
    DEFAULT_OPENING_CONFIG,
    OpeningGenerationRequest,
    generate_openings,
)
from fpg_core.floor_plan_post_processing import (
    FloorPlanPostProcessingConfig,
    PipelineStatus,
    PostProcessingRequest,
    post_process_floor_plan,
)
from fpg_core.floor_plan_scoring import (
    FloorPlanScoringInput,
    create_default_config as create_default_scoring_config,
    score_floor_plan,
)
from fpg_core.floor_plan_solver import (
    FloorPlanSolveRequest,
    FloorPlanSolverConfig,
    PreparationConfig,
    SolverConfig,
    generate_floor_plan,
)


def _single_room_specification() -> FloorPlanGenerationSpec:
    return FloorPlanGenerationSpec(
        floor=FloorSpec(width=20.0, length=20.0),
        rooms=(
            RoomSpec(
                id=RoomId("living"),
                room_type=RoomType.LIVING_ROOM,
                name="Living Room",
                size=RoomSizeSpec(
                    min_width=20.0,
                    max_width=20.0,
                    min_area=400.0,
                    max_area=400.0,
                ),
            ),
        ),
        room_relations=(),
    )


def test_plan_flow_public_contracts_connect() -> None:
    specification = _single_room_specification()
    solver_config = FloorPlanSolverConfig(
        name="targeted_flow",
        hard_constraints=(),
        soft_constraints=(),
        solver=SolverConfig(
            max_time_seconds=2.0,
            num_search_workers=1,
            random_seed=1,
        ),
        preparation=PreparationConfig(coordinate_scale=1),
    )

    solved = generate_floor_plan(
        FloorPlanSolveRequest(specification=specification, config=solver_config),
        mode=ExecutionMode.DEBUG,
    )
    assert solved.result.solved
    assert solved.details is not None
    assert solved.result.floor_plan is not None

    post_processed = post_process_floor_plan(
        PostProcessingRequest(
            floor_plan=solved.result.floor_plan,
            specification=specification,
            config=FloorPlanPostProcessingConfig(
                name="targeted_flow_noop",
                processors=(),
            ),
        ),
        mode=ExecutionMode.DEBUG,
    )
    assert post_processed.result.status is PipelineStatus.SUCCESS
    assert post_processed.details is not None

    openings = generate_openings(
        OpeningGenerationRequest(
            floor_plan=post_processed.result.floor_plan,
            config=DEFAULT_OPENING_CONFIG,
        ),
        mode=ExecutionMode.DEBUG,
    )
    assert openings.result.solved
    assert openings.details is not None
    assert openings.result.floor_plan is not None

    scoring = score_floor_plan(
        FloorPlanScoringInput(
            floor_plan=openings.result.floor_plan,
            specification=specification,
            config=create_default_scoring_config(),
        ),
        mode=ExecutionMode.DEBUG,
    )
    assert scoring.details is not None
    assert 0.0 <= scoring.result.total_score <= 100.0
