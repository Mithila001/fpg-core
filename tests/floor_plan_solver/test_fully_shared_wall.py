from __future__ import annotations

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

KEY = "fully_shared_wall"
BEDROOM = (RoomType.BEDROOM, 20, 20, 20, 20)
FRONT = (RoomType.HALLWAY, 20, 10, 20, 10)
RIGHT = (RoomType.KITCHEN, 40, 20, 10, 20)
BACK = (RoomType.DINING_ROOM, 20, 40, 20, 10)
LEFT = (RoomType.BATHROOM, 10, 20, 10, 20)
VERANDA = (RoomType.VERANDA, 50, 50, 10, 10)


def rule(count=1, arrangement="adjacent", **settings):
    return {
        "room_types": [RoomType.BEDROOM],
        "minimum_shared_sides": count,
        "arrangement": arrangement,
        **settings,
    }


def assert_layout(neighbors, rules, expected=True, scale=1):
    rooms = []
    hints = []
    for index, (room_type, x, y, width, length) in enumerate((BEDROOM, *neighbors)):
        room_id = RoomId(f"room_{index}")
        rooms.append(RoomSpec(room_id, room_type, room_id, RoomSizeSpec(1, 80, 1, 6400)))
        hints.append(RoomPlacementHint(room_id, x, y, width, length))
    spec = FloorPlanGenerationSpec(floor=FloorSpec(80, 80), rooms=tuple(rooms), room_relations=())
    config = FloorPlanSolverConfig(
        name=KEY,
        hard_constraints=(HardConstraintUse(KEY, {"rules": rules}),),
        soft_constraints=(),
        solver=SolverConfig(max_time_seconds=2, num_search_workers=1, random_seed=0),
        preparation=PreparationConfig(coordinate_scale=scale),
        seed=SeedPolicy(
            source=SeedSource.CANDIDATE_HINTS,
            require_source=True,
            position_tolerance=0,
            size_tolerance=0,
        ),
    )
    execution = generate_floor_plan(
        FloorPlanSolveRequest(spec, config, tuple(hints)), mode=ExecutionMode.DEBUG
    )
    assert execution.details is not None
    assert KEY in execution.details.applied_hard_constraints
    assert execution.result.status is (SolverStatus.OPTIMAL if expected else SolverStatus.INFEASIBLE)


@pytest.mark.parametrize(
    "neighbors, expected",
    [
        ((FRONT,), True),
        (((RoomType.KITCHEN, 20, 10, 7, 10), (RoomType.BATHROOM, 27, 10, 13, 10)), True),
        (((RoomType.KITCHEN, 20, 10, 7, 10), (RoomType.BATHROOM, 28, 10, 12, 10)), False),
        (((RoomType.KITCHEN, 10, 10, 20, 10),), False),
        (((RoomType.KITCHEN, 10, 10, 10, 10),), False),
        (((RoomType.KITCHEN, 20, 9, 20, 10),), False),
    ],
    ids=["single", "collective", "gap", "clipped", "corner", "separated"],
)
def test_shared_wall_geometry(neighbors, expected):
    assert_layout(neighbors, [rule()], expected)


@pytest.mark.parametrize("arrangement", ["adjacent", "any"])
@pytest.mark.parametrize("count", range(5))
def test_minimum_count(count, arrangement):
    walls = (FRONT, RIGHT, BACK, LEFT)
    assert_layout(walls[:count], [rule(count, arrangement)])
    if count:
        assert_layout(walls[: count - 1], [rule(count, arrangement)], False)


def test_opposite_sides_and_extra_coverage():
    assert_layout((FRONT, BACK), [rule(2)], False)
    assert_layout((FRONT, BACK), [rule(2, "any")])
    assert_layout((FRONT, LEFT), [rule(2)])  # Wrap around the front-left corner.
    assert_layout((FRONT, RIGHT, BACK, LEFT), [rule(2)])


