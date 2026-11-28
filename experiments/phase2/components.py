from __future__ import annotations

import json
from pathlib import Path

from fpg_core.candidate_circulation import (
    CandidateCirculationConfig,
    CandidateCirculationInput,
    RoutingCostProfile,
    refine_candidate_circulation,
)
from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    create_default_config,
    create_default_registry,
    evaluate_candidate,
)
from fpg_core.domain import (
    CandidateMap,
    CandidatePoint,
    CirculationRouteRule,
    CirculationTrafficClass,
    ConstraintStrength,
    DestinationSelection,
    ExecutionMode,
    FloorPlanGenerationSpec,
    FloorSpec,
    MatchPolicy,
    ResolvedCandidateGrid,
    RoomId,
    RoomRelationSpec,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)

KINDS = (
    ("living", RoomType.LIVING_ROOM),
    ("kitchen", RoomType.KITCHEN),
    ("dining", RoomType.DINING_ROOM),
    ("bed1", RoomType.BEDROOM),
    ("bed2", RoomType.BEDROOM),
    ("attached", RoomType.ATTACHED_BATHROOM),
    ("bath", RoomType.BATHROOM),
    ("veranda", RoomType.VERANDA),
    ("garage", RoomType.GARAGE),
    ("hall", RoomType.HALLWAY),
)
ROOMS = tuple(
    RoomSpec(
        RoomId(room_id), kind, room_id,
        RoomSizeSpec(10, 30, 400, 900) if kind is not RoomType.HALLWAY
        else RoomSizeSpec(10, 12, 100, 40000),
    )
    for room_id, kind in KINDS
)
SPEC = FloorPlanGenerationSpec(
    FloorSpec(200, 200),
    ROOMS,
    (RoomRelationSpec(RoomId("attached"), (RoomId("bed1"),), MatchPolicy.OR, ConstraintStrength.SOFT),),
)
GRID = ResolvedCandidateGrid(tuple(range(0, 201, 10)), tuple(range(0, 201, 10)))
ROUTING = CandidateCirculationConfig(
    costs=RoutingCostProfile(1.0, 0.35, 0.25, 0.4, 2.0),
    route_rules=(
        CirculationRouteRule(1, "bedroom_to_living", RoomType.BEDROOM, RoomType.LIVING_ROOM, DestinationSelection.LOWEST_COST_MATCH, CirculationTrafficClass.PRIVATE, (RoomType.HALLWAY,), 1.5),
        CirculationRouteRule(2, "bathroom_to_living", RoomType.BATHROOM, RoomType.LIVING_ROOM, DestinationSelection.LOWEST_COST_MATCH, CirculationTrafficClass.PRIVATE, (), 2.0, (RoomType.HALLWAY,)),
        CirculationRouteRule(3, "veranda_to_living", RoomType.VERANDA, RoomType.LIVING_ROOM, DestinationSelection.LOWEST_COST_MATCH, CirculationTrafficClass.PUBLIC, (RoomType.HALLWAY,), 1.0),
        CirculationRouteRule(4, "kitchen_to_dining", RoomType.KITCHEN, RoomType.DINING_ROOM, DestinationSelection.LOWEST_COST_MATCH, CirculationTrafficClass.PUBLIC, (RoomType.HALLWAY, RoomType.LIVING_ROOM), 1.0),
        CirculationRouteRule(5, "attached_to_assigned_bedroom", RoomType.ATTACHED_BATHROOM, RoomType.BEDROOM, DestinationSelection.ASSIGNED_RELATION, CirculationTrafficClass.PRIVATE, (), 1.5, allow_global_transit=False),
    ),
    always_traversable_room_types=(RoomType.HALLWAY,),
    max_routing_passes=3,
)
MAPS = {
    "well_arranged": [(60, 60), (80, 60), (80, 80), (40, 100), (60, 100), (40, 110), (150, 100), (60, 30), (140, 40), (100, 100)],
    "distant_attached_bath": [(60, 60), (80, 60), (80, 80), (40, 100), (60, 100), (150, 150), (150, 100), (60, 30), (140, 40), (100, 100)],
    "blocked_exterior": [(60, 60), (60, 40), (80, 80), (40, 100), (60, 100), (40, 110), (150, 100), (60, 30), (140, 40), (100, 100)],
    "scattered_bedrooms": [(60, 60), (80, 60), (80, 80), (30, 30), (170, 170), (40, 40), (150, 100), (60, 30), (140, 40), (100, 100)],
    "overlapping": [(60, 60), (70, 60), (80, 80), (40, 100), (60, 100), (40, 110), (150, 100), (60, 30), (140, 40), (100, 100)],
    "assigned_bathroom_on_group_edge": [(60, 60), (80, 60), (80, 80), (40, 100), (80, 100), (60, 100), (150, 150), (60, 30), (140, 40), (100, 100)],
}


def evaluate(name, positions):
    candidate = CandidateMap(
        GRID,
        tuple(
            CandidatePoint(room.id, x, y, room.room_type)
            for room, (x, y) in zip(ROOMS, positions, strict=True)
        ),
    )
    try:
        circulation = refine_candidate_circulation(
            CandidateCirculationInput(
                candidate,
                ROUTING,
                room_relations=SPEC.room_relations,
            )
        )
        clean_candidate = circulation.result.candidate
        final_circulation = circulation.result.final_circulation
        route_error = None
    except Exception as exc:
        clean_candidate = candidate
        final_circulation = None
        route_error = f"{type(exc).__name__}: {exc}"
    result = evaluate_candidate(
        CandidateScoringInput(SPEC, clean_candidate, final_circulation=final_circulation),
        registry=create_default_registry(),
        config=create_default_config(),
        mode=ExecutionMode.DEBUG,
    )
    evaluators = {}
    for item in result.evaluator_results:
        evaluators[str(item.evaluator_key)] = {"score": item.raw_score, "details": item.details}
    return {"name": name, "total": result.total_score, "route_error": route_error, "evaluators": evaluators}


if __name__ == "__main__":
    output = [evaluate(name, positions) for name, positions in MAPS.items()]
    path = Path(__file__).with_name("component_results.json")
    path.write_text(json.dumps(output, indent=2, default=lambda value: getattr(value, "value", str(value))) + "\n", encoding="utf-8")
    print(path)
    print(json.dumps([{"map": row["name"], **{key: value["score"] for key, value in row["evaluators"].items()}} for row in output], indent=2))
