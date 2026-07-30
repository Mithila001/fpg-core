from __future__ import annotations

from ...types import OpeningPurpose, OpeningType, RoomType
from ..domain import OpeningDemand, PlacementOption, PreparedFloorPlan, WallKind
from ..profiles import OpeningGenerationProfile


class ExteriorDoorFeature:
    feature_id = "exterior_doors"

    def build_demands(
        self,
        prepared: PreparedFloorPlan,
        profile: OpeningGenerationProfile,
    ) -> tuple[OpeningDemand, ...]:
        clearance = round(profile.geometry.corner_clearance * prepared.scale)
        preferred_width = round(profile.dimensions.door_width * prepared.scale)
        exterior = [wall for wall in prepared.walls if wall.kind is WallKind.EXTERIOR]
        demands: list[OpeningDemand] = []

        has_veranda = any(
            room.room_type is RoomType.VERANDA for room in prepared.rooms_by_id.values()
        )
        if has_veranda:
            minimum = round(profile.dimensions.minimum_shared_wall * prepared.scale)
            has_veranda_connection = any(
                wall.kind is WallKind.SHARED
                and wall.length >= minimum
                and {
                    prepared.rooms_by_id[room_id].room_type for room_id in wall.room_ids
                }
                == {RoomType.LIVING_ROOM, RoomType.VERANDA}
                for wall in prepared.walls
            )
            if not has_veranda_connection:
                demands.append(
                    OpeningDemand(
                        id="main_entrance",
                        feature_id=self.feature_id,
                        opening_type=OpeningType.DOOR,
                        purpose=OpeningPurpose.MAIN_ENTRANCE,
                        room_ids=(),
                        options=(),
                        objective_tier="main_entrance",
                        category="main_entrance",
                    )
                )
        if not has_veranda and prepared.rooms_by_id:
            side_priority = {
                side: index for index, side in enumerate(profile.policy.main_side_priority)
            }
            options: list[PlacementOption] = []
            for index, wall in enumerate(exterior):
                usable = wall.length - 2 * clearance
                if usable <= 0:
                    continue
                if wall.exterior_side is None:
                    continue
                room = prepared.rooms_by_id[wall.room_ids[0]]
                room_rank = 0 if room.room_type is RoomType.LIVING_ROOM else 1
                side_rank = side_priority[wall.exterior_side.value]
                width = min(preferred_width, usable)
                options.append(
                    PlacementOption(
                        id=f"main:{index}:{wall.id}",
                        wall_id=wall.id,
                        width=width,
                        preference_rank=room_rank * 4 + side_rank,
                        undersized=width < preferred_width,
                    )
                )
            demands.append(
                OpeningDemand(
                    id="main_entrance",
                    feature_id=self.feature_id,
                    opening_type=OpeningType.DOOR,
                    purpose=OpeningPurpose.MAIN_ENTRANCE,
                    room_ids=(),
                    options=tuple(options),
                    objective_tier="main_entrance",
                    category="main_entrance",
                )
            )

        eligible_rooms = {
            room.id
            for room in prepared.rooms_by_id.values()
            if room.room_type in profile.policy.secondary_room_priority
        }
        if eligible_rooms:
            room_priority = {
                room_type: index
                for index, room_type in enumerate(profile.policy.secondary_room_priority)
            }
            side_priority = {
                side: index
                for index, side in enumerate(profile.policy.secondary_side_priority)
            }
            options = []
            for index, wall in enumerate(exterior):
                if wall.room_ids[0] not in eligible_rooms:
                    continue
                usable = wall.length - 2 * clearance
                if usable <= 0:
                    continue
                if wall.exterior_side is None:
                    continue
                room = prepared.rooms_by_id[wall.room_ids[0]]
                width = min(preferred_width, usable)
                options.append(
                    PlacementOption(
                        id=f"secondary:{index}:{wall.id}",
                        wall_id=wall.id,
                        width=width,
                        preference_rank=(
                            room_priority[room.room_type] * 4
                            + side_priority[wall.exterior_side.value]
                        ),
                        undersized=width < preferred_width,
                    )
                )
            demands.append(
                OpeningDemand(
                    id="secondary_entrance",
                    feature_id=self.feature_id,
                    opening_type=OpeningType.DOOR,
                    purpose=OpeningPurpose.SECONDARY_ENTRANCE,
                    room_ids=(),
                    options=tuple(options),
                    objective_tier="secondary_entrance",
                    category="secondary_entrance",
                )
            )
        return tuple(demands)