@pytest.mark.parametrize(
    "front_gap,right_gap,expected",
    [(0, 0, True), (10, 0, True), (3, 6, True), (4, 6, True), (6, 6, False), (10, 10, False)],
)
def test_combined_tolerance(front_gap, right_gap, expected):
    neighbors = (
        (RoomType.HALLWAY, 20 + front_gap, 10, 20 - front_gap, 10),
        (RoomType.KITCHEN, 40, 20 + right_gap, 10, 20 - right_gap),
    )
    assert_layout(neighbors, [rule(2, uncovered_length_tolerance=10)], expected)


def test_multiple_gaps_and_missing_contact():
    neighbors = ((RoomType.KITCHEN, 22, 10, 6, 10), (RoomType.BATHROOM, 31, 10, 7, 10))
    assert_layout(neighbors, [rule(uncovered_length_tolerance=7)])
    assert_layout(neighbors, [rule(uncovered_length_tolerance=6)], False)
    assert_layout((FRONT,), [rule(2, uncovered_length_tolerance=1000)], False)


@pytest.mark.parametrize("tolerance,expected", [(0.19999999999, False), (0.2, True), (0.29, True)])
def test_tolerance_uses_coordinate_scale_and_rounds_down(tolerance, expected):
    neighbors = ((RoomType.HALLWAY, 20, 10, 19.9, 10), (RoomType.KITCHEN, 40, 20, 10, 19.9))
    assert_layout(neighbors, [rule(2, uncovered_length_tolerance=tolerance)], expected, scale=10)


@pytest.mark.parametrize("exists", [False, True])
@pytest.mark.parametrize("include_veranda", [False, True])
def test_rule_condition_uses_room_type_existence(exists, include_veranda):
    neighbors = (FRONT, VERANDA) if include_veranda else (FRONT,)
    rules = [rule(1), rule(2, when={"room_type": RoomType.VERANDA, "exists": exists})]
    assert_layout(neighbors, rules, expected=exists != include_veranda)


def test_rules_apply_to_every_matching_room():
    second = (RoomType.BEDROOM, 60, 60, 10, 10)
    other_neighbor = (RoomType.GARAGE, 60, 70, 10, 10)
    assert_layout((FRONT, second), [rule()], False)
    assert_layout((FRONT, second, other_neighbor), [rule()])


@pytest.mark.parametrize("settings", [{}, {"rules": []}, {"rules": {}}, {"rules": [rule()], "extra": 1}])
def test_invalid_settings(settings):
    with pytest.raises(InvalidProfileError, match=KEY):
        HardConstraintUse(KEY, settings)


@pytest.mark.parametrize(
    "overrides",
    [
        {"room_types": []}, {"room_types": "bedroom"}, {"room_types": ["bedroom"]},
        {"room_types": {RoomType.BEDROOM: None}},
        {"minimum_shared_sides": -1}, {"minimum_shared_sides": 5},
        {"minimum_shared_sides": 1.0}, {"minimum_shared_sides": True},
        {"arrangement": "opposite"},
        {"uncovered_length_tolerance": -1}, {"uncovered_length_tolerance": "1"},
        {"uncovered_length_tolerance": False}, {"uncovered_length_tolerance": float("nan")},
        {"uncovered_length_tolerance": float("inf")},
        {"when": None}, {"when": {"room_type": RoomType.GARAGE}},
        {"when": {"room_type": "invalid", "exists": False}},
        {"when": {"room_type": RoomType.GARAGE, "exists": 1}},
        {"when": {"room_type": RoomType.GARAGE, "exists": True, "extra": 1}},
        {"extra": 1},
    ],
)
def test_invalid_rule_identifies_index(overrides):
    with pytest.raises(InvalidProfileError, match=r"fully_shared_wall\.rules\[1\]"):
        HardConstraintUse(KEY, {"rules": [rule(), rule() | overrides]})
