from __future__ import annotations

from dataclasses import replace

from fpg_core.buildable_land import BuildableLandConfig
from fpg_core.candidate_circulation import (
    CandidateCirculationConfig,
    HallwayConsolidationConfig,
    RoutingCostProfile,
)
from fpg_core.candidate_scoring import (
    RELATIONSHIP_QUALITY_KEY,
    EvaluatorCategory,
    EvaluatorRule,
    RelationshipQualityConfig,
    ScoringConfig,
)
from fpg_core.candidate_scoring import (
    create_default_config as create_default_candidate_scoring_config,
)
from fpg_core.candidate_search import CandidateSearchConfig
from fpg_core.domain import (
    BuildableSpaceRequestData,
    CirculationRouteRule,
    CirculationTrafficClass,
    ConstraintStrength,
    DestinationSelection,
    GridRoutingCostProfile,
    LandSide,
    MatchPolicy,
    Point,
    Polygon,
    RoadAttachment,
    RoadRole,
    RoadType,
    RoomType,
    SetbackCalculationMode,
    SetbackProfile,
    ValidationLimits,
)
from fpg_core.floor_plan_openings import DEFAULT_OPENING_CONFIG
from fpg_core.floor_plan_preprocessing import (
    AspectRatioRule,
    PreprocessingConfig,
    RoomCountRule,
    RoomRelationReference,
    RoomSizeReference,
)
from fpg_core.floor_plan_scoring import (
    create_default_config as create_default_final_scoring_config,
)
from fpg_core.floor_plan_solver import DefaultProfileSettings, build_default_profiles
from fpg_core.usable_land import UsableLandConfig

TEST_TYPE = "full_flow"
PROJECT_UNITS_PER_METER = 10


def build_land_request() -> BuildableSpaceRequestData:
    # 24 m x 20 m rectangular parcel. Edge 0 is the front/main-road edge.
    return BuildableSpaceRequestData(
        land_boundary=Polygon(
            (
                Point(0.0, 0.0),
                Point(240.0, 0.0),
                Point(240.0, 200.0),
                Point(0.0, 200.0),
            )
        ),
        roads=(
            RoadAttachment(
                boundary_edge_index=0,
                role=RoadRole.MAIN_ENTRY,
                road_type=RoadType.MAIN_ROAD,
            ),
        ),
    )


def build_buildable_land_config() -> BuildableLandConfig:
    setback_profile = SetbackProfile(
        name="custom_test_residential_v1",
        status="active",
        description="Deterministic residential profile for fpg-core manual verification.",
        calculation_mode=SetbackCalculationMode.BASE_PLUS_ROAD_ADJUSTMENT,
        base_setbacks={
            LandSide.FRONT: 10,
            LandSide.RIGHT: 10,
            LandSide.BACK: 30,
            LandSide.LEFT: 10,
        },
        road_adjustments={
            RoadType.MAIN_ROAD: {LandSide.FRONT: 5},
            RoadType.PRIVATE_ROAD: {LandSide.FRONT: 0},
        },
    )
    return BuildableLandConfig(
        setback_profile=setback_profile,
        validation_limits=ValidationLimits(
            minimum_vertex_count=4,
            maximum_vertex_count=32,
            maximum_absolute_coordinate=100_000,
        ),
    )


def build_usable_land_config() -> UsableLandConfig:
    return UsableLandConfig(
        minimum_width=80,
        minimum_length=80,
        search_resolution=1,
        maximum_sweep_lines=5_000,
    )


