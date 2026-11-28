from typing import Any, cast

from fpg_core.domain.room_size_preferences import DEFAULT_ROOM_SIZE_PAIRS
from fpg_core.floor_plan_scoring import RoomAreaAggregation, create_default_config
from fpg_core.floor_plan_solver.constraints.s_room_size_relations import (
    DEFAULT_CROSS_TYPE_RULES,
    DEFAULT_SAME_TYPE_RULES,
)


def test_default_solver_and_scoring_relationships_match():
    scoring = cast(
        Any,
        next(
            rule.settings
            for rule in create_default_config().evaluators
            if rule.key == "room_size_consistency"
        ),
    )
    assert len(scoring.relation_rules) == len(DEFAULT_CROSS_TYPE_RULES) == 12
    assert {
        (rule.compared_type, rule.reference_type) for rule in scoring.relation_rules
    } == set(DEFAULT_ROOM_SIZE_PAIRS)
    for solver, score in zip(
        DEFAULT_CROSS_TYPE_RULES, scoring.relation_rules, strict=True
    ):
        assert (
            solver["compared_type"],
            solver["reference_type"],
            solver["max_ratio"],
        ) == (score.compared_type, score.reference_type, score.max_ratio)
        assert score.reference_aggregation == RoomAreaAggregation.MIN
        assert score.compared_aggregation == RoomAreaAggregation.MAX

    assert [
        (r["room_type"], r["maximum_spread_ratio"]) for r in DEFAULT_SAME_TYPE_RULES
    ] == [(r.room_type, r.maximum_spread_ratio) for r in scoring.consistency_rules]


def test_proportionality_penalties_and_validation():
    from types import SimpleNamespace

    import pytest
    from ortools.sat.python import cp_model

    from fpg_core.domain import RoomType
    from fpg_core.floor_plan_solver.constraints.s_room_size_relations import (
        RoomSizeRelationsConstraint,
    )
    from fpg_core.floor_plan_solver.exceptions import InvalidProfileError

    def evaluate(areas, settings):
        model: Any = cp_model.CpModel()
        rooms = {
            index: SimpleNamespace(
                room=SimpleNamespace(room_type=room_type, max_area=100),
                area=model.NewConstant(area),
            )
            for index, (room_type, area) in enumerate(areas)
        }
        counter = iter(range(1000))
        context: Any = SimpleNamespace(
            model=model,
            room_variables=rooms,
            new_name=lambda name: f"{name}_{next(counter)}",
        )
        penalty = RoomSizeRelationsConstraint().build_penalty(context, settings)
        solver = cp_model.CpSolver()
        assert solver.Solve(model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        return solver.Value(penalty) if not isinstance(penalty, int) else penalty

    settings = {
        "cross_type_rules": [
            {
                "compared_type": RoomType.KITCHEN,
                "reference_type": RoomType.LIVING_ROOM,
                "min_ratio": 0.4,
                "max_ratio": 0.8,
            }
        ],
        "same_type_rules": [
            {"room_type": RoomType.BEDROOM, "maximum_spread_ratio": 0.25}
        ],
    }
    rooms = [
        (RoomType.KITCHEN, 50),
        (RoomType.LIVING_ROOM, 100),
        (RoomType.BEDROOM, 40),
        (RoomType.BEDROOM, 50),
    ]
    assert evaluate(rooms, settings) == 0
    assert evaluate(rooms[:-1] + [(RoomType.BEDROOM, 70)], settings) > 0
    assert evaluate([(RoomType.KITCHEN, 50)], settings) == 0
    with pytest.raises(InvalidProfileError):
        evaluate(rooms, {"rules": []})
    with pytest.raises(InvalidProfileError):
        evaluate(rooms, {"cross_type_rules": settings["cross_type_rules"] * 2})
