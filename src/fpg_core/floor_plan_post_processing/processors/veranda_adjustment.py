from __future__ import annotations

from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry import box
from shapely.ops import unary_union

from ...domain import RoomRole, RoomType
from ..config import VerandaAdjustmentConfig
from ..contracts import FloorPlanProcessor, ProcessorOutcome, ProcessorStatus
from ..geometry import from_shapely, to_shapely


class VerandaAdjustmentProcessor(FloorPlanProcessor):
    processor_id = "veranda_adjustment"
    description = "Expand verandas into their associated solver placeholder region."
    config_type = VerandaAdjustmentConfig

    def is_applicable(self, floor_plan, context, config):
        assert isinstance(config, VerandaAdjustmentConfig)
        if config.transformation_version in floor_plan.applied_transformations:
            return False, "this transformation version was already applied"
        has_pair = any(
            room.role is RoomRole.SOLVER_PLACEHOLDER and room.parent_room_id is not None
            for room in floor_plan.rooms
        )
        return has_pair, "no veranda placeholder association exists"

    def process(self, floor_plan, context, config):
        assert isinstance(config, VerandaAdjustmentConfig)
        by_id = {room.id: room for room in floor_plan.rooms}
        floor_shape = to_shapely(floor_plan.boundary)
        standard_shapes = {
            room.id: to_shapely(room.boundary)
            for room in floor_plan.rooms
            if room.role is RoomRole.STANDARD
        }
        affected = []

        placeholders = sorted(
            (
                room
                for room in floor_plan.rooms
                if room.role is RoomRole.SOLVER_PLACEHOLDER
                and room.parent_room_id is not None
            ),
            key=lambda room: str(room.id),
        )
        for placeholder in placeholders:
            parent_room_id = placeholder.parent_room_id
            if parent_room_id is None:
                continue
            veranda = by_id.get(parent_room_id)
            if veranda is None or veranda.room_type is not RoomType.VERANDA:
                continue
            current = standard_shapes[veranda.id]
            reserved = to_shapely(placeholder.boundary)
            minx, miny, maxx, maxy = current.bounds
            pminx, _, pmaxx, _ = reserved.bounds
            tolerance = context.numeric.tolerance
            if abs(pmaxx - minx) <= tolerance:
                strip = box(pminx, miny, minx, maxy)
            elif abs(pminx - maxx) <= tolerance:
                strip = box(maxx, miny, pmaxx, maxy)
            else:
                continue
            candidate = unary_union((current, reserved.intersection(strip)))
            if not isinstance(candidate, ShapelyPolygon):
                continue
            if candidate.area <= current.area + tolerance:
                continue
            width = candidate.bounds[2] - candidate.bounds[0]
            floor_width = floor_shape.bounds[2] - floor_shape.bounds[0]
            if width >= floor_width - tolerance or not floor_shape.buffer(
                tolerance
            ).covers(candidate):
                continue
            if any(
                candidate.intersection(other).area > tolerance
                for room_id, other in standard_shapes.items()
                if room_id != veranda.id
            ):
                continue
            veranda.boundary = from_shapely(candidate, tolerance)
            standard_shapes[veranda.id] = candidate
            affected.append(veranda.id)

        floor_plan.applied_transformations.add(config.transformation_version)
        if not affected:
            return ProcessorOutcome(
                ProcessorStatus.NO_CHANGE, "no veranda could be expanded"
            )
        return ProcessorOutcome(
            ProcessorStatus.CHANGED,
            "expanded associated veranda geometry",
            tuple(affected),
            metrics={"rooms_modified": len(affected)},
        )