def build_preprocessing_config() -> PreprocessingConfig:
    room_count_rules = (
        RoomCountRule(RoomType.BEDROOM, 1, 4),
        RoomCountRule(RoomType.BATHROOM, 1, 4),
        RoomCountRule(RoomType.ATTACHED_BATHROOM, 0, 4),
        RoomCountRule(RoomType.LIVING_ROOM, 1, 1),
        RoomCountRule(RoomType.KITCHEN, 1, 1),
        RoomCountRule(RoomType.DINING_ROOM, 1, 1),
        RoomCountRule(RoomType.HALLWAY, 1, 1, client_selectable=False),
        RoomCountRule(RoomType.VERANDA, 0, 1),
        RoomCountRule(RoomType.GARAGE, 0, 1),
    )
    room_sizes = (
        RoomSizeReference(RoomType.BEDROOM, "regular", 30.0, 42.0, 900.0, 1764.0),
        RoomSizeReference(RoomType.BATHROOM, "regular", 18.0, 25.0, 324.0, 625.0),
        RoomSizeReference(
            RoomType.ATTACHED_BATHROOM, "regular", 18.0, 24.0, 324.0, 672.0
        ),
        RoomSizeReference(RoomType.LIVING_ROOM, "regular", 40.0, 60.0, 1400.0, 3300.0),
        RoomSizeReference(RoomType.KITCHEN, "regular", 28.0, 40.0, 700.0, 1600.0),
        RoomSizeReference(RoomType.DINING_ROOM, "regular", 30.0, 45.0, 900.0, 2025.0),
        RoomSizeReference(RoomType.VERANDA, "regular", 20.0, 50.0, 360.0, 1500.0),
        RoomSizeReference(RoomType.GARAGE, "regular", 30.0, 38.0, 1650.0, 2470.0),
    )
    relations = (
        RoomRelationReference(
            RoomType.VERANDA,
            (RoomType.LIVING_ROOM,),
            MatchPolicy.OR,
            ConstraintStrength.HARD,
            required=False,
        ),
        RoomRelationReference(
            RoomType.DINING_ROOM,
            (RoomType.LIVING_ROOM,),
            MatchPolicy.OR,
            ConstraintStrength.HARD,
        ),
        RoomRelationReference(
            RoomType.KITCHEN,
            (RoomType.DINING_ROOM,),
            MatchPolicy.OR,
            ConstraintStrength.HARD,
        ),
        RoomRelationReference(
            RoomType.BATHROOM,
            (RoomType.HALLWAY,),
            MatchPolicy.OR,
            ConstraintStrength.HARD,
        ),
        RoomRelationReference(
            RoomType.BEDROOM,
            (RoomType.LIVING_ROOM, RoomType.HALLWAY),
            MatchPolicy.OR,
            ConstraintStrength.SOFT,
        ),
    )
    return PreprocessingConfig(
        room_count_rules=room_count_rules,
        supported_aspect_ratios=(
            AspectRatioRule("1:2", 0.5),
            AspectRatioRule("3:4", 0.75),
            AspectRatioRule("1:1", 1.0),
            AspectRatioRule("4:3", 4.0 / 3.0),
            AspectRatioRule("2:1", 2.0),
        ),
        room_sizes=room_sizes,
        room_relations=relations,
        mandatory_room_types=(
            RoomType.BEDROOM,
            RoomType.BATHROOM,
            RoomType.LIVING_ROOM,
            RoomType.KITCHEN,
            RoomType.DINING_ROOM,
        ),
        floor_area_buffer=500.0,
        hallway_area_buffer=120.0,
        max_hallway_room_count=4,
        hallway_min_width=8.0,
        candidate_search_grid_spacing=20,
        default_room_size="regular",
        max_aspect_residual_units=20.0,
    )


