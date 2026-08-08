from __future__ import annotations

import math

from shapely.geometry import Polygon as ShapelyPolygon

from ..domain import (
    BuildableSpaceErrorCode,
    BuildableSpaceRequestData,
    LandEdge,
    NormalizedLand,
    Polygon,
    Segment,
)
from .config import BuildableLandConfig
from .exceptions import BuildableLandError
from .geometry import geometry_tolerance, signed_area


def normalize_land_request(
    request: BuildableSpaceRequestData,
    config: BuildableLandConfig,
) -> NormalizedLand:
    points = list(request.land_boundary.points)
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()

    limits = config.validation_limits
    if not limits.minimum_vertex_count <= len(points) <= limits.maximum_vertex_count:
        raise BuildableLandError(
            BuildableSpaceErrorCode.INVALID_LAND_BOUNDARY,
            "The land boundary has an unsupported number of effective vertices.",
        )
    if any(
        not math.isfinite(point.x)
        or not math.isfinite(point.y)
        or abs(point.x) > limits.maximum_absolute_coordinate
        or abs(point.y) > limits.maximum_absolute_coordinate
        for point in points
    ):
        raise BuildableLandError(
            BuildableSpaceErrorCode.INVALID_LAND_BOUNDARY,
            "Land coordinates exceed the configured limits.",
        )
    if len(set(points)) != len(points):
        raise BuildableLandError(
            BuildableSpaceErrorCode.INVALID_LAND_BOUNDARY,
            "Duplicate land-boundary points are not supported.",
        )

    if len(request.roads) != 1:
        raise BuildableLandError(
            BuildableSpaceErrorCode.MULTIPLE_MAIN_ENTRY_ROADS,
            "Exactly one main-entry road attachment is required.",
        )
    road = request.roads[0]
    if road.boundary_edge_index < 0 or road.boundary_edge_index >= len(points):
        raise BuildableLandError(
            BuildableSpaceErrorCode.INVALID_ROAD_ATTACHMENT,
            "The road attachment references an unknown boundary edge.",
        )
    if road.road_type not in config.setback_profile.road_adjustments:
        raise BuildableLandError(
            BuildableSpaceErrorCode.UNSUPPORTED_ROAD_TYPE,
            "The road type is not configured in the setback profile.",
        )

    polygon = Polygon(tuple(points))
    tolerance = geometry_tolerance(polygon.points)
    shape = ShapelyPolygon([(point.x, point.y) for point in points])
    if not shape.is_valid:
        raise BuildableLandError(
            BuildableSpaceErrorCode.SELF_INTERSECTING_LAND,
            "The land boundary must be ordered and non-self-intersecting.",
        )
    if shape.area <= tolerance:
        raise BuildableLandError(
            BuildableSpaceErrorCode.INVALID_LAND_BOUNDARY,
            "The land boundary must have positive area.",
        )

    cross_sign = 0
    for index, current in enumerate(points):
        following = points[(index + 1) % len(points)]
        after = points[(index + 2) % len(points)]
        cross = (
            (following.x - current.x) * (after.y - following.y)
            - (following.y - current.y) * (after.x - following.x)
        )
        if abs(cross) <= tolerance:
            raise BuildableLandError(
                BuildableSpaceErrorCode.INVALID_LAND_BOUNDARY,
                "Intermediate collinear boundary vertices are not supported.",
            )
        current_sign = 1 if cross > 0 else -1
        if cross_sign and current_sign != cross_sign:
            raise BuildableLandError(
                BuildableSpaceErrorCode.NON_CONVEX_LAND,
                "The land boundary must be convex.",
            )
        cross_sign = current_sign

    count = len(points)
    if signed_area(polygon) > 0:
        normalized_points = tuple(points)
        source_indexes = tuple(range(count))
    else:
        normalized_points = tuple(reversed(points))
        source_indexes = tuple((count - 2 - index) % count for index in range(count))

    edges = tuple(
        LandEdge(
            index=index,
            source_edge_index=source_indexes[index],
            segment=Segment(
                normalized_points[index],
                normalized_points[(index + 1) % count],
            ),
        )
        for index in range(count)
    )
    return NormalizedLand(
        boundary=Polygon(normalized_points),
        edges=edges,
        main_entry_road=road,
    )
