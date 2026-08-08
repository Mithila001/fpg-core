from __future__ import annotations

import json
import logging
import math
import sys
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Any

# Allow running directly from a source checkout without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
if SOURCE_ROOT.is_dir():
    sys.path.insert(0, str(SOURCE_ROOT))

from fpg_core.candidate_circulation import (  # noqa: E402
    CandidateCirculationConfig,
    CandidateCirculationInput,
    RoutingCostProfile,
    refine_candidate_circulation,
)
from fpg_core.candidate_scoring import (  # noqa: E402
    EXTERIOR_CLEARANCE_KEY,
    RELATIONSHIP_QUALITY_KEY,
    SPATIAL_DISTRIBUTION_KEY,
    ZONE_SUITABILITY_KEY,
    CandidateScoringInput,
    EvaluatorCategory,
    EvaluatorRule,
    ExteriorClearanceRule,
    RelationshipQualityConfig,
    ScoringConfig,
    ZoneSuitabilityConfig,
    create_default_registry,
    evaluate_candidate,
)
from fpg_core.candidate_search import (  # noqa: E402
    CandidateSearchConfig,
    CandidateSearchInput,
    build_candidate_search_targets,
    search_candidates,
)
from fpg_core.domain import (  # noqa: E402
    CandidateMap,
    CirculationRouteRule,
    CirculationTrafficClass,
    ConstraintStrength,
    DestinationSelection,
    ExecutionMode,
    GridRoutingCostProfile,
    LandSide,
    MatchPolicy,
    RoomType,
)
from fpg_core.floor_plan_preprocessing import (  # noqa: E402
    AspectRatioRule,
    ExcessAttachedBathroomPolicy,
    FloorLimits,
    PreprocessingConfig,
    PreprocessingInput,
    PreprocessingRequest,
    RequestedRoom,
    RoomCountRule,
    RoomRelationReference,
    RoomSizeReference,
    RoomSizeSelectionStrategy,
    prepare_generation_input,
)

HERE = Path(__file__).resolve().parent
INPUT_PATH = HERE / "input.json"
RESULT_PATH = HERE / "result.json"

logging.getLogger("optuna").setLevel(logging.WARNING)


def room_type(raw: str) -> RoomType:
    return RoomType(raw)


def load_input() -> dict[str, Any]:
    with INPUT_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("input.json must contain a JSON object.")
    return data


def build_preprocessing_input(data: dict[str, Any]) -> PreprocessingInput:
    section = data["preprocessing"]
    request_data = section["request"]
    config_data = section["config"]

    request = PreprocessingRequest(
        floor_limits=FloorLimits(**request_data["floor_limits"]),
        aspect_ratio=request_data["aspect_ratio"],
        rooms=tuple(
            RequestedRoom(
                id=item.get("id"),
                name=item.get("name"),
                room_type=room_type(item["room_type"]),
                requested_size=item.get("requested_size"),
            )
            for item in request_data["rooms"]
        ),
    )

    config = PreprocessingConfig(
        room_count_rules=tuple(
            RoomCountRule(
                room_type=room_type(item["room_type"]),
                minimum=item["minimum"],
                maximum=item["maximum"],
                client_selectable=item.get("client_selectable", True),
            )
            for item in config_data["room_count_rules"]
        ),
        supported_aspect_ratios=tuple(
            AspectRatioRule(**item)
            for item in config_data["supported_aspect_ratios"]
        ),
        room_sizes=tuple(
            RoomSizeReference(
                room_type=room_type(item["room_type"]),
                size=item["size"],
                min_width=item["min_width"],
                max_width=item["max_width"],
                min_area=item["min_area"],
                max_area=item["max_area"],
            )
            for item in config_data["room_sizes"]
        ),
        room_relations=tuple(
            RoomRelationReference(
                source_room_type=room_type(item["source_room_type"]),
                target_room_types=tuple(
                    room_type(value) for value in item["target_room_types"]
                ),
                match_policy=MatchPolicy(item["match_policy"]),
                strength=ConstraintStrength(item["strength"]),
                required=item.get("required", True),
            )
            for item in config_data["room_relations"]
        ),
        mandatory_room_types=tuple(
            room_type(value) for value in config_data["mandatory_room_types"]
        ),
        floor_area_buffer=config_data["floor_area_buffer"],
        hallway_area_buffer=config_data["hallway_area_buffer"],
        max_hallway_room_count=config_data["max_hallway_room_count"],
        hallway_min_width=config_data["hallway_min_width"],
        candidate_search_grid_spacing=config_data[
            "candidate_search_grid_spacing"
        ],
        default_room_size=config_data["default_room_size"],
        max_aspect_residual_units=config_data["max_aspect_residual_units"],
        min_aspect_ratio=config_data.get("min_aspect_ratio", 0.5),
        max_aspect_ratio=config_data.get("max_aspect_ratio", 2.0),
        room_size_strategy=RoomSizeSelectionStrategy(
            config_data.get("room_size_strategy", "majority")
        ),
        size_normalization_exclusions=tuple(
            room_type(value)
            for value in config_data.get(
                "size_normalization_exclusions", [RoomType.HALLWAY.value]
            )
        ),
        excess_attached_bathrooms=ExcessAttachedBathroomPolicy(
            config_data.get("excess_attached_bathrooms", "reject")
        ),
    )
    return PreprocessingInput(request=request, config=config)


