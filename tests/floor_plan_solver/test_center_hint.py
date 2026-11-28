from fpg_core.domain import (
    FloorPlanGenerationSpec,
    FloorSpec,
    RoomId,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)
from fpg_core.floor_plan_solver import (
    FloorPlanSolverConfig,
    FloorPlanSolveRequest,
    PreparationConfig,
    RoomPlacementHint,
    SeedPolicy,
    SeedSource,
    SolverConfig,
    generate_floor_plan,
)
from fpg_core.floor_plan_solver.preparation import prepare_problem


def test_center_hint_is_converted_and_tolerance_tracks_actual_center():
    room = RoomSpec(
        RoomId("room"), RoomType.BEDROOM, "Room", RoomSizeSpec(10, 20, 400, 400)
    )
    spec = FloorPlanGenerationSpec(FloorSpec(100, 100), (room,), ())
    config = FloorPlanSolverConfig(
        name="center",
        hard_constraints=(),
        soft_constraints=(),
        solver=SolverConfig(max_time_seconds=2, num_search_workers=1),
        preparation=PreparationConfig(coordinate_scale=10),
        seed=SeedPolicy(source=SeedSource.CANDIDATE_HINTS, position_tolerance=0),
    )
    hint = RoomPlacementHint(room.id, 40, 40, position_reference="center")
    request = FloorPlanSolveRequest(spec, config, (hint,))
    seed = prepare_problem(request).seed.rooms[str(room.id)]
    assert (seed.x, seed.y, seed.center_x, seed.center_y) == (300, 300, 400, 400)
    result = generate_floor_plan(request).result
    assert result.solved
    points = result.floor_plan.rooms[0].boundary.points
    assert (min(p.x for p in points) + max(p.x for p in points)) / 2 == 40
    assert (min(p.y for p in points) + max(p.y for p in points)) / 2 == 40
