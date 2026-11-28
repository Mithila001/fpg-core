from types import SimpleNamespace
from typing import Any, cast

import pytest
from ortools.sat.python import cp_model

from fpg_core.floor_plan_solver.constraints.exposure import exposure_literal


@pytest.mark.parametrize("side", ["front", "back", "left", "right"])
@pytest.mark.parametrize("minimum,expected", [(None, False), (3, True), (4, False)])
def test_continuous_exposure_is_exact(side, minimum, expected):
    model: Any = cp_model.CpModel()
    counter = iter(range(1000))

    def room(name, box):
        x, y, width, length = box
        present = model.NewBoolVar(name)
        model.Add(present == 1)
        return SimpleNamespace(
            room=SimpleNamespace(id_key=name),
            present=present,
            x=x,
            y=y,
            x_end=x + width,
            y_end=y + length,
        )

    target: Any = room("target", (5, 5, 10, 10))
    boxes = {
        "front": (8, 0, 4, 2),
        "back": (8, 18, 4, 2),
        "left": (0, 8, 2, 4),
        "right": (18, 8, 2, 4),
    }
    blocker = room("blocker", boxes[side])
    context: Any = SimpleNamespace(
        model=model,
        room_variables={"target": target, "blocker": blocker},
        exposure_cache={},
        exposure_blocker_cache={},
        new_name=lambda *args: str(next(counter)),
    )
    literal = exposure_literal(context, target, side, minimum)
    model.AddAssumption(literal if expected else literal.Not())
    assert cp_model.CpSolver().Solve(model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    model.ClearAssumptions()
    model.AddAssumption(literal.Not() if expected else literal)
    assert cp_model.CpSolver().Solve(model) == cp_model.INFEASIBLE


def _rule_context(boxes):
    from fpg_core.domain import RoomType
    from fpg_core.floor_plan_solver.preparation import CoordinateScale

    model: Any = cp_model.CpModel()
    counter = iter(range(100000))
    rooms = {}
    for name, kind, (x, y, width, length) in boxes:
        present = model.NewBoolVar(name)
        model.Add(present == 1)
        rooms[name] = SimpleNamespace(
            room=SimpleNamespace(id_key=name, room_type=RoomType(kind)),
            present=present,
            x=x,
            y=y,
            x_end=x + width,
            y_end=y + length,
        )
    return cast(
        Any,
        SimpleNamespace(
            model=model,
            room_variables=rooms,
            exposure_cache={},
            exposure_blocker_cache={},
            problem=SimpleNamespace(
                scale=CoordinateScale(1), floor=SimpleNamespace(width=50, length=50)
            ),
            new_name=lambda *args: str(next(counter)),
        ),
    )


def test_composition_counts_and_soft_penalty():
    from fpg_core.domain import RoomType
    from fpg_core.floor_plan_solver.constraints.exposure_rules import (
        SoftExteriorWallExposure,
        apply_rules,
    )

    boxes = [
        ("a", "bedroom", (0, 10, 5, 5)),
        ("b", "bedroom", (10, 10, 5, 5)),
        ("c", "bedroom", (20, 10, 5, 5)),
        ("blocker", "kitchen", (10, 0, 5, 5)),
    ]
    rule = {
        "id": "bedrooms",
        "room_types": (RoomType.BEDROOM,),
        "match": {"policy": "at_least", "count": 2},
        "requirement": {
            "all": [
                {"side": "front", "coverage": "full_wall"},
                {
                    "any": [
                        {"side": "left", "coverage": "full_wall"},
                        {"side": "right", "coverage": "full_wall"},
                    ]
                },
            ]
        },
    }
    context = _rule_context(boxes)
    apply_rules(context, {"rules": [rule]}, "exterior_wall_exposure")
    assert cp_model.CpSolver().Solve(context.model) == cp_model.OPTIMAL
    rule["match"]["count"] = 3
    context = _rule_context(boxes)
    apply_rules(context, {"rules": [rule]}, "exterior_wall_exposure")
    assert cp_model.CpSolver().Solve(context.model) == cp_model.INFEASIBLE
    context = _rule_context(boxes)
    penalty = SoftExteriorWallExposure().build_penalty(context, {"rules": [rule]})
    context.model.Minimize(penalty)
    solver = cp_model.CpSolver()
    assert solver.Solve(context.model) == cp_model.OPTIMAL
    assert solver.ObjectiveValue() == 10_000


@pytest.mark.parametrize(
    "change", ["side", "coverage", "length", "count", "mixed", "empty"]
)
def test_configuration_validation_before_model_build(change):
    from fpg_core.domain import RoomType
    from fpg_core.floor_plan_solver import HardConstraintUse
    from fpg_core.floor_plan_solver.exceptions import InvalidProfileError

    rule = {
        "id": "bedrooms",
        "room_types": (RoomType.BEDROOM,),
        "match": {"policy": "at_least", "count": 2},
        "requirement": {
            "side": "front",
            "coverage": "minimum_continuous_length",
            "minimum_length": 10,
        },
    }
    settings: dict[str, Any] = {"rules": [rule]}
    if change == "side":
        rule["requirement"]["side"] = "north"
    if change == "coverage":
        rule["requirement"]["coverage"] = "full_wall"
    if change == "length":
        rule["requirement"]["minimum_length"] = float("nan")
    if change == "count":
        rule["match"]["count"] = True
    if change == "mixed":
        settings["minimum_exposure"] = 10
    if change == "empty":
        rule["requirement"] = {"all": []}
    with pytest.raises(InvalidProfileError):
        HardConstraintUse("exterior_wall_exposure", settings)


@pytest.mark.parametrize(
    "projections,minimum,expected",
    [
        ([], 10, True),
        ([(0, 10)], 1, False),
        ([(0, 2), (4, 6), (8, 10)], 3, False),
        ([(0, 2), (4, 6), (8, 10)], 2, True),
        ([(2, 7), (4, 9)], 3, False),
        ([(10, 12)], 10, True),
    ],
)
def test_separate_and_overlapping_projections(projections, minimum, expected):
    boxes = [("target", "bedroom", (0, 10, 10, 5))]
    boxes.extend(
        (f"block{i}", "kitchen", (a, 0, b - a, 5))
        for i, (a, b) in enumerate(projections)
    )
    context = _rule_context(boxes)
    literal = exposure_literal(
        context, context.room_variables["target"], "front", minimum
    )
    context.model.AddAssumption(literal if expected else literal.Not())
    assert cp_model.CpSolver().Solve(context.model) == cp_model.OPTIMAL
    context.model.ClearAssumptions()
    context.model.AddAssumption(literal.Not() if expected else literal)
    assert cp_model.CpSolver().Solve(context.model) == cp_model.INFEASIBLE


def test_boundary_wall_and_cache():
    context = _rule_context(
        [("target", "bedroom", (0, 0, 10, 5)), ("corner", "kitchen", (10, 0, 5, 5))]
    )
    target = context.room_variables["target"]
    first = exposure_literal(context, target, "front")
    count = len(context.model.Proto().constraints)
    assert exposure_literal(context, target, "front") is first
    assert len(context.model.Proto().constraints) == count
    context.model.Add(first == 1)
    assert cp_model.CpSolver().Solve(context.model) == cp_model.OPTIMAL


def test_variable_positions_and_shared_wall_blocking():
    model: Any = cp_model.CpModel()
    counter = iter(range(10000))
    present = model.NewBoolVar("target_present")
    model.Add(present == 1)
    blocker_present = model.NewBoolVar("blocker_present")
    model.Add(blocker_present == 1)
    x = model.NewIntVar(0, 10, "target_x")
    target: Any = SimpleNamespace(
        room=SimpleNamespace(id_key="target"),
        present=present,
        x=x,
        x_end=x + 10,
        y=10,
        y_end=15,
    )
    blocker = SimpleNamespace(
        room=SimpleNamespace(id_key="blocker"),
        present=blocker_present,
        x=0,
        x_end=10,
        y=5,
        y_end=10,
    )
    context: Any = SimpleNamespace(
        model=model,
        room_variables={"target": target, "blocker": blocker},
        exposure_cache={},
        exposure_blocker_cache={},
        new_name=lambda *args: str(next(counter)),
    )
    exposed = exposure_literal(context, target, "front", 5)
    model.Add(exposed == 1)
    model.Minimize(x)
    solver = cp_model.CpSolver()
    assert solver.Solve(model) == cp_model.OPTIMAL
    assert solver.Value(x) == 5


def test_absence_and_scaled_length():
    from fpg_core.domain import RoomType
    from fpg_core.floor_plan_solver.constraints.exposure_rules import (
        SoftExteriorWallExposure,
        apply_rules,
    )
    from fpg_core.floor_plan_solver.preparation import CoordinateScale

    context = _rule_context([("living", "living_room", (0, 0, 10, 10))])
    context.problem.scale = CoordinateScale(10)
    rule = {
        "id": "kitchen",
        "room_types": [RoomType.KITCHEN],
        "match": {"policy": "at_least", "count": 1},
        "requirement": {
            "side": "front",
            "coverage": "minimum_continuous_length",
            "minimum_length": 1.01,
        },
    }
    assert SoftExteriorWallExposure().build_penalty(context, {"rules": [rule]}) == 0
    apply_rules(context, {"rules": [rule]}, "exterior_wall_exposure")
    assert cp_model.CpSolver().Solve(context.model) == cp_model.INFEASIBLE

    context = _rule_context([("bed", "bedroom", (0, 10, 10, 10))])
    context.problem.scale = CoordinateScale(10)
    rule["room_types"] = [RoomType.BEDROOM]
    apply_rules(context, {"rules": [rule]}, "exterior_wall_exposure")
    assert cp_model.CpSolver().Solve(context.model) == cp_model.INFEASIBLE


def test_projected_interval_oracle():
    import itertools

    projections = [(0, 3), (2, 6), (5, 8), (7, 10)]
    for blocks in itertools.combinations(projections, 2):
        for minimum in (1, 3, 5):
            boxes = [("target", "bedroom", (0, 10, 10, 5))]
            boxes += [
                (f"block{i}", "kitchen", (a, 0, b - a, 5))
                for i, (a, b) in enumerate(blocks)
            ]
            expected = any(
                all(b <= start or a >= start + minimum for a, b in blocks)
                for start in range(11 - minimum)
            )
            context = _rule_context(boxes)
            literal = exposure_literal(
                context, context.room_variables["target"], "front", minimum
            )
            context.model.AddAssumption(literal if expected else literal.Not())
            assert cp_model.CpSolver().Solve(context.model) == cp_model.OPTIMAL
            context.model.ClearAssumptions()
            context.model.AddAssumption(literal.Not() if expected else literal)
            assert cp_model.CpSolver().Solve(context.model) == cp_model.INFEASIBLE


def test_legacy_exposure_settings_and_keys_are_rejected():
    from fpg_core.floor_plan_solver import HardConstraintUse
    from fpg_core.floor_plan_solver.constraints.defaults import build_default_registry
    from fpg_core.floor_plan_solver.exceptions import (
        InvalidProfileError,
        UnknownConstraintError,
    )

    with pytest.raises(InvalidProfileError, match="rules"):
        HardConstraintUse("exterior_wall_exposure", {"minimum_exposure": 10})
    with pytest.raises(UnknownConstraintError, match="back_exposure"):
        build_default_registry().get_hard("back_exposure")


def test_soft_neighbour_relationships_count_once():
    from fpg_core.floor_plan_solver import SoftConstraintUse
    from fpg_core.floor_plan_solver.constraints.s_room_relations import (
        SoftRoomRelationsConstraint,
    )

    context = _rule_context(
        [
            ("source", "living_room", (0, 0, 10, 10)),
            ("touching", "bedroom", (10, 0, 10, 10)),
            ("far_a", "bedroom", (30, 0, 10, 10)),
            ("far_b", "bedroom", (30, 20, 10, 10)),
        ]
    )
    context.adjacency_cache = {}
    context.variables_for = context.room_variables.__getitem__
    context.problem.relations = [
        SimpleNamespace(
            strength="soft",
            source_id_key="source",
            target_id_keys=("far_a", "far_b"),
            match_policy="and",
        ),
        SimpleNamespace(
            strength="soft",
            source_id_key="source",
            target_id_keys=("far_a", "touching"),
            match_policy="or",
        ),
    ]
    weight = SoftConstraintUse("room_relations", 2.42).weight
    assert weight == 2.5
    assert SoftConstraintUse("room_relations", 0).weight == 0
    penalty = SoftRoomRelationsConstraint().build_penalty(
        context, {"minimum_overlap": 10}
    )
    context.model.Minimize(penalty)
    solver = cp_model.CpSolver()
    assert solver.Solve(context.model) == cp_model.OPTIMAL
    assert solver.Value(penalty) == 5_000
