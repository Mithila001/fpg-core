from __future__ import annotations

from ...types import Point, Polygon
from ..config import GridSnapConfig
from ..contracts import FloorPlanProcessor, ProcessorOutcome, ProcessorStatus
from ..exceptions import ProcessorError
from ..geometry import normalize_polygon
from ..validation import validate_floor_plan


class GridSnapProcessor(FloorPlanProcessor):
    processor_id = "grid_snap"
    description = "Snap floor and room coordinates to the configured grid."
    config_type = GridSnapConfig

    def process(self, floor_plan, context, config):
        assert isinstance(config, GridSnapConfig)
        grid = (
            config.grid_size
            if config.grid_size is not None
            else context.numeric.grid_size
        )
        if grid <= 0:
            raise ProcessorError("grid size must be positive")
        tolerance = context.numeric.tolerance

        def snap(polygon):
            return normalize_polygon(
                Polygon(
                    tuple(
                        Point(
                            round(point.x / grid) * grid, round(point.y / grid) * grid
                        )
                        for point in polygon.points
                    )
                ),
                tolerance,
            )

        changed = []
        snapped_floor = snap(floor_plan.boundary)
        floor_changed = snapped_floor != floor_plan.boundary
        if floor_changed:
            floor_plan.boundary = snapped_floor
        for room in floor_plan.rooms:
            boundary = snap(room.boundary)
            if boundary != room.boundary:
                room.boundary = boundary
                changed.append(room.id)
        validate_floor_plan(floor_plan, tolerance=tolerance)
        if not changed and not floor_changed:
            return ProcessorOutcome(
                ProcessorStatus.NO_CHANGE, "geometry was already grid-aligned"
            )
        return ProcessorOutcome(
            ProcessorStatus.CHANGED,
            "snapped geometry to the configured grid",
            tuple(changed),
            metrics={"rooms_modified": len(changed), "grid_size": grid},
        )
