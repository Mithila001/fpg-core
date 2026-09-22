from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from .geometry import Polygon, Segment


class RoadRole(StrEnum):
    MAIN_ENTRY = "main_entry"


class RoadType(StrEnum):
    MAIN_ROAD = "main_road"
    PRIVATE_ROAD = "private_road"


class LandSide(StrEnum):
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"


class SetbackCalculationMode(StrEnum):
    BASE_PLUS_ROAD_ADJUSTMENT = "base_plus_road_adjustment"


class FloorWidthAlignment(StrEnum):
    PARALLEL_TO_ENTRY_ROAD = "parallel_to_entry_road"
    PERPENDICULAR_TO_ENTRY_ROAD = "perpendicular_to_entry_road"


class BuildableSpaceStage(StrEnum):
    REQUEST_VALIDATION = "request_validation"
    REFERENCE_DATA = "reference_data"
    BUILDABLE_LAND = "buildable_land"
    USABLE_LAND = "usable_land"
    RESPONSE = "response"


class BuildableSpaceErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INVALID_LAND_BOUNDARY = "invalid_land_boundary"
    NON_CONVEX_LAND = "non_convex_land"
    SELF_INTERSECTING_LAND = "self_intersecting_land"
    INVALID_ROAD_ATTACHMENT = "invalid_road_attachment"
    MULTIPLE_MAIN_ENTRY_ROADS = "multiple_main_entry_roads"
    UNSUPPORTED_ROAD_TYPE = "unsupported_road_type"
    REFERENCE_DATA_ERROR = "reference_data_error"
    SETBACK_ELIMINATES_BUILDABLE_LAND = "setback_eliminates_buildable_land"
    BUILDABLE_LAND_CALCULATION_FAILED = "buildable_land_calculation_failed"
    NO_USABLE_LAND_FOUND = "no_usable_land_found"
    SEARCH_LIMIT_EXCEEDED = "search_limit_exceeded"
    USABLE_LAND_CALCULATION_FAILED = "usable_land_calculation_failed"
    UNEXPECTED_BUILDABLE_SPACE_ERROR = "unexpected_buildable_space_error"


@dataclass(frozen=True, slots=True)
class LandEdge:
    index: int
    source_edge_index: int
    segment: Segment


@dataclass(frozen=True, slots=True)
class RoadAttachment:
    boundary_edge_index: int
    role: RoadRole
    road_type: RoadType


@dataclass(frozen=True, slots=True)
class BuildableSpaceRequestData:
    land_boundary: Polygon
    roads: tuple[RoadAttachment, ...]


@dataclass(frozen=True, slots=True)
class NormalizedLand:
    boundary: Polygon
    edges: tuple[LandEdge, ...]
    main_entry_road: RoadAttachment


@dataclass(frozen=True, slots=True)
class EdgeClassification:
    edge_index: int
    side: LandSide


@dataclass(frozen=True, slots=True)
class EdgeSetback:
    edge_index: int
    side: LandSide
    base_setback: int
    road_adjustment: int
    final_setback: int
    road_type: RoadType | None = None


@dataclass(frozen=True, slots=True)
class BuildableLand:
    boundary: Polygon
    area: float
    edge_setbacks: tuple[EdgeSetback, ...]


@dataclass(frozen=True, slots=True)
class UsableLand:
    boundary: Polygon
    width: int
    length: int
    area: int
    floor_width_alignment: FloorWidthAlignment
    entry_road_edge_index: int


@dataclass(frozen=True, slots=True)
class SetbackProfile:
    name: str
    status: str
    description: str
    calculation_mode: SetbackCalculationMode
    base_setbacks: Mapping[LandSide, int]
    road_adjustments: Mapping[RoadType, Mapping[LandSide, int]]

    def __post_init__(self) -> None:
        frozen_base = MappingProxyType(dict(self.base_setbacks))
        frozen_adjustments = MappingProxyType(
            {
                road_type: MappingProxyType(dict(adjustments))
                for road_type, adjustments in self.road_adjustments.items()
            }
        )
        object.__setattr__(self, "base_setbacks", frozen_base)
        object.__setattr__(self, "road_adjustments", frozen_adjustments)


@dataclass(frozen=True, slots=True)
class UsableLandConstraints:
    minimum_width: int
    minimum_length: int
    search_resolution: int
    maximum_sweep_lines: int


@dataclass(frozen=True, slots=True)
class ValidationLimits:
    minimum_vertex_count: int
    maximum_vertex_count: int
    maximum_absolute_coordinate: int


@dataclass(frozen=True, slots=True)
class BuildableSpaceReferenceData:
    schema_version: int
    project_units_per_meter: int
    active_profile: SetbackProfile
    usable_land_constraints: UsableLandConstraints
    validation_limits: ValidationLimits


@dataclass(frozen=True, slots=True)
class BuildableSpaceResult:
    original_land_area: float
    buildable_land: BuildableLand
    usable_land: UsableLand
    reference_profile: str
    project_units_per_meter: int
