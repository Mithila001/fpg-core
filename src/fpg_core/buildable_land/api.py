from __future__ import annotations

import math

from shapely.geometry import Polygon as ShapelyPolygon

from ..domain import (
    BuildableLand,
    BuildableSpaceErrorCode,
    NormalizedLand,
    Polygon,
    SetbackProfile,
)
from .classification import classify_edges
from .exceptions import BuildableLandError
from .geometry import (
    clip_half_plane,
    dot,
    geometry_tolerance,
    polygon_area,
    unit_inward_normal,
)
from .setbacks import resolve_setbacks


def calculate_buildable_land(
    land: NormalizedLand,
    profile: SetbackProfile,
) -> BuildableLand:
    try:
        classifications = classify_edges(land)
        setbacks = resolve_setbacks(land, classifications, profile)
        setbacks_by_index = {item.edge_index: item for item in setbacks}
        tolerance = geometry_tolerance(land.boundary.points)
        clipped = land.boundary.points
        constraints: list[tuple[tuple[float, float], float]] = []
        for edge in land.edges:
            normal = unit_inward_normal(edge.segment)
            setback = setbacks_by_index[edge.source_edge_index].final_setback
            constant = dot(edge.segment.start, normal) + setback
            constraints.append((normal, constant))
            clipped = clip_half_plane(clipped, normal, constant, tolerance)
            if len(clipped) < 3:
                raise BuildableLandError(
                    BuildableSpaceErrorCode.SETBACK_ELIMINATES_BUILDABLE_LAND,
                    "The configured setbacks eliminate the buildable land.",
                )

        boundary = Polygon(clipped)
        area = polygon_area(boundary)
        if area <= tolerance or any(
            not math.isfinite(point.x) or not math.isfinite(point.y)
            for point in boundary.points
        ):
            raise BuildableLandError(
                BuildableSpaceErrorCode.SETBACK_ELIMINATES_BUILDABLE_LAND,
                "The configured setbacks do not leave a positive buildable area.",
            )
        for point in boundary.points:
            if any(dot(point, normal) < constant - tolerance for normal, constant in constraints):
                raise BuildableLandError(
                    BuildableSpaceErrorCode.BUILDABLE_LAND_CALCULATION_FAILED,
                    "The calculated buildable land violates a setback constraint.",
                )

        original_shape = ShapelyPolygon(
            [(point.x, point.y) for point in land.boundary.points]
        )
        buildable_shape = ShapelyPolygon(
            [(point.x, point.y) for point in boundary.points]
        )
        if (
            not buildable_shape.is_valid
            or not buildable_shape.equals(buildable_shape.convex_hull)
            or not original_shape.buffer(tolerance).covers(buildable_shape)
        ):
            raise BuildableLandError(
                BuildableSpaceErrorCode.BUILDABLE_LAND_CALCULATION_FAILED,
                "The calculated buildable land failed geometry validation.",
            )

        return BuildableLand(
            boundary=boundary,
            area=area,
            edge_setbacks=setbacks,
        )
    except BuildableLandError:
        raise
    except (ArithmeticError, KeyError, ValueError) as exc:
        wrapped = BuildableLandError(
            BuildableSpaceErrorCode.BUILDABLE_LAND_CALCULATION_FAILED,
            "Buildable-land geometry calculation failed.",
        )
        raise wrapped from exc
