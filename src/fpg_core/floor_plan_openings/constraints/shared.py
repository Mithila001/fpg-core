from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING, Any

from ...domain import OpeningPurpose, OpeningType, RoomId, RoomType

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
        attached_by_room: dict[RoomId, list[Any]] = {}
        for demand in context.demands:
            if demand.opening_type is not OpeningType.DOOR or len(demand.room_ids) != 2:
                continue
            selected = demand_selected[demand.id]
            for room_id in demand.room_ids:
                room_incident.setdefault(room_id, []).append(selected)
            if demand.category == "attached_bathroom":
                for room_id in demand.room_ids:
                    attached_by_room.setdefault(room_id, []).append(selected)

        caps = context.profile.policy.cap_by_room_type
        for room_id, terms in room_incident.items():
            room = context.prepared.rooms_by_id[room_id]
            if room.room_type is RoomType.BEDROOM:
                attached = sum(attached_by_room.get(room_id, ()))
                context.model.Add(sum(terms) <= 1 + attached)
                context.model.Add(attached <= 1)
            else:
                context.model.Add(sum(terms) <= caps.get(room.room_type, 10))
            if room.room_type is RoomType.ATTACHED_BATHROOM:
                context.model.Add(sum(attached_by_room.get(room_id, ())) <= 1)
