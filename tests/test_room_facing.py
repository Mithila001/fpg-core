from types import SimpleNamespace

from ortools.sat.python import cp_model

from fpg_core.domain import RoomType
from fpg_core.floor_plan_solver import DEFAULT_PROFILES
from fpg_core.floor_plan_solver.constraints.exposure_rules import (
    HardExteriorWallExposure,
)
from fpg_core.floor_plan_solver.constraints.room_specific.h_front_facing import (
    LivingRoomFrontConstraint,
)
from fpg_core.floor_plan_solver.preparation import CoordinateScale


def solve(kind, other_box, veranda=False, second=None):
    model = cp_model.CpModel()

    def room(name, typ, box):
        x, y, width, length = box
        present = model.NewBoolVar(name)
        model.Add(present == 1)
        return SimpleNamespace(
            room=SimpleNamespace(room_type=typ, id_key=name),
            x=x,
            y=y,
            x_end=x + width,
            y_end=y + length,
            present=present,
        )

    target = room("target", kind, (5, 5, 5, 5))
    other = room("other", RoomType.BEDROOM, other_box)
    rooms = {"target": target, "other": other}
    if second is not None:
        rooms["second"] = room("second", RoomType.BEDROOM, second)
    if veranda:
        rooms["veranda"] = room("veranda", RoomType.VERANDA, (15, 15, 2, 2))
    counter = iter(range(1000))
    context = SimpleNamespace(
        model=model,
        problem=SimpleNamespace(
            scale=CoordinateScale(1), floor=SimpleNamespace(width=50, length=50)
        ),
        room_variables=rooms,
        exposure_cache={},
        exposure_blocker_cache={},
        new_name=lambda *args: str(next(counter)),
    )
    uses = DEFAULT_PROFILES.initial.hard_constraints
    key = (
        "living_room_front"
        if kind == RoomType.LIVING_ROOM
        else "exterior_wall_exposure"
    )
    settings = next(use.settings for use in uses if use.key == key)
    if kind != RoomType.LIVING_ROOM:
        settings = {
            "rules": [
                next(rule for rule in settings["rules"] if kind in rule["room_types"])
            ]
        }
    constraint = (
        LivingRoomFrontConstraint()
        if kind == RoomType.LIVING_ROOM
        else HardExteriorWallExposure()
    )
    constraint.apply(context, settings)
    return cp_model.CpSolver().Solve(model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_facing_clearance():
    assert not solve(RoomType.VERANDA, (6, 0, 2, 2))
    assert solve(RoomType.VERANDA, (0, 0, 5, 2))
    assert not solve(RoomType.LIVING_ROOM, (6, 0, 2, 2))
    assert solve(RoomType.LIVING_ROOM, (6, 0, 2, 2), veranda=True)
    assert solve(RoomType.GARAGE, (0, 0, 2, 2))
    assert solve(RoomType.GARAGE, (0, 0, 2, 2), second=(12, 0, 2, 2))
    assert solve(RoomType.GARAGE, (0, 11, 2, 2), second=(12, 11, 2, 2))
