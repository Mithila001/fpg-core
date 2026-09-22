from __future__ import annotations

import math
from time import perf_counter

from shapely.geometry import Polygon as ShapelyPolygon

from ..domain import (
    BuildableLand,
    BuildableSpaceErrorCode,
    ExecutionMetadata,
    ExecutionMode,
    FeatureExecution,
    Polygon,
)
from .classification import classify_edges
from .contracts import BuildableLandDetails, BuildableLandInput, BuildableLandResult
from .exceptions import BuildableLandError
from .geometry import (
    clip_half_plane,
    dot,
    geometry_tolerance,
    polygon_area,
    unit_inward_normal,
)
from .setbacks import resolve_setbacks
from .validation import normalize_land_request


def calculate_buildable_land(
    buildable_input: BuildableLandInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[BuildableLandResult, BuildableLandDetails]:
    """Validate a land request, apply setbacks, and calculate buildable land."""

    if not isinstance(buildable_input, BuildableLandInput):
        raise TypeError("buildable_input must be a BuildableLandInput instance.")
    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance.")

    started_at = perf_counter()
    try:
        land = normalize_land_request(buildable_input.request, buildable_input.config)
        classifications = classify_edges(land)
        setbacks = resolve_setbacks(
            land,
            classifications,
            buildable_input.config.setback_profile,
        )
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
            if any(
                dot(point, normal) < constant - tolerance
                for normal, constant in constraints
            ):
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

        buildable_land = BuildableLand(
            boundary=boundary,
            area=area,
            edge_setbacks=setbacks,
        )
        result = BuildableLandResult(
            buildable_land=buildable_land,
            normalized_land=land,
        )
        details = (
            BuildableLandDetails(edge_classifications=classifications)
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
    except BuildableLandError:
        raise
    except (ArithmeticError, KeyError, StopIteration, ValueError) as exc:
        wrapped = BuildableLandError(
            BuildableSpaceErrorCode.BUILDABLE_LAND_CALCULATION_FAILED,
            "Buildable-land geometry calculation failed.",
        )
        raise wrapped from exc


__all__ = ["calculate_buildable_land"]