def build_route_rules(items: list[dict[str, Any]]) -> tuple[CirculationRouteRule, ...]:
    return tuple(
        CirculationRouteRule(
            id=item["id"],
            name=item["name"],
            source_room_type=room_type(item["source_room_type"]),
            destination_room_type=room_type(item["destination_room_type"]),
            destination_selection=DestinationSelection(
                item["destination_selection"]
            ),
            traffic_class=CirculationTrafficClass(item["traffic_class"]),
            allowed_transit_room_types=tuple(
                room_type(value) for value in item["allowed_transit_room_types"]
            ),
            importance_weight=item["importance_weight"],
        )
        for item in items
    )


def build_circulation_config(data: dict[str, Any]) -> CandidateCirculationConfig:
    section = data["candidate_circulation"]
    costs = section["costs"]
    return CandidateCirculationConfig(
        costs=RoutingCostProfile(
            empty_node_cost=costs["empty_node_cost"],
            traversable_hint_node_cost=costs["traversable_hint_node_cost"],
            turn_cost=costs["turn_cost"],
            perimeter_bias_max_cost=costs["perimeter_bias_max_cost"],
            traffic_conflict_cost=costs["traffic_conflict_cost"],
        ),
        route_rules=build_route_rules(section["route_rules"]),
        always_traversable_room_types=tuple(
            room_type(value)
            for value in section["always_traversable_room_types"]
        ),
        max_routing_passes=section["max_routing_passes"],
    )


def build_scoring_config(
    data: dict[str, Any],
    route_rules: tuple[CirculationRouteRule, ...],
) -> ScoringConfig:
    section = data["candidate_scoring"]
    zone = section["zone_suitability"]
    weights = section["evaluator_weights"]
    circulation_costs = data["candidate_circulation"]["costs"]

    zone_config = ZoneSuitabilityConfig(
        zone_count_per_axis=zone["zone_count_per_axis"],
        falloff_multiplier=zone["falloff_multiplier"],
        valid_zones={
            room_type(key): tuple(tuple(cell) for cell in cells)
            for key, cells in zone["valid_zones"].items()
        },
    )
    exterior_rules = tuple(
        ExteriorClearanceRule(
            room_types=tuple(room_type(value) for value in item["room_types"]),
            required_clear_room_count=item["required_clear_room_count"],
            clearance_width=item["clearance_width"],
            direction=LandSide(item["direction"]),
        )
        for item in section["exterior_clearance_rules"]
    )
    relationship_config = RelationshipQualityConfig(
        costs=GridRoutingCostProfile(
            empty_node_cost=circulation_costs["empty_node_cost"],
            traversable_hint_node_cost=circulation_costs[
                "traversable_hint_node_cost"
            ],
            turn_cost=circulation_costs["turn_cost"],
            perimeter_bias_max_cost=circulation_costs[
                "perimeter_bias_max_cost"
            ],
        ),
        route_rules=route_rules,
        always_traversable_room_types=(RoomType.HALLWAY,),
    )

    return ScoringConfig(
        evaluator_rules=(
            EvaluatorRule(
                key=ZONE_SUITABILITY_KEY,
                category=EvaluatorCategory.QUALITY,
                order=10,
                weight=weights["zone_suitability"],
                settings={"zone_config": zone_config},
            ),
            EvaluatorRule(
                key=EXTERIOR_CLEARANCE_KEY,
                category=EvaluatorCategory.QUALITY,
                order=20,
                weight=weights["exterior_clearance"],
                settings={"rules": exterior_rules},
            ),
            EvaluatorRule(
                key=RELATIONSHIP_QUALITY_KEY,
                category=EvaluatorCategory.QUALITY,
                order=30,
                weight=weights["relationship_quality"],
                settings={"routing_config": relationship_config},
            ),
            EvaluatorRule(
                key=SPATIAL_DISTRIBUTION_KEY,
                category=EvaluatorCategory.QUALITY,
                order=40,
                weight=weights["spatial_distribution"],
                settings=section["spatial_distribution"],
            ),
        ),
        fail_fast_on_critical_failure=True,
        not_applicable_quality_contributes=False,
        raise_on_evaluator_error=True,
    )


