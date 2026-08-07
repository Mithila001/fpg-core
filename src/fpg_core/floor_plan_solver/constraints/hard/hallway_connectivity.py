from __future__ import annotations

from ....domain import RoomType
from ...model import ModelContext
from ..base import ConstraintSettings, require_room_types
from ..geometry import adjacency_literal


class HallwayConnectivityConstraint:
    key = "hallway_connectivity"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        hallway_types = set(
            require_room_types(
                settings.get("hallway_room_types", (RoomType.HALLWAY,)),
                "hallway_connectivity.hallway_room_types",
            )
        )
        anchor_types = set(
            require_room_types(
                settings.get("anchor_room_types", (RoomType.LIVING_ROOM,)),
                "hallway_connectivity.anchor_room_types",
            )
        )
        minimum_overlap = max(
            1,
            context.problem.scale.minimum_length(
                float(settings.get("minimum_overlap", 0.6))
            ),
        )

        all_rooms = tuple(context.room_variables.values())
        hallways = [
            room for room in all_rooms if room.room.room_type in hallway_types
        ]
        anchors = [
            room for room in all_rooms if room.room.room_type in anchor_types
        ]
        destinations = [
            room
            for room in all_rooms
            if room.room.room_type not in hallway_types | anchor_types
        ]

        for hallway in hallways:
            anchor_options = [
                adjacency_literal(context, hallway, anchor, minimum_overlap)
                for anchor in anchors
                if anchor.room.id_key != hallway.room.id_key
            ]
            destination_options = [
                adjacency_literal(context, hallway, destination, minimum_overlap)
                for destination in destinations
                if destination.room.id_key != hallway.room.id_key
            ]

            if anchor_options:
                context.model.AddBoolOr(
                    anchor_options + [hallway.present.Not()]
                )
            else:
                context.model.Add(hallway.present == 0)

            if destination_options:
                context.model.AddBoolOr(
                    destination_options + [hallway.present.Not()]
                )
            else:
                context.model.Add(hallway.present == 0)
