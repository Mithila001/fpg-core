from __future__ import annotations

import math
from time import perf_counter

from shapely.geometry import Polygon as ShapelyPolygon

from ..domain import (
    BuildableSpaceErrorCode,
    ExecutionMetadata,
    ExecutionMode,
    FeatureExecution,
    UsableLand,
)
from .contracts import UsableLandDetails, UsableLandInput
from .exceptions import UsableLandError
from .geometry import geometry_tolerance
from .search import find_best_local_rectangle
from .transform import build_road_aligned_transform


def find_usable_land(
    usable_input: UsableLandInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[UsableLand, UsableLandDetails]:
    """Find the best road-aligned rectangle inside buildable land."""

    if not isinstance(usable_input, UsableLandInput):
        raise TypeError("usable_input must be a UsableLandInput instance.")
    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance.")

    started_at = perf_counter()
    try:
        transform = build_road_aligned_transform(usable_input.land)
        local_buildable = transform.to_local_polygon(usable_input.buildable_land.boundary)
        candidate, evaluated = find_best_local_rectangle(
            local_buildable,
            usable_input.config,
        )

        tolerance = geometry_tolerance(local_buildable.points)
        buildable_shape = ShapelyPolygon(
            [(point.x, point.y) for point in local_buildable.points]
        )
        candidate_shape = ShapelyPolygon(
            [(point.x, point.y) for point in candidate.polygon.points]
        )
        if (
            not candidate_shape.is_valid
            or candidate_shape.area <= 0
            or not buildable_shape.buffer(tolerance).covers(candidate_shape)
            or not math.isclose(
                candidate_shape.area,
                candidate.area,
                rel_tol=1e-9,
                abs_tol=tolerance,
            )
        ):
            raise UsableLandError(
                BuildableSpaceErrorCode.USABLE_LAND_CALCULATION_FAILED,
                "The selected usable rectangle failed final geometry validation.",
            )

        world_boundary = transform.to_world_polygon(candidate.polygon)
        if any(
            not math.isfinite(point.x) or not math.isfinite(point.y)
            for point in world_boundary.points
        ):
            raise UsableLandError(
                BuildableSpaceErrorCode.USABLE_LAND_CALCULATION_FAILED,
                "The selected usable rectangle has non-finite coordinates.",
            )

        result = UsableLand(
            boundary=world_boundary,
            width=candidate.width,
            length=candidate.length,
            area=candidate.area,
            floor_width_alignment=candidate.alignment,
            entry_road_edge_index=usable_input.land.main_entry_road.boundary_edge_index,
        )
        details = (
            UsableLandDetails(
                evaluated_rectangle_pairs=evaluated,
                local_buildable_boundary=local_buildable,
                selected_local_boundary=candidate.polygon,
                transform_origin=transform.origin,
                transform_x_axis=transform.x_axis,
                transform_y_axis=transform.y_axis,
            )
            if mode is ExecutionMode.DEBUG
            else None
        )
        return FeatureExecution(
            result=result,
            details=details,
            metadata=ExecutionMetadata(
                mode=mode,
                duration_seconds=perf_counter() - started_at,
            ),
        )
    except UsableLandError:
        raise
    except (ArithmeticError, StopIteration, ValueError) as exc:
        wrapped = UsableLandError(
            BuildableSpaceErrorCode.USABLE_LAND_CALCULATION_FAILED,
            "Usable-land geometry calculation failed.",
        )
        raise wrapped from exc


__all__ = ["find_usable_land"]
