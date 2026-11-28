from __future__ import annotations

from typing import Annotated, Any, Literal

from fpg_core.floor_plan_scoring import (
    RoomRelationshipQualitySettings,
    RoomSizeConsistencySettings,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from fpg_lab.e03a_config import Configuration as E03AConfiguration

RoomTypeValue = Literal[
    "bedroom",
    "bathroom",
    "attached_bathroom",
    "living_room",
    "kitchen",
    "dining_room",
    "hallway",
    "veranda",
    "garage",
]
LandSideValue = Literal["front", "back", "left", "right"]
CardinalSideValue = Literal["south", "east", "north", "west"]
RoadTypeValue = Literal["main_road", "private_road"]
MatchPolicyValue = Literal["and", "or"]
ConstraintStrengthValue = Literal["hard", "soft"]
DestinationSelectionValue = Literal["all_matching", "lowest_cost_match", "assigned_relation"]
TrafficClassValue = Literal["public", "private"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetbackProfileDocument(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    status: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    calculation_mode: Literal["base_plus_road_adjustment"]
    base_setbacks: dict[LandSideValue, int]
    road_adjustments: dict[RoadTypeValue, dict[LandSideValue, int]]

    @model_validator(mode="after")
    def validate_sides(self) -> SetbackProfileDocument:
        sides = {"front", "back", "left", "right"}
        if set(self.base_setbacks) != sides:
            raise ValueError("base_setbacks must define front, back, left, and right")
        for road_type, values in self.road_adjustments.items():
            if set(values) != sides:
                raise ValueError(f"road_adjustments.{road_type} must define every side")
        return self


class UsableLandConstraintsDocument(StrictModel):
    minimum_width: int = Field(gt=0)
    minimum_length: int = Field(gt=0)
    search_resolution: int = Field(gt=0)
    maximum_sweep_lines: int = Field(gt=0)


class ValidationLimitsDocument(StrictModel):
    minimum_vertex_count: int = Field(ge=4)
    maximum_vertex_count: int = Field(ge=4)
    maximum_absolute_coordinate: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_counts(self) -> ValidationLimitsDocument:
        if self.minimum_vertex_count > self.maximum_vertex_count:
            raise ValueError("minimum_vertex_count cannot exceed maximum_vertex_count")
        return self


class BuildableSpaceDocument(StrictModel):
    active_profile: SetbackProfileDocument
    usable_land_constraints: UsableLandConstraintsDocument
    validation_limits: ValidationLimitsDocument


class RoomCountRuleDocument(StrictModel):
    room_type: RoomTypeValue
    minimum: int = Field(ge=0)
    maximum: int = Field(ge=0)
    client_selectable: bool = True

    @model_validator(mode="after")
    def validate_range(self) -> RoomCountRuleDocument:
        if self.minimum > self.maximum:
            raise ValueError("minimum room count cannot exceed maximum")
        return self


class AspectRatioRuleDocument(StrictModel):
    label: str = Field(min_length=1, max_length=32)
    canonical_value: float = Field(gt=0, allow_inf_nan=False)


class RoomSizeReferenceDocument(StrictModel):
    room_type: RoomTypeValue
    size: str = Field(min_length=1, max_length=64)
    min_width: float = Field(gt=0, allow_inf_nan=False)
    max_width: float = Field(gt=0, allow_inf_nan=False)
    min_area: float = Field(gt=0, allow_inf_nan=False)
    max_area: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_ranges(self) -> RoomSizeReferenceDocument:
        if self.min_width > self.max_width or self.min_area > self.max_area:
            raise ValueError("room size minimums cannot exceed maximums")
        return self


class RoomRelationReferenceDocument(StrictModel):
    source_room_type: RoomTypeValue
    target_room_types: list[RoomTypeValue] = Field(min_length=1)
    match_policy: MatchPolicyValue
    strength: ConstraintStrengthValue
    required: bool = True

    @model_validator(mode="after")
    def validate_targets(self) -> RoomRelationReferenceDocument:
        if len(set(self.target_room_types)) != len(self.target_room_types):
            raise ValueError("target_room_types must be unique")
        return self


class PreprocessingDocument(StrictModel):
    room_count_rules: list[RoomCountRuleDocument] = Field(min_length=1)
    supported_aspect_ratios: list[AspectRatioRuleDocument] = Field(min_length=1)
    room_sizes: list[RoomSizeReferenceDocument] = Field(min_length=1)
    room_relations: list[RoomRelationReferenceDocument] = Field(default_factory=list)
    mandatory_room_types: list[RoomTypeValue] = Field(min_length=1)
    floor_area_buffer: float = Field(ge=0, allow_inf_nan=False)
    hallway_area_buffer: float = Field(gt=0, allow_inf_nan=False)
    max_hallway_room_count: int = Field(ge=1)
    hallway_min_width: float = Field(ge=10, allow_inf_nan=False)
    candidate_search_grid_spacing: int = Field(ge=1)
    default_room_size: str = Field(min_length=1, max_length=64)
    max_aspect_residual_units: float = Field(default=20.0, ge=0, allow_inf_nan=False)
    min_aspect_ratio: float = Field(default=0.5, gt=0, allow_inf_nan=False)
    max_aspect_ratio: float = Field(default=2.0, gt=0, allow_inf_nan=False)
    room_size_strategy: Literal["majority"] = "majority"
    size_normalization_exclusions: list[RoomTypeValue] = Field(default_factory=lambda: ["hallway"])
    excess_attached_bathrooms: Literal["reject", "remove"] = "reject"

    @model_validator(mode="after")
    def validate_contract(self) -> PreprocessingDocument:
        for label, values in (
            ("room_count_rules", [item.room_type for item in self.room_count_rules]),
            ("supported_aspect_ratios", [item.label for item in self.supported_aspect_ratios]),
            ("mandatory_room_types", self.mandatory_room_types),
            ("size_normalization_exclusions", self.size_normalization_exclusions),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{label} must contain unique values")
        if self.candidate_search_grid_spacing % 2:
            raise ValueError("candidate_search_grid_spacing must be an even integer")
        if self.min_aspect_ratio > self.max_aspect_ratio:
            raise ValueError("min_aspect_ratio cannot exceed max_aspect_ratio")
        return self


class CandidateSearchDocument(StrictModel):
    max_grid_node_count: int = Field(default=250_000, ge=9)
    random_seed: int | None = Field(default=None, ge=0)


class RoutingCostDocument(StrictModel):
    empty_node_cost: float = Field(gt=0, allow_inf_nan=False)
    traversable_hint_node_cost: float = Field(gt=0, allow_inf_nan=False)
    turn_cost: float = Field(ge=0, allow_inf_nan=False)
    perimeter_bias_max_cost: float = Field(ge=0, allow_inf_nan=False)
    traffic_conflict_cost: float = Field(gt=0, allow_inf_nan=False)


class RouteDistancePolicyDocument(StrictModel):
    preferred_max_grid_steps: int = Field(ge=0, strict=True)
    over_limit_score_multiplier: float = Field(ge=0, le=1, allow_inf_nan=False)


class RouteRuleDocument(StrictModel):
    id: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=200)
    source_room_type: RoomTypeValue
    destination_room_type: RoomTypeValue
    destination_selection: DestinationSelectionValue
    traffic_class: TrafficClassValue
    allowed_transit_room_types: list[RoomTypeValue] = Field(default_factory=list)
    required_transit_room_types: list[RoomTypeValue] = Field(default_factory=list)
    importance_weight: float = Field(gt=0, allow_inf_nan=False)
    allow_global_transit: bool = True
    distance_policy: RouteDistancePolicyDocument | None = None


class CandidateCirculationDocument(StrictModel):
    costs: RoutingCostDocument
    route_rules: list[RouteRuleDocument] = Field(min_length=1)
    always_traversable_room_types: list[RoomTypeValue] = Field(default_factory=lambda: ["hallway"])
    max_routing_passes: int = Field(default=3, ge=2, le=10)

    @model_validator(mode="after")
    def validate_rules(self) -> CandidateCirculationDocument:
        if len({item.id for item in self.route_rules}) != len(self.route_rules):
            raise ValueError("candidate circulation route rule IDs must be unique")
        return self


class ZoneSuitabilitySettingsDocument(StrictModel):
    zone_count_per_axis: int = Field(default=3, gt=0)
    falloff_multiplier: float = Field(default=1.5, gt=0, allow_inf_nan=False)
    valid_zones: dict[RoomTypeValue, list[tuple[int, int]]] = Field(default_factory=dict)


class ExteriorClearanceRuleDocument(StrictModel):
    room_types: list[RoomTypeValue] = Field(min_length=1)
    required_clear_room_count: int = Field(gt=0)
    clearance_width: float = Field(gt=0, allow_inf_nan=False)
    direction: LandSideValue


class ExteriorClearanceSettingsDocument(StrictModel):
    rules: list[ExteriorClearanceRuleDocument] = Field(min_length=1)


class CirculationQualitySettingsDocument(StrictModel):
    efficiency_weight: float = Field(default=0.7, ge=0, allow_inf_nan=False)
    traffic_separation_weight: float = Field(default=0.3, ge=0, allow_inf_nan=False)
    single_hallway_penalty_multiplier: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    multiple_hallway_penalty_multiplier: float = Field(default=1.0, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_weights(self):
        if self.efficiency_weight + self.traffic_separation_weight <= 0:
            raise ValueError("circulation weights must have a positive sum")
        return self


class FunctionalGroupDocument(StrictModel):
    name: str = Field(min_length=1)
    room_types: list[RoomTypeValue] = Field(min_length=1)


class FunctionalGroupPuritySettingsDocument(StrictModel):
    groups: list[FunctionalGroupDocument] = Field(default_factory=lambda: [FunctionalGroupDocument(name="bedrooms", room_types=["bedroom"])])
    direct_interruption_penalty: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    regional_intrusion_penalty: float = Field(default=0.5, ge=0, allow_inf_nan=False)
    connection_tolerance_grid_steps: float = Field(default=0.5, ge=0, allow_inf_nan=False)


class SpatialDistributionSettingsDocument(StrictModel):
    nnd_weight: float = Field(default=0.4, ge=0, allow_inf_nan=False)
    coverage_weight: float = Field(default=0.6, ge=0, allow_inf_nan=False)
    nnd_cv_sensitivity: float = Field(default=8.0, gt=0, allow_inf_nan=False)
    sample_count_per_axis: int = Field(default=20, ge=2)
    gap_zero_score_ratio: float = Field(default=1.5, gt=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_weights(self) -> SpatialDistributionSettingsDocument:
        if self.nnd_weight + self.coverage_weight <= 0:
            raise ValueError("spatial distribution weights must have a positive sum")
        return self


class CandidateEvaluatorBaseDocument(StrictModel):
    category: Literal["critical", "quality"] = "quality"
    enabled: bool = True
    order: int = Field(ge=0)
    weight: float = Field(gt=0, allow_inf_nan=False)
    minimum_score: float | None = Field(default=None, ge=0, le=100)


class ZoneSuitabilityEvaluatorDocument(CandidateEvaluatorBaseDocument):
    key: Literal["zone_suitability"]
    settings: ZoneSuitabilitySettingsDocument


class ExteriorClearanceEvaluatorDocument(CandidateEvaluatorBaseDocument):
    key: Literal["exterior_clearance"]
    settings: ExteriorClearanceSettingsDocument


class CirculationQualityEvaluatorDocument(CandidateEvaluatorBaseDocument):
    key: Literal["circulation_quality"]
    settings: CirculationQualitySettingsDocument


class FunctionalGroupPurityEvaluatorDocument(CandidateEvaluatorBaseDocument):
    key: Literal["functional_group_purity"]
    settings: FunctionalGroupPuritySettingsDocument


class SpatialDistributionEvaluatorDocument(CandidateEvaluatorBaseDocument):
    key: Literal["spatial_distribution"]
    settings: SpatialDistributionSettingsDocument


CandidateEvaluatorDocument = Annotated[
    ZoneSuitabilityEvaluatorDocument
    | ExteriorClearanceEvaluatorDocument
    | CirculationQualityEvaluatorDocument
    | FunctionalGroupPurityEvaluatorDocument
    | SpatialDistributionEvaluatorDocument,
    Field(discriminator="key"),
]


class CandidateScoringDocument(StrictModel):
    evaluator_rules: list[CandidateEvaluatorDocument] = Field(min_length=1)
    fail_fast_on_critical_failure: bool = True

    @model_validator(mode="after")
    def unique_rules(self) -> CandidateScoringDocument:
        keys = [item.key for item in self.evaluator_rules]
        if len(keys) != len(set(keys)):
            raise ValueError("candidate scoring evaluator keys must be unique")
        return self


class ConstraintUseDocument(StrictModel):
    key: str = Field(min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)


class SoftConstraintUseDocument(ConstraintUseDocument):
    weight: float = Field(ge=0, le=10, strict=True, allow_inf_nan=False)


class SolverRuntimeDocument(StrictModel):
    max_time_seconds: float = Field(gt=0, allow_inf_nan=False)
    num_search_workers: int = Field(ge=0)
    random_seed: int | None = Field(default=None, ge=0)
    log_search_progress: bool = False
    relative_gap_limit: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cp_model_presolve: bool = True


class SolverPreparationDocument(StrictModel):
    coordinate_scale: int = Field(ge=1)


class SolverSeedDocument(StrictModel):
    source: Literal["none", "candidate_hints", "existing_floor_plan"]
    require_source: bool = False
    apply_hints: bool = True
    position_tolerance: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    size_tolerance: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class SolverStageDocument(StrictModel):
    name: str = Field(min_length=1)
    hard_constraints: list[ConstraintUseDocument]
    soft_constraints: list[SoftConstraintUseDocument]
    solver: SolverRuntimeDocument
    preparation: SolverPreparationDocument
    seed: SolverSeedDocument


class FloorPlanSolverDocument(StrictModel):
    initial: SolverStageDocument
    refinement_a: SolverStageDocument
    refinement_b: SolverStageDocument


class NumericPolicyDocument(StrictModel):
    tolerance: float = Field(gt=0, allow_inf_nan=False)
    grid_size: float = Field(gt=0, allow_inf_nan=False)


class WallExtensionRuleDocument(StrictModel):
    room_type: RoomTypeValue
    max_distance: float = Field(gt=0, allow_inf_nan=False)


class ExteriorStepPolicyDocument(StrictModel):
    direction: Literal["front", "back", "left", "right"]
    minimum_depth: float = Field(ge=0, allow_inf_nan=False)
    minimum_segment_length: float = Field(ge=0, allow_inf_nan=False)
    preferred_max_steps: int = Field(ge=0)


class WallExtensionSettingsDocument(StrictModel):
    rules: list[WallExtensionRuleDocument]
    exterior_steps: list[ExteriorStepPolicyDocument]
    max_recess_ratio: float = Field(gt=0, allow_inf_nan=False)
    max_recess_levels: int = Field(gt=0)
    min_pocket_area: float = Field(ge=0, allow_inf_nan=False)
    min_contact_length: float = Field(gt=0, allow_inf_nan=False)
    min_residual_edge: float = Field(gt=0, allow_inf_nan=False)
    min_extension_width: float = Field(gt=0, allow_inf_nan=False)
    min_extension_depth: float = Field(gt=0, allow_inf_nan=False)
    hallway_min_extension_width: float = Field(gt=0, allow_inf_nan=False)
    hallway_min_extension_depth: float = Field(gt=0, allow_inf_nan=False)
    max_area_excess: float = Field(ge=0, allow_inf_nan=False)
    max_width_excess: float = Field(ge=0, allow_inf_nan=False)
    max_iterations: int = Field(gt=0)
    max_candidate_evaluations: int = Field(gt=0)
    transformation_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_policies(self) -> WallExtensionSettingsDocument:
        directions = [item.direction for item in self.exterior_steps]
        if len(directions) != 4 or set(directions) != {"front", "back", "left", "right"}:
            raise ValueError("exterior_steps must contain each direction exactly once")
        room_types = [item.room_type for item in self.rules]
        if len(room_types) != len(set(room_types)):
            raise ValueError("wall-extension room types must be unique")
        return self


class EmptySettingsDocument(StrictModel):
    pass


class HallwayMergeSettingsDocument(StrictModel):
    minimum_shared_wall: float = Field(gt=0, allow_inf_nan=False)


class GridSnapSettingsDocument(StrictModel):
    grid_size: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class ProcessorBaseDocument(StrictModel):
    required: bool = False
    validate_after: bool = False


class WallExtensionProcessorDocument(ProcessorBaseDocument):
    processor_id: Literal["wall_extension"]
    config: WallExtensionSettingsDocument


class PlaceholderProcessorDocument(ProcessorBaseDocument):
    processor_id: Literal["remove_placeholder_rooms"]
    config: EmptySettingsDocument


class HallwayMergeProcessorDocument(ProcessorBaseDocument):
    processor_id: Literal["hallway_merge"]
    config: HallwayMergeSettingsDocument


class GridSnapProcessorDocument(ProcessorBaseDocument):
    processor_id: Literal["grid_snap"]
    config: GridSnapSettingsDocument


class RectilinearProcessorDocument(ProcessorBaseDocument):
    processor_id: Literal["rectilinear_simplification"]
    config: EmptySettingsDocument


ProcessorDocument = Annotated[
    WallExtensionProcessorDocument
    | PlaceholderProcessorDocument
    | HallwayMergeProcessorDocument
    | GridSnapProcessorDocument
    | RectilinearProcessorDocument,
    Field(discriminator="processor_id"),
]


class PostProcessingDocument(StrictModel):
    name: str = Field(min_length=1)
    processors: list[ProcessorDocument]
    numeric: NumericPolicyDocument
    reject_existing_openings: bool = True


class OpeningGeometryDocument(StrictModel):
    coordinate_scale: int = Field(ge=1)
    tolerance: float = Field(gt=0, allow_inf_nan=False)
    corner_clearance: float = Field(ge=0, allow_inf_nan=False)
    window_spacing: float = Field(ge=0, allow_inf_nan=False)


class OpeningDimensionsDocument(StrictModel):
    door_width: float = Field(gt=0, allow_inf_nan=False)
    window_width: float = Field(gt=0, allow_inf_nan=False)
    minimum_shared_wall: float = Field(gt=0, allow_inf_nan=False)


class InteriorDoorPolicyDocument(StrictModel):
    door_width: float = Field(gt=0, allow_inf_nan=False)
    preferred_clearance: float = Field(ge=0, allow_inf_nan=False)
    minimum_clearance: float = Field(ge=0, allow_inf_nan=False)
    minimum_shared_wall: float = Field(gt=0, allow_inf_nan=False)
    placement_preference: Literal["wall_end", "center"]


class InteriorDoorOverrideDocument(StrictModel):
    room_type: RoomTypeValue
    policy: InteriorDoorPolicyDocument


class InteriorDoorsDocument(StrictModel):
    default: InteriorDoorPolicyDocument
    overrides: list[InteriorDoorOverrideDocument]


class OpeningRoomPairDocument(StrictModel):
    first: RoomTypeValue
    second: RoomTypeValue


class OpeningRoomDoorCapDocument(StrictModel):
    room_type: RoomTypeValue
    maximum: int = Field(gt=0)


class OpeningDoorPriorityDocument(StrictModel):
    room_type: RoomTypeValue
    priority: int = Field(ge=0)


class WindowPolicyDocument(StrictModel):
    width: float = Field(gt=0, allow_inf_nan=False)
    target_count: int = Field(ge=1)
    preferred_clearance: float = Field(ge=0, allow_inf_nan=False)
    minimum_clearance: float = Field(ge=0, allow_inf_nan=False)


class WindowPolicyOverrideDocument(StrictModel):
    room_type: RoomTypeValue
    policy: WindowPolicyDocument


class OpeningFeaturePolicyDocument(StrictModel):
    allowed_room_pairs: list[OpeningRoomPairDocument]
    room_door_caps: list[OpeningRoomDoorCapDocument]
    secondary_room_priority: list[RoomTypeValue]
    window_room_types: list[RoomTypeValue]
    window_policies: list[WindowPolicyOverrideDocument]
    normal_connection_caps: list[OpeningRoomDoorCapDocument]
    prevent_duplicate_connections: bool
    main_side_priority: list[CardinalSideValue]
    secondary_side_priority: list[CardinalSideValue]
    window_side_priority: list[CardinalSideValue]
    required_access_room_types: list[RoomTypeValue]
    door_placement_priority: list[OpeningDoorPriorityDocument]


class OpeningObjectiveDocument(StrictModel):
    tier_order: list[str]


class OpeningSolverDocument(StrictModel):
    max_time_seconds: float = Field(gt=0, allow_inf_nan=False)
    num_search_workers: int = Field(gt=0)
    random_seed: int = Field(ge=0)
    cp_model_presolve: bool = True
    log_search_progress: bool = False


class OpeningsDocument(StrictModel):
    name: str = Field(min_length=1)
    enabled_features: list[Literal["interior_doors", "exterior_doors", "windows"]]
    enabled_constraints: list[
        Literal["shared_placement", "room_door_limits", "required_room_access"]
    ]
    geometry: OpeningGeometryDocument
    dimensions: OpeningDimensionsDocument
    interior_doors: InteriorDoorsDocument
    policy: OpeningFeaturePolicyDocument
    objective: OpeningObjectiveDocument
    solver: OpeningSolverDocument


class ScoringGroupDocument(StrictModel):
    key: str = Field(min_length=1)
    enabled: bool = True
    order: int = Field(ge=0)
    weight: float = Field(gt=0, allow_inf_nan=False)


class GeometryIntegritySettingsDocument(StrictModel):
    tolerance: float = Field(ge=0, allow_inf_nan=False)


class EnclosedVoidsSettingsDocument(StrictModel):
    area_tolerance: float = Field(ge=0, allow_inf_nan=False)


class InwardRecessSettingsDocument(StrictModel):
    max_depth_to_width_ratio: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    max_recess_levels: int = Field(default=1, ge=1, strict=True)
    tolerance: float = Field(default=1e-6, ge=0, allow_inf_nan=False)


class LivingRoomBalanceSettingsDocument(StrictModel):
    maximum_excess_ratio: float = Field(gt=0, allow_inf_nan=False)


class BedroomQualitySettingsDocument(StrictModel):
    area_compliance_weight: float = Field(gt=0, allow_inf_nan=False)
    consistency_weight: float = Field(gt=0, allow_inf_nan=False)
    full_spread_penalty_ratio: float = Field(ge=0, allow_inf_nan=False)
    maximum_spread_penalty: float = Field(ge=0, allow_inf_nan=False)


class FloorEvaluatorBaseDocument(StrictModel):
    group_key: str = Field(min_length=1)
    enabled: bool = True
    order: int = Field(ge=0)
    weight: float = Field(gt=0, allow_inf_nan=False)
    minimum_score: float | None = Field(default=None, ge=0, le=100)


class GeometryIntegrityEvaluatorDocument(FloorEvaluatorBaseDocument):
    key: Literal["geometry_integrity"]
    settings: GeometryIntegritySettingsDocument


class EnclosedVoidsEvaluatorDocument(FloorEvaluatorBaseDocument):
    key: Literal["enclosed_voids"]
    settings: EnclosedVoidsSettingsDocument


class InwardRecessEvaluatorDocument(FloorEvaluatorBaseDocument):
    key: Literal["inward_recess"]
    settings: InwardRecessSettingsDocument


class LivingRoomBalanceEvaluatorDocument(FloorEvaluatorBaseDocument):
    key: Literal["living_room_balance"]
    settings: LivingRoomBalanceSettingsDocument


class BedroomQualityEvaluatorDocument(FloorEvaluatorBaseDocument):
    key: Literal["bedroom_quality"]
    settings: BedroomQualitySettingsDocument


class RoomRelationshipQualityEvaluatorDocument(FloorEvaluatorBaseDocument):
    key: Literal["room_relationship_quality"]
    settings: RoomRelationshipQualitySettings


class RoomSizeConsistencyEvaluatorDocument(FloorEvaluatorBaseDocument):
    key: Literal["room_size_consistency"]
    settings: RoomSizeConsistencySettings


FloorEvaluatorDocument = Annotated[
    GeometryIntegrityEvaluatorDocument
    | EnclosedVoidsEvaluatorDocument
    | InwardRecessEvaluatorDocument
    | LivingRoomBalanceEvaluatorDocument
    | BedroomQualityEvaluatorDocument
    | RoomRelationshipQualityEvaluatorDocument
    | RoomSizeConsistencyEvaluatorDocument,
    Field(discriminator="key"),
]


class FloorPlanScoringDocument(StrictModel):
    groups: list[ScoringGroupDocument] = Field(min_length=1)
    evaluators: list[FloorEvaluatorDocument] = Field(min_length=1)


class ExperimentsDocument(StrictModel):
    p01b_refinement: SolverStageDocument | None = None
    e03a: E03AConfiguration | None = None


class SystemConfigurationDocument(StrictModel):
    schema_version: Literal[8] = 8
    project_units_per_meter: int = Field(gt=0)
    buildable_space: BuildableSpaceDocument | None = None
    preprocessing: PreprocessingDocument | None = None
    candidate_search: CandidateSearchDocument | None = None
    candidate_circulation: CandidateCirculationDocument | None = None
    candidate_scoring: CandidateScoringDocument | None = None
    floor_plan_solver: FloorPlanSolverDocument | None = None
    post_processing: PostProcessingDocument | None = None
    openings: OpeningsDocument | None = None
    floor_plan_scoring: FloorPlanScoringDocument | None = None
    experiments: ExperimentsDocument = Field(default_factory=ExperimentsDocument)
