import pytest

from fpg_core.domain import (
    ExecutionMode,
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
    HardConstraintUse,
    PreparationConfig,
    RoomPlacementHint,
    SeedPolicy,
    SeedSource,
    SolverConfig,
    SolverStatus,
    generate_floor_plan,
)
from fpg_core.floor_plan_solver.exceptions import InvalidProfileError


def solve(types, ys, maximum, *, scale=1, when=None):
    rooms = tuple(
        RoomSpec(RoomId(str(i)), t, str(i), RoomSizeSpec(1, 80, 1, 6400))
        for i, t in enumerate(types)
    )
    hints = tuple(
        RoomPlacementHint(r.id, i * 10, y, 5, 5)
        for i, (r, y) in enumerate(zip(rooms, ys, strict=True))
    )
    rule = {"room_types": [types[1]], "maximum_setback": maximum}
    if when is not None:
        rule["when"] = when
    config = FloorPlanSolverConfig(
        name="test",
        hard_constraints=(HardConstraintUse("front_wall_setback", {"rules": [rule]}),),
        soft_constraints=(),
        solver=SolverConfig(max_time_seconds=2, num_search_workers=1),
        preparation=PreparationConfig(coordinate_scale=scale),
        seed=SeedPolicy(
            source=SeedSource.CANDIDATE_HINTS,
            require_source=True,
            position_tolerance=0,
            size_tolerance=0,
        ),
    )
    result = generate_floor_plan(
        FloorPlanSolveRequest(
            FloorPlanGenerationSpec(FloorSpec(80, 80), rooms, ()), config, hints
        ),
        mode=ExecutionMode.DEBUG,
    )
    assert "front_wall_setback" in result.details.applied_hard_constraints
    return result.result.status


@pytest.mark.parametrize(
    "room_type", [RoomType.GARAGE, RoomType.VERANDA, RoomType.LIVING_ROOM]
)
@pytest.mark.parametrize(
    "offset,maximum,expected", [(0, 0, True), (10, 10, True), (11, 10, False)]
)
def test_relative_front(room_type, offset, maximum, expected):
    status = solve(
        [RoomType.BEDROOM, room_type, room_type], [20, 20 + offset, 20], maximum
    )
    assert (status is SolverStatus.OPTIMAL) == expected


def test_all_matching_rooms_and_condition():
    types = [
        RoomType.BEDROOM,
        RoomType.LIVING_ROOM,
        RoomType.LIVING_ROOM,
        RoomType.VERANDA,
    ]
    condition = {"room_type": RoomType.VERANDA, "exists": False}
    assert solve(types, [20, 20, 31, 20], 10) is SolverStatus.INFEASIBLE
    assert solve(types, [20, 20, 31, 20], 10, when=condition) is SolverStatus.OPTIMAL


def test_fractional_grid_rounds_down():
    types = [RoomType.BEDROOM, RoomType.GARAGE]
    assert solve(types, [20, 20.5], 0.59, scale=10) is SolverStatus.OPTIMAL
    assert solve(types, [20, 20.6], 0.59, scale=10) is SolverStatus.INFEASIBLE


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1"])
def test_invalid_maximum(value):
    with pytest.raises(InvalidProfileError):
        HardConstraintUse(
            "front_wall_setback",
            {"rules": [{"room_types": [RoomType.GARAGE], "maximum_setback": value}]},
        )


def test_post_processing_rechecks_when_unrelated_room_moves_forward():
    from types import SimpleNamespace

    from shapely.geometry import box

    from fpg_core.domain import RoomRole
    from fpg_core.floor_plan_post_processing.protection import candidate_protection

    ids = [RoomId("garage"), RoomId("bedroom")]
    types = [RoomType.GARAGE, RoomType.BEDROOM]
    rooms = [
        SimpleNamespace(id=i, room_type=t, role=RoomRole.STANDARD)
        for i, t in zip(ids, types, strict=True)
    ]
    specs = tuple(
        RoomSpec(i, t, str(i), RoomSizeSpec(1, 80, 1, 6400))
        for i, t in zip(ids, types, strict=True)
    )
    rule = HardConstraintUse(
        "front_wall_setback",
        {"rules": [{"room_types": [RoomType.GARAGE], "maximum_setback": 5}]},
    )
    config = FloorPlanSolverConfig(
        name="test",
        hard_constraints=(rule,),
        soft_constraints=(),
        preparation=PreparationConfig(coordinate_scale=10),
    )
    context = SimpleNamespace(
        specification=FloorPlanGenerationSpec(FloorSpec(80, 80), specs, ()),
        solver_config=config,
        numeric=SimpleNamespace(tolerance=1e-6),
    )
    before = {ids[0]: box(0, 25, 5, 30), ids[1]: box(10, 20, 15, 25)}
    after = dict(before)
    after[ids[1]] = box(10, 19, 15, 25)
    assert (
        candidate_protection(
            SimpleNamespace(rooms=rooms),
            context,
            before,
            after,
            ids[1],
            area_excess=0,
            width_excess=0,
        )
        == "front wall setback"
    )
    after[ids[1]] = box(10, 20, 15, 26)
    assert (
        candidate_protection(
            SimpleNamespace(rooms=rooms),
            context,
            before,
            after,
            ids[1],
            area_excess=0,
            width_excess=0,
        )
        is None
    )
