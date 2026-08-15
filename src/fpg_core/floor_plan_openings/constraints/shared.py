from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING, Any

from ...domain import OpeningPurpose, OpeningType, RoomId
from ..domain import WallKind

if TYPE_CHECKING:
    from ..model import OpeningModelContext


class SharedPlacementConstraint:
    constraint_id = "shared_placement"

    def apply(self, context: OpeningModelContext) -> None:
        for variables in context.variables_by_demand.values():
            context.model.Add(sum(item.selected for item in variables) <= 1)

        for wall_id, variables in context.variables_by_wall.items():
            context.model.AddNoOverlap([item.interval for item in variables])
            for left, right in combinations(variables, 2):
                if OpeningType.WINDOW not in {
                    left.demand.opening_type,
                    right.demand.opening_type,
                }:
                    continue
                order = context.model.NewBoolVar(
                    context.new_name("spacing_order", wall_id)
                )
                gap = context.window_spacing
                context.model.Add(left.end + gap <= right.start).OnlyEnforceIf(
                    [left.selected, right.selected, order]
                )
                context.model.Add(right.end + gap <= left.start).OnlyEnforceIf(
                    [left.selected, right.selected, order.Not()]
                )

        main = [
            item
            for item in context.all_variables
            if item.demand.purpose is OpeningPurpose.MAIN_ENTRANCE
        ]
        if main:
            context.model.Add(sum(item.selected for item in main) <= 1)

        secondary = [
            item
            for item in context.all_variables
            if item.demand.purpose is OpeningPurpose.SECONDARY_ENTRANCE
        ]
        secondary_walls = {item.wall.id for item in secondary}
        if len(secondary_walls) > 1:
            for secondary_item in secondary:
                for main_item in main:
                    if secondary_item.wall.id == main_item.wall.id:
                        context.model.Add(
                            secondary_item.selected + main_item.selected <= 1
                        )


class RoomDoorLimitConstraint:
    constraint_id = "room_door_limits"

    def apply(self, context: OpeningModelContext) -> None:
        demand_selected = {
            demand.id: sum(
                item.selected for item in context.variables_by_demand.get(demand.id, ())
            )
            for demand in context.demands
        }
        room_incident: dict[RoomId, list[Any]] = {}
        for demand in context.demands:
            if demand.opening_type is not OpeningType.DOOR or len(demand.room_ids) != 2:
                continue
            selected = demand_selected[demand.id]
            for room_id in demand.room_ids:
                room_incident.setdefault(room_id, []).append(selected)

        caps = context.config.policy.cap_by_room_type
        for room_id, terms in room_incident.items():
            room = context.prepared.rooms_by_id[room_id]
            context.model.Add(sum(terms) <= caps.get(room.room_type, 10))


class RequiredRoomAccessConstraint:
    """Require a main entrance and graph connectivity for configured room types.

    A single-commodity flow originates from the selected main entrance and must
    deliver one unit to every room whose type is listed in
    `required_access_room_types`. Selected shared-wall doors are the only edges
    that can carry that flow, so a room cannot satisfy the rule with an isolated
    or purely local door connection.
    """

    constraint_id = "required_room_access"

    def apply(self, context: OpeningModelContext) -> None:
        rooms = context.prepared.rooms_by_id
        if not rooms:
            return

        main_variables = [
            item
            for item in context.all_variables
            if item.demand.opening_type is OpeningType.DOOR
            and item.demand.purpose is OpeningPurpose.MAIN_ENTRANCE
        ]
        context.model.Add(sum(item.selected for item in main_variables) == 1)

        required_types = set(context.config.policy.required_access_room_types)
        required_room_ids = {
            room_id
            for room_id, room in rooms.items()
            if room.room_type in required_types
        }
        required_count = len(required_room_ids)
        if required_count == 0:
            return

        incoming: dict[RoomId, list[Any]] = {room_id: [] for room_id in rooms}
        outgoing: dict[RoomId, list[Any]] = {room_id: [] for room_id in rooms}

        for item in context.all_variables:
            if item.demand.opening_type is not OpeningType.DOOR:
                continue

            if item.wall.kind is WallKind.SHARED and len(item.wall.room_ids) == 2:
                left_id, right_id = item.wall.room_ids
                left_to_right = context.model.NewIntVar(
                    0,
                    required_count,
                    context.new_name("access_flow", left_id, right_id, item.option.id),
                )
                right_to_left = context.model.NewIntVar(
                    0,
                    required_count,
                    context.new_name("access_flow", right_id, left_id, item.option.id),
                )
                context.model.Add(
                    left_to_right + right_to_left
                    <= required_count * item.selected
                )
                outgoing[left_id].append(left_to_right)
                incoming[right_id].append(left_to_right)
                outgoing[right_id].append(right_to_left)
                incoming[left_id].append(right_to_left)

            if item.demand.purpose is OpeningPurpose.MAIN_ENTRANCE:
                root_room_ids = (
                    item.wall.room_ids
                    if item.wall.room_ids
                    else item.demand.room_ids
                )
                for room_id in root_room_ids:
                    if room_id not in rooms:
                        continue
                    source_flow = context.model.NewIntVar(
                        0,
                        required_count,
                        context.new_name("entry_flow", room_id, item.option.id),
                    )
                    context.model.Add(
                        source_flow <= required_count * item.selected
                    )
                    incoming[room_id].append(source_flow)

        for room_id in rooms:
            consumption = 1 if room_id in required_room_ids else 0
            context.model.Add(
                sum(incoming[room_id]) - sum(outgoing[room_id]) == consumption
            )
