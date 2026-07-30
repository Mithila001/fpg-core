from __future__ import annotations

from ...types import OpeningPurpose, OpeningType, RoomId, RoomType
from ..domain import OpeningDemand, PlacementOption, PreparedFloorPlan, WallKind
from ..profiles import OpeningGenerationProfile


class InteriorDoorFeature:
    feature_id = "interior_doors"

    @staticmethod
    def _allowed(left: RoomType, right: RoomType, profile: OpeningGenerationProfile) -> bool:
        pair = frozenset((left, right))
        if RoomType.ATTACHED_BATHROOM in pair:
            return pair == frozenset((RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM))
        if RoomType.HALLWAY in pair:
            return True
        return any(pair == frozenset(configured) for configured in profile.policy.allowed_room_pairs)

    def build_demands(
        self,
        prepared: PreparedFloorPlan,
        profile: OpeningGenerationProfile,
    ) -> tuple[OpeningDemand, ...]:
        minimum = round(profile.dimensions.minimum_shared_wall * prepared.scale)
        width = round(profile.dimensions.door_width * prepared.scale)
        clearance = round(profile.geometry.corner_clearance * prepared.scale)
        candidates = []
        for wall in prepared.walls:
            if wall.kind is not WallKind.SHARED or wall.length < minimum:
                continue
            left = prepared.rooms_by_id[wall.room_ids[0]]
            right = prepared.rooms_by_id[wall.room_ids[1]]
            if self._allowed(left.room_type, right.room_type, profile):
                candidates.append((wall, left, right))

        connection_types: dict[RoomId, set[RoomType]] = {}
        preferred_types = {
            RoomType.BEDROOM,
            RoomType.KITCHEN,
            RoomType.BATHROOM,
            RoomType.GARAGE,
        }
        for _, left, right in candidates:
            if left.room_type in preferred_types and right.room_type in {
                RoomType.HALLWAY,
                RoomType.LIVING_ROOM,
            }:
                connection_types.setdefault(left.id, set()).add(right.room_type)
            if right.room_type in preferred_types and left.room_type in {
                RoomType.HALLWAY,
                RoomType.LIVING_ROOM,
            }:
                connection_types.setdefault(right.id, set()).add(left.room_type)

        has_veranda = any(
            room.room_type is RoomType.VERANDA for room in prepared.rooms_by_id.values()
        )
        demands: list[OpeningDemand] = []
        for index, (wall, left, right) in enumerate(candidates):
            pair = frozenset((left.room_type, right.room_type))
            purpose = OpeningPurpose.ROOM_CONNECTION
            category = "other_interior"
            tier = "other_interior"
            if has_veranda and pair == frozenset((RoomType.LIVING_ROOM, RoomType.VERANDA)):
                purpose = OpeningPurpose.MAIN_ENTRANCE
                category = "main_entrance"
                tier = "main_entrance"
            elif pair == frozenset((RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM)):
                category = "attached_bathroom"
                tier = "attached_bathroom"
            elif pair == frozenset((RoomType.BATHROOM, RoomType.HALLWAY)):
                category = "bathroom_hallway"
                tier = "bathroom_hallway"
            else:
                ordinary_room = None
                if left.room_type is RoomType.HALLWAY:
                    ordinary_room = right
                elif right.room_type is RoomType.HALLWAY:
                    ordinary_room = left
                if ordinary_room is not None and {
                    RoomType.HALLWAY,
                    RoomType.LIVING_ROOM,
                }.issubset(connection_types.get(ordinary_room.id, set())):
                    category = "preferred_hallway"
                    tier = "preferred_hallway"

            options = (
                PlacementOption(
                    id=f"interior:{index}:{wall.id}",
                    wall_id=wall.id,
                    width=width,
                ),
            ) if wall.length >= width + 2 * clearance else ()
            demands.append(
                OpeningDemand(
                    id=f"interior:{index}:{wall.id}",
                    feature_id=self.feature_id,
                    opening_type=OpeningType.DOOR,
                    purpose=purpose,
                    room_ids=wall.room_ids,
                    options=options,
                    objective_tier=tier,
                    category=category,
                )
            )
        return tuple(demands)
