from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from flows.scenario import (
    build_candidate_circulation_config,
    build_preprocessing_config,
    build_preprocessing_request,
)
from fpg_core.candidate_circulation import (
    CandidateCirculationInput,
    refine_candidate_circulation,
)
from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    create_default_config,
    create_default_registry,
    evaluate_candidate,
)
from fpg_core.domain import CandidateMap, CandidatePoint, ExecutionMode, RoomType
from fpg_core.floor_plan_preprocessing import (
    PreprocessingInput,
    prepare_generation_input,
)
from fpg_core.floor_plan_solver import (
    INITIAL_GENERATION_PROFILE,
    FloorPlanSolveRequest,
    RoomPlacementHint,
    generate_floor_plan,
)


def main():
    prepared = prepare_generation_input(PreprocessingInput(build_preprocessing_request(180, 160), build_preprocessing_config()), mode=ExecutionMode.DEBUG).result
    desired = {
        RoomType.BEDROOM: [(30, 30), (50, 30)],
        RoomType.BATHROOM: [(30, 50)],
        RoomType.LIVING_ROOM: [(70, 50)],
        RoomType.KITCHEN: [(90, 50)],
        RoomType.DINING_ROOM: [(90, 70)],
        RoomType.VERANDA: [(70, 30)],
        RoomType.GARAGE: [(130, 30)],
        RoomType.HALLWAY: [(40, 46), (50, 70), (110, 70), (110, 50)],
    }
    available = {(x, y) for x in prepared.candidate_grid.x_positions for y in prepared.candidate_grid.y_positions if not prepared.candidate_grid.is_edge_node(*prepared.candidate_grid.node_indexes(x, y))}
    points = []
    hallway_count = 0
    for room in prepared.generation_spec.rooms:
        if room.room_type is RoomType.HALLWAY:
            if hallway_count:
                continue
            hallway_count += 1
        options = desired.get(room.room_type, [])
        if not options:
            continue
        target = options.pop(0)
        point = min(available, key=lambda p: (p[0]-target[0])**2 + (p[1]-target[1])**2)
        available.remove(point)
        points.append(CandidatePoint(room.id, *point, room.room_type))
    candidate = CandidateMap(prepared.candidate_grid, tuple(points))
    result = {"spec_room_count": len(prepared.generation_spec.rooms), "candidate_count": len(points), "candidate": [{"room_id": str(p.room_id), "type": p.room_type.value, "x": p.x, "y": p.y} for p in points]}
    try:
        circulation = refine_candidate_circulation(CandidateCirculationInput(candidate, build_candidate_circulation_config(), prepared.generation_spec.room_relations), mode=ExecutionMode.DEBUG)
        result["circulation"] = "completed"
        result["route_count"] = len(circulation.result.final_circulation.routes)
        scoring = evaluate_candidate(CandidateScoringInput(prepared.generation_spec, circulation.result.candidate, final_circulation=circulation.result.final_circulation), registry=create_default_registry(), config=create_default_config(), mode=ExecutionMode.DEBUG)
        result["scores"] = {str(item.evaluator_key): item.raw_score for item in scoring.evaluator_results}
        hints = tuple(RoomPlacementHint(p.room_id, p.x, p.y, position_reference="center") for p in circulation.result.candidate.points)
        profile = INITIAL_GENERATION_PROFILE
        started = time.perf_counter()
        solved = generate_floor_plan(FloorPlanSolveRequest(prepared.generation_spec_for_candidate(circulation.result.candidate), profile, hints), mode=ExecutionMode.DEBUG)
        result["solver"] = {"status": solved.result.status.value, "seconds": time.perf_counter()-started, "message": solved.result.message}
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    path = Path(__file__).with_name("prepared_case.json")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
