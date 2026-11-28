from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING, Any

from ...domain import OpeningPurpose, OpeningType, RoomId, RoomType
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

        # ponytail: quadratic candidate-pair scan; group by wall line if large plans make it costly.
        for left, right in combinations(context.all_variables, 2):
            if left.wall.id == right.wall.id or left.wall.orientation is not right.wall.orientation or left.wall.fixed_coordinate != right.wall.fixed_coordinate:
                continue
            if OpeningType.WINDOW not in {left.demand.opening_type, right.demand.opening_type}:
                continue
            if left.wall.start > right.wall.start:
                left, right = right, left
            context.model.Add(left.wall.start + left.end + context.window_spacing <= right.wall.start + right.start).OnlyEnforceIf([left.selected, right.selected])

        main = [
            item
            for item in context.all_variables
            if item.demand.purpose is OpeningPurpose.MAIN_ENTRANCE
        ]
        if main:
            context.model.Add(sum(item.selected for item in main) <= 1)


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
        normal_incident: dict[RoomId, list[Any]] = {}
        for demand in context.demands:
            if demand.opening_type is not OpeningType.DOOR or len(demand.room_ids) != 2:
                continue
            selected = demand_selected[demand.id]
            for room_id in demand.room_ids:
                room_type = context.prepared.rooms_by_id[room_id].room_type
                other_id = next(value for value in demand.room_ids if value != room_id)
                other_type = context.prepared.rooms_by_id[other_id].room_type
                special = (room_type, other_type) in {
                    (RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM),
                    (RoomType.KITCHEN, RoomType.DINING_ROOM),
                }
                if not special:
                    normal_incident.setdefault(room_id, []).append(selected)
                room_incident.setdefault(room_id, []).append(selected)

        caps = context.config.policy.cap_by_room_type
        for room_id, terms in room_incident.items():
            room = context.prepared.rooms_by_id[room_id]
            allowance = sum(
                demand_selected[demand.id] for demand in context.demands
                if len(demand.room_ids) == 2 and room_id in demand.room_ids
                and (room.room_type, context.prepared.rooms_by_id[next(value for value in demand.room_ids if value != room_id)].room_type)
                in {(RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM), (RoomType.KITCHEN, RoomType.DINING_ROOM)}
            )
            context.model.Add(allowance <= 1)
            context.model.Add(sum(terms) <= caps.get(room.room_type, 10) + allowance)
        for room_id, terms in normal_incident.items():
            cap = dict(context.config.policy.normal_connection_caps).get(context.prepared.rooms_by_id[room_id].room_type)
            if cap is not None:
                context.model.Add(sum(terms) <= cap)


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

        secondary_variables = [
            item for item in context.all_variables
            if item.demand.purpose is OpeningPurpose.SECONDARY_ENTRANCE
        ]
        context.model.Add(sum(item.selected for item in secondary_variables) == 1)

        required_types = set(context.config.policy.required_access_room_types)
        required_room_ids = {
            room_id
            for room_id, room in rooms.items()
            if room.room_type in required_types
        }
        required_count = len(required_room_ids) + 1

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
            consumption = (1 if room_id in required_room_ids else 0) + sum(
                item.selected for item in secondary_variables if item.wall.room_ids[0] == room_id
            )
            context.model.Add(
                sum(incoming[room_id]) - sum(outgoing[room_id]) == consumption
            )
