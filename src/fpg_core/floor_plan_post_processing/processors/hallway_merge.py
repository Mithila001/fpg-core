from __future__ import annotations

from dataclasses import replace

from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from ...types import RoomType
from ..config import HallwayMergeConfig
from ..contracts import FloorPlanProcessor, ProcessorOutcome, ProcessorStatus
from ..exceptions import ProcessorError
from ..geometry import from_shapely, to_shapely


class HallwayMergeProcessor(FloorPlanProcessor):
    processor_id = "hallway_merge"
    description = "Merge hallway components sharing sufficient wall contact."
    config_type = HallwayMergeConfig

    def is_applicable(self, floor_plan, context, config):
        count = sum(room.room_type is RoomType.HALLWAY for room in floor_plan.rooms)
        return count > 1, "fewer than two hallways exist"

    def process(self, floor_plan, context, config):
        assert isinstance(config, HallwayMergeConfig)
        if config.minimum_shared_wall < 0:
            raise ProcessorError("minimum shared-wall length cannot be negative")
        hallways = sorted(
            (room for room in floor_plan.rooms if room.room_type is RoomType.HALLWAY),
            key=lambda room: str(room.id),
        )
        shapes = {room.id: to_shapely(room.boundary) for room in hallways}
        parent = {room.id: room.id for room in hallways}

        def find(item):
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        def union(left, right):
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[max((left_root, right_root), key=str)] = min(
                    (left_root, right_root), key=str
                )

        tolerance = context.numeric.tolerance
        for index, left in enumerate(hallways):
            for right in hallways[index + 1 :]:
                shared = shapes[left.id].boundary.intersection(
                    shapes[right.id].boundary
                )
                if shared.length + tolerance >= config.minimum_shared_wall:
                    union(left.id, right.id)

        groups = {}
        for room in hallways:
            groups.setdefault(find(room.id), []).append(room)
        merge_groups = [rooms for rooms in groups.values() if len(rooms) > 1]
        if not merge_groups:
            return ProcessorOutcome(
                ProcessorStatus.NO_CHANGE, "no hallway pair met the threshold"
            )

        removed = set()
        redirects = {}
        affected = []
        for rooms in sorted(
            merge_groups, key=lambda group: str(min((r.id for r in group), key=str))
        ):
            survivor = min(rooms, key=lambda room: str(room.id))
            merged = unary_union([shapes[room.id] for room in rooms])
            if not isinstance(merged, ShapelyPolygon):
                raise ProcessorError("hallway merge produced disconnected geometry")
            source_ids = tuple(sorted((room.id for room in rooms), key=str))
            survivor.boundary = from_shapely(merged, tolerance)
            survivor.metadata = replace(survivor.metadata, source_room_ids=source_ids)
            for room in rooms:
                if room.id != survivor.id:
                    removed.add(room.id)
                    redirects[room.id] = survivor.id
            affected.append(survivor.id)

        floor_plan.rooms[:] = [
            room for room in floor_plan.rooms if room.id not in removed
        ]
        for room in floor_plan.rooms:
            if room.parent_room_id in redirects:
                room.parent_room_id = redirects[room.parent_room_id]
        for source, target in list(floor_plan.identity_redirects.items()):
            if target in redirects:
                floor_plan.identity_redirects[source] = redirects[target]
        floor_plan.identity_redirects.update(redirects)
        return ProcessorOutcome(
            ProcessorStatus.CHANGED,
            "merged hallway components",
            tuple(affected),
            redirects,
            {"rooms_removed": len(removed), "components_merged": len(merge_groups)},
        )
