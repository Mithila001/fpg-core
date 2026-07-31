from __future__ import annotations

__all__ = [
    "find_usable_land",
]

import math

from shapely.geometry import Polygon as ShapelyPolygon

from .geometry import geometry_tolerance
from ..domain import (
    BuildableLand,
    BuildableSpaceErrorCode,
    NormalizedLand,
    UsableLand,
    UsableLandConstraints,
)
from .exceptions import UsableLandError
from .search import find_best_local_rectangle
from .transform import build_road_aligned_transform


def find_usable_land(
    buildable_land: BuildableLand,
    land: NormalizedLand,
    constraints: UsableLandConstraints,
) -> UsableLand:
    try:
        transform = build_road_aligned_transform(land)
        local_buildable = transform.to_local_polygon(buildable_land.boundary)
        candidate, evaluated = find_best_local_rectangle(
            local_buildable,
            constraints,
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
        return UsableLand(
            boundary=world_boundary,
            width=candidate.width,
            length=candidate.length,
            area=candidate.area,
            floor_width_alignment=candidate.alignment,
            entry_road_edge_index=land.main_entry_road.boundary_edge_index,
        )
    except UsableLandError:
        raise
    except (ArithmeticError, StopIteration, ValueError) as exc:
        wrapped = UsableLandError(
            BuildableSpaceErrorCode.USABLE_LAND_CALCULATION_FAILED,
            "Usable-land geometry calculation failed.",
        )
        raise wrapped from exc
