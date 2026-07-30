from __future__ import annotations

from ...types import OpeningPurpose, OpeningType, RoomId
from ..domain import (
    AnalyzedWall,
    OpeningDemand,
    PlacementOption,
    PreparedFloorPlan,
    WallKind,
)
from ..profiles import OpeningGenerationProfile


class WindowFeature:
    feature_id = "windows"

    def build_demands(
        self,
        prepared: PreparedFloorPlan,
        profile: OpeningGenerationProfile,
    ) -> tuple[OpeningDemand, ...]:
        width = round(profile.dimensions.window_width * prepared.scale)
        clearance = round(profile.geometry.corner_clearance * prepared.scale)
        side_priority = {
            side: index for index, side in enumerate(profile.policy.window_side_priority)
        }
        exterior_by_room: dict[RoomId, list[AnalyzedWall]] = {}
        for wall in prepared.walls:
            if wall.kind is WallKind.EXTERIOR:
                exterior_by_room.setdefault(wall.room_ids[0], []).append(wall)

        demands: list[OpeningDemand] = []
        eligible = sorted(
            (
                room
                for room in prepared.rooms_by_id.values()
                if room.room_type in profile.policy.window_room_types
            ),
            key=lambda room: str(room.id),
        )
        for room in eligible:
            options: list[PlacementOption] = []
            for index, wall in enumerate(exterior_by_room.get(room.id, [])):
                if wall.length - 2 * clearance < width:
                    continue
                if wall.exterior_side is None:
                    continue
                options.append(
                    PlacementOption(
                        id=f"window:{room.id!s}:{index}:{wall.id}",
                        wall_id=wall.id,
                        width=width,
                        preference_rank=side_priority[wall.exterior_side.value],
                    )
                )
            demands.append(
                OpeningDemand(
                    id=f"window:{room.id!s}",
                    feature_id=self.feature_id,
                    opening_type=OpeningType.WINDOW,
                    purpose=OpeningPurpose.DAYLIGHT,
                    room_ids=(room.id,),
                    options=tuple(options),
                    objective_tier="window",
                    category="window",
                )
            )
        return tuple(demands)
