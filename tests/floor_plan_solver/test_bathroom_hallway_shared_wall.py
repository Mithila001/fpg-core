from __future__ import annotations

import pytest

from fpg_core.domain import (
    ConstraintStrength,
    FloorPlanGenerationSpec,
    FloorSpec,
    MatchPolicy,
    RoomId,
    RoomRelationSpec,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)
from fpg_core.floor_plan_solver import (
    FloorPlanSolverConfig,
    FloorPlanSolveRequest,
    HardConstraintUse,
    PreparationConfig,
    RoomPlacementHint,
    SeedPolicy,
    SeedSource,
    generate_floor_plan,
)


@pytest.mark.parametrize("side_count, second_x, second_y, solved", [(0, 50, 10, False), (1, 50, 10, True), (1, 10, 30, False), (2, 10, 30, True), (4, 10, 30, True)])
def test_bathroom_shared_side_budget(side_count, second_x, second_y, solved) -> None:
    bathroom = RoomSpec(
        id=RoomId("bathroom"),
        room_type=RoomType.BATHROOM,
        name="Bathroom",
        size=RoomSizeSpec(16, 28, 300, 700),
    )
    hallways = (
        RoomSpec(
            id=RoomId(f"hallway_{index}"),
            room_type=RoomType.HALLWAY,
            name=f"Hallway {index}",
            size=RoomSizeSpec(10, 12, 120, 17_360),
        )
        for index in (1, 2)
    )
    hallway_1, hallway_2 = hallways
    specification = FloorPlanGenerationSpec(
        floor=FloorSpec(112, 155),
        rooms=(bathroom, hallway_1, hallway_2),
        room_relations=(
            RoomRelationSpec(
                source_room_id=bathroom.id,
                target_room_ids=(hallway_1.id, hallway_2.id),
                match_policy=MatchPolicy.OR,
                strength=ConstraintStrength.HARD,
            ),
        ),
    )
    config = FloorPlanSolverConfig(
        name="bathroom_hallway_regression",
        hard_constraints=(HardConstraintUse("bathroom_hallway_shared_wall", {"maximum_shared_sides": side_count}),),
        soft_constraints=(),
        preparation=PreparationConfig(coordinate_scale=1),
        seed=SeedPolicy(
            source=SeedSource.CANDIDATE_HINTS,
            require_source=True,
            position_tolerance=0,
            size_tolerance=0,
        ),
    )
    hints = (
        RoomPlacementHint(bathroom.id, 10, 10, 20, 20),
        RoomPlacementHint(hallway_1.id, 30, 10, 10, 12),
        RoomPlacementHint(hallway_2.id, second_x, second_y, 12, 10),
    )

    execution = generate_floor_plan(
        FloorPlanSolveRequest(specification, config, hints)
    )

    assert execution.result.solved is solved
