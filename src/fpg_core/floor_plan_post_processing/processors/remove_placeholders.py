from __future__ import annotations

from ...domain import RoomRole
from ..config import PlaceholderRemovalConfig
from ..contracts import FloorPlanProcessor, ProcessorOutcome, ProcessorStatus


class RemovePlaceholderRoomsProcessor(FloorPlanProcessor):
    processor_id = "remove_placeholder_rooms"
    description = "Remove solver-only placeholder rooms and stale references."
    config_type = PlaceholderRemovalConfig

    def is_applicable(self, floor_plan, context, config):
        present = any(
            room.role is RoomRole.SOLVER_PLACEHOLDER for room in floor_plan.rooms
        )
        return present, "no placeholder rooms exist"

    def process(self, floor_plan, context, config):
        removed = {
            room.id
            for room in floor_plan.rooms
            if room.role is RoomRole.SOLVER_PLACEHOLDER
        }
        floor_plan.rooms[:] = [
            room for room in floor_plan.rooms if room.id not in removed
        ]
        for room in floor_plan.rooms:
            if room.parent_room_id in removed:
                room.parent_room_id = None
        floor_plan.identity_redirects = {
            source: target
            for source, target in floor_plan.identity_redirects.items()
            if source not in removed and target not in removed
        }
        return ProcessorOutcome(
            ProcessorStatus.CHANGED,
            "removed solver placeholder rooms",
            tuple(sorted(removed, key=str)),
            metrics={"rooms_removed": len(removed)},
        )
