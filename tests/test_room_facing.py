from types import SimpleNamespace
from ortools.sat.python import cp_model
from fpg_core.domain import RoomType
from fpg_core.floor_plan_solver.constraints.room_specific.h_garage_placement import GaragePlacementConstraint
from fpg_core.floor_plan_solver.constraints.room_specific.h_front_facing import VerandaFrontConstraint, LivingRoomFrontConstraint


def solve(kind, other_box, veranda=False, second=None):
    model = cp_model.CpModel()
    def room(name, typ, box):
        x, y, width, length = box
        present = model.NewBoolVar(name)
        model.Add(present == 1)
        return SimpleNamespace(room=SimpleNamespace(room_type=typ, id_key=name), x=x, y=y, x_end=x+width, y_end=y+length, present=present)
    target = room('target', kind, (5, 5, 5, 5))
    other = room('other', RoomType.BEDROOM, other_box)
    rooms = {'target': target, 'other': other}
    if second is not None:
        rooms['second'] = room('second', RoomType.BEDROOM, second)
    if veranda:
        rooms['veranda'] = room('veranda', RoomType.VERANDA, (15, 15, 2, 2))
    counter = iter(range(1000))
    context = SimpleNamespace(model=model, room_variables=rooms, new_name=lambda *args: str(next(counter)))
    rule = {RoomType.GARAGE: GaragePlacementConstraint, RoomType.VERANDA: VerandaFrontConstraint, RoomType.LIVING_ROOM: LivingRoomFrontConstraint}[kind]()
    rule.apply(context, {})
    return cp_model.CpSolver().Solve(model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_facing_clearance():
    assert not solve(RoomType.VERANDA, (6, 0, 2, 2))
    assert solve(RoomType.VERANDA, (0, 0, 5, 2))
    assert not solve(RoomType.LIVING_ROOM, (6, 0, 2, 2))
    assert solve(RoomType.LIVING_ROOM, (6, 0, 2, 2), veranda=True)
    assert solve(RoomType.GARAGE, (0, 0, 2, 2))
    assert not solve(RoomType.GARAGE, (0, 0, 2, 2), second=(12, 0, 2, 2))
    assert solve(RoomType.GARAGE, (0, 11, 2, 2), second=(12, 11, 2, 2))
