from ....domain import RoomType
from ..exposure_rules import apply_rules


class LivingRoomFrontConstraint:
    key = "living_room_front"

    def apply(self, context, settings):
        if not any(
            room.room.room_type == RoomType.VERANDA
            for room in context.room_variables.values()
        ):
            apply_rules(context, settings, self.key)