def build_route_rules() -> tuple[CirculationRouteRule, ...]:
    return (
        CirculationRouteRule(
            id=1,
            name="bedroom_to_living",
            source_room_type=RoomType.BEDROOM,
            destination_room_type=RoomType.LIVING_ROOM,
            destination_selection=DestinationSelection.LOWEST_COST_MATCH,
            traffic_class=CirculationTrafficClass.PRIVATE,
            allowed_transit_room_types=(RoomType.HALLWAY,),
            importance_weight=1.5,
        ),
        CirculationRouteRule(
            id=2,
            name="bathroom_to_living_via_hallway",
            source_room_type=RoomType.BATHROOM,
            destination_room_type=RoomType.LIVING_ROOM,
            destination_selection=DestinationSelection.LOWEST_COST_MATCH,
            traffic_class=CirculationTrafficClass.PRIVATE,
            allowed_transit_room_types=(),
            required_transit_room_types=(RoomType.HALLWAY,),
            importance_weight=2.0,
        ),
        CirculationRouteRule(
            id=3,
            name="veranda_to_living",
            source_room_type=RoomType.VERANDA,
            destination_room_type=RoomType.LIVING_ROOM,
            destination_selection=DestinationSelection.LOWEST_COST_MATCH,
            traffic_class=CirculationTrafficClass.PUBLIC,
            allowed_transit_room_types=(RoomType.HALLWAY,),
            importance_weight=1.0,
        ),
        CirculationRouteRule(
            id=4,
            name="kitchen_to_dining",
            source_room_type=RoomType.KITCHEN,
            destination_room_type=RoomType.DINING_ROOM,
            destination_selection=DestinationSelection.LOWEST_COST_MATCH,
            traffic_class=CirculationTrafficClass.PUBLIC,
            allowed_transit_room_types=(RoomType.HALLWAY, RoomType.LIVING_ROOM),
            importance_weight=1.0,
        ),
    )


def build_candidate_circulation_config() -> CandidateCirculationConfig:
    return CandidateCirculationConfig(
        costs=RoutingCostProfile(
            empty_node_cost=1.0,
            traversable_hint_node_cost=0.35,
            turn_cost=0.25,
            perimeter_bias_max_cost=0.40,
            traffic_conflict_cost=2.0,
        ),
        route_rules=build_route_rules(),
        always_traversable_room_types=(RoomType.HALLWAY,),
        max_routing_passes=3,
        hallway_consolidation=HallwayConsolidationConfig(
            enabled=True,
            minimum_separation_grid_steps=2.0,
            max_route_cost_increase_ratio=0.15,
        ),
    )


def build_candidate_scoring_config() -> ScoringConfig:
    base = create_default_candidate_scoring_config()
    relationship_config = RelationshipQualityConfig(
        costs=GridRoutingCostProfile(
            empty_node_cost=1.0,
            traversable_hint_node_cost=0.35,
            turn_cost=0.25,
            perimeter_bias_max_cost=0.40,
        ),
        route_rules=build_route_rules(),
        always_traversable_room_types=(RoomType.HALLWAY,),
    )
    return ScoringConfig(
        evaluator_rules=base.evaluator_rules
        + (
            EvaluatorRule(
                key=RELATIONSHIP_QUALITY_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=35.0,
                order=30,
                settings={"routing_config": relationship_config},
            ),
        ),
        fail_fast_on_critical_failure=base.fail_fast_on_critical_failure,
        not_applicable_quality_contributes=base.not_applicable_quality_contributes,
        raise_on_evaluator_error=base.raise_on_evaluator_error,
    )


def build_candidate_search_config() -> CandidateSearchConfig:
    return CandidateSearchConfig(
        trial_count=30,
        max_grid_node_count=250_000,
        random_seed=42,
    )


def build_solver_profiles():
    return build_default_profiles(
        DefaultProfileSettings(
            initial_max_time_seconds=5.0,
            refinement_max_time_seconds=2.0,
            max_hallway_shared_wall=12.0,
        )
    )


def build_opening_config():
    # Opening connectivity policy is consumer-owned. Keep the package defaults,
    # but add the hard kitchen<->dining relationship used by this scenario so
    # required room-access connectivity can be satisfied after solving.
    policy = replace(
        DEFAULT_OPENING_CONFIG.policy,
        allowed_room_pairs=(
            *DEFAULT_OPENING_CONFIG.policy.allowed_room_pairs,
            (RoomType.KITCHEN, RoomType.DINING_ROOM),
        ),
    )
    return replace(
        DEFAULT_OPENING_CONFIG,
        name="custom_test_full_flow_openings",
        policy=policy,
    )


def build_final_scoring_config():
    return create_default_final_scoring_config()