def make_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Cannot write a non-finite number to result.json.")
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            field.name: make_json_safe(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if hasattr(value, "items"):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list, set, frozenset)):
        return [make_json_safe(item) for item in value]
    raise TypeError(f"Cannot serialize value of type {type(value).__name__}.")


def run() -> dict[str, Any]:
    raw_input = load_input()
    started_at = datetime.now(UTC)
    started_timer = perf_counter()

    print("1/4 Preprocessing realistic floor-plan request...")
    preprocessing = prepare_generation_input(
        build_preprocessing_input(raw_input),
        mode=ExecutionMode.DEBUG,
    )
    prepared = preprocessing.result
    specification_template = prepared.generation_spec

    circulation_config = build_circulation_config(raw_input)
    scoring_config = build_scoring_config(
        raw_input,
        circulation_config.route_rules,
    )
    scoring_registry = create_default_registry()

    def evaluate_search_candidate(candidate: CandidateMap) -> float:
        candidate_specification = prepared.generation_spec_for_candidate(candidate)
        circulation = refine_candidate_circulation(
            CandidateCirculationInput(
                candidate=candidate,
                config=circulation_config,
            ),
            mode=ExecutionMode.PRODUCTION,
        )
        scoring = evaluate_candidate(
            CandidateScoringInput(
                specification=candidate_specification,
                candidate=circulation.result.candidate,
                hallway_classifications=(
                    circulation.result.hallway_classifications
                ),
            ),
            registry=scoring_registry,
            config=scoring_config,
            mode=ExecutionMode.PRODUCTION,
        )
        return scoring.total_score

    print("2/4 Searching candidate maps using circulation + score evaluation...")
    search_data = raw_input["candidate_search"]
    search = search_candidates(
        CandidateSearchInput(
            targets=build_candidate_search_targets(specification_template),
            grid=prepared.candidate_grid,
            hallway_room_count_range=prepared.hallway_room_count_range,
            config=CandidateSearchConfig(
                max_grid_node_count=search_data["max_grid_node_count"],
                trial_count=search_data["trial_count"],
                random_seed=search_data.get("random_seed"),
            ),
            evaluator=evaluate_search_candidate,
        ),
        mode=ExecutionMode.DEBUG,
    )

    candidate_specification = prepared.generation_spec_for_candidate(
        search.result.candidate
    )

    print("3/4 Refining the winning candidate circulation in DEBUG mode...")
    circulation = refine_candidate_circulation(
        CandidateCirculationInput(
            candidate=search.result.candidate,
            config=circulation_config,
        ),
        mode=ExecutionMode.DEBUG,
    )

    print("4/4 Scoring the refined candidate in DEBUG mode...")
    scoring = evaluate_candidate(
        CandidateScoringInput(
            specification=candidate_specification,
            candidate=circulation.result.candidate,
            hallway_classifications=circulation.result.hallway_classifications,
        ),
        registry=scoring_registry,
        config=scoring_config,
        mode=ExecutionMode.DEBUG,
    )

    completed_at = datetime.now(UTC)
    payload = {
        "run": {
            "input_file": INPUT_PATH.name,
            "started_at_utc": started_at.isoformat(),
            "completed_at_utc": completed_at.isoformat(),
            "duration_seconds": perf_counter() - started_timer,
        },
        "summary": {
            "floor_width": specification_template.floor.width,
            "floor_length": specification_template.floor.length,
            "candidate_grid_spacing": prepared.candidate_grid.grid_spacing,
            "candidate_grid_node_count": search.result.candidate.grid.node_count,
            "hallway_room_count_range": prepared.hallway_room_count_range,
            "template_room_count": len(specification_template.rooms),
            "search_trial_count": search.result.completed_trials,
            "search_best_score": search.result.score,
            "search_candidate_room_count": len(search.result.candidate.points),
            "search_hallway_room_count": search.result.hallway_room_count,
            "final_room_count": len(circulation.result.candidate.points),
            "final_hallway_room_count": sum(
                point.room_type is RoomType.HALLWAY
                for point in circulation.result.candidate.points
            ),
            "removed_hallway_point_count": len(
                circulation.details.removed_hallway_points
                if circulation.details is not None
                else ()
            ),
            "final_candidate_score": scoring.total_score,
            "passed_critical_checks": scoring.passed_critical_checks,
        },
        "preprocessing": preprocessing,
        "candidate_search": search,
        "candidate_circulation": circulation,
        "candidate_specific_generation_spec": candidate_specification,
        "candidate_scoring": scoring,
    }
    return make_json_safe(payload)


def main() -> None:
    payload = run()
    with RESULT_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")

    summary = payload["summary"]
    print(f"Saved: {RESULT_PATH}")
    print(
        "Final score: "
        f"{summary['final_candidate_score']:.3f} | "
        f"Best search score: {summary['search_best_score']:.3f}"
    )


if __name__ == "__main__":
    main()
