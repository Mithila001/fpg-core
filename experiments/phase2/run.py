from __future__ import annotations

import json
import math
import time
from dataclasses import replace
from pathlib import Path

from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    EvaluatorCategory,
    EvaluatorKey,
    EvaluatorRule,
    ScoringConfig,
    create_default_registry,
    evaluate_candidate,
)
from fpg_core.candidate_search import (
    CandidateSearchConfig,
    CandidateSearchInput,
    CandidateSearchSession,
    CandidateSearchTarget,
)
from fpg_core.domain import (
    CandidateMap,
    CandidatePoint,
    FloorPlanGenerationSpec,
    FloorSpec,
    HallwayRoomCountRange,
    ResolvedCandidateGrid,
    RoomId,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)
from fpg_core.floor_plan_solver import (
    INITIAL_GENERATION_PROFILE,
    FloorPlanSolveRequest,
    RoomPlacementHint,
    SeedPolicy,
    SeedSource,
    SolverConfig,
    generate_floor_plan,
)


def setup():
    kinds = [
        RoomType.LIVING_ROOM,
        RoomType.KITCHEN,
        RoomType.DINING_ROOM,
        RoomType.BEDROOM,
        RoomType.HALLWAY,
    ]
    rooms = tuple(
        RoomSpec(
            RoomId(f"room_{i}"),
            kind,
            kind.value,
            RoomSizeSpec(10, 40, 400, 900 if kind is not RoomType.HALLWAY else 40000),
        )
        for i, kind in enumerate(kinds)
    )
    spec = FloorPlanGenerationSpec(FloorSpec(200, 200), rooms, ())
    axis = tuple(range(0, 201, 10))
    grid = ResolvedCandidateGrid(axis, axis)
    targets = tuple(CandidateSearchTarget(room.id, room.room_type) for room in rooms)
    return spec, rooms, grid, targets


def scorer(spec, objective):
    key = "spatial_distribution" if objective == "distribution" else "spatial_occupancy"
    rule = EvaluatorRule(EvaluatorKey(key), EvaluatorCategory.QUALITY, settings={})
    config = ScoringConfig((rule,))
    registry = create_default_registry()

    def evaluate(candidate):
        return evaluate_candidate(
            CandidateScoringInput(spec, candidate), registry=registry, config=config
        ).total_score

    return evaluate, config, registry


def physical_metrics(spec, candidate):
    result = evaluate_candidate(
        CandidateScoringInput(spec, candidate),
        registry=create_default_registry(),
        config=ScoringConfig(
            (
                EvaluatorRule(
                    EvaluatorKey("spatial_occupancy"), EvaluatorCategory.QUALITY
                ),
            )
        ),
    ).evaluator_results[0]
    return result.raw_score


def run_one(spec, rooms, grid, targets, objective, seed, count):
    evaluate, _, _ = scorer(spec, objective)
    session = CandidateSearchSession(
        CandidateSearchInput(
            targets,
            grid,
            HallwayRoomCountRange(maximum=1),
            evaluate,
            CandidateSearchConfig(trial_count=count, random_seed=seed),
        )
    )
    started = time.perf_counter()
    scores, physical = [], []
    while session.has_remaining_trials:
        suggestion = session.ask_next_trial()
        score = evaluate(suggestion.candidate)
        session.record_score(suggestion, score)
        scores.append(score)
        physical.append(physical_metrics(spec, suggestion.candidate))
    elapsed = time.perf_counter() - started
    best = session.best_result()
    return {
        "objective": objective,
        "seed": seed,
        "trials": count,
        "elapsed_seconds": elapsed,
        "seconds_per_trial": elapsed / count,
        "mean_search_score": sum(scores) / len(scores),
        "best_search_score": best.score,
        "mean_occupancy_score": sum(physical) / len(physical),
        "best_occupancy_score": max(physical),
        "best_candidate": [
            {
                "room_id": str(p.room_id),
                "room_type": p.room_type.value,
                "x": p.x,
                "y": p.y,
            }
            for p in best.candidate.points
        ],
    }


def main():
    spec, rooms, grid, targets = setup()
    results = []
    for count in (100, 500):
        for objective in ("distribution", "occupancy"):
            results.append(
                run_one(spec, rooms, grid, targets, objective, 314159, count)
            )
    target = Path(__file__).with_name("results.json")
    target.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(target)
    print(
        json.dumps(
            [
                {
                    k: row[k]
                    for k in (
                        "objective",
                        "trials",
                        "elapsed_seconds",
                        "mean_search_score",
                        "mean_occupancy_score",
                        "best_occupancy_score",
                    )
                }
                for row in results
            ],
            indent=2,
        )
    )
    solver_results = []
    solver_config = replace(
        INITIAL_GENERATION_PROFILE,
        solver=SolverConfig(
            max_time_seconds=5, num_search_workers=1, random_seed=314159
        ),
        seed=SeedPolicy(source=SeedSource.CANDIDATE_HINTS, require_source=True),
    )
    arrangements = {
        "desirable": [(40, 40), (80, 40), (80, 80), (40, 80), (120, 40)],
        "clustered": [(40, 40), (50, 40), (40, 50), (50, 50), (60, 50)],
        "scattered": [(20, 20), (180, 20), (20, 180), (180, 180), (100, 100)],
    }
    for label, positions in arrangements.items():
        candidate = CandidateMap(
            grid,
            tuple(
                CandidatePoint(room.id, *xy, room.room_type)
                for room, xy in zip(rooms, positions, strict=True)
            ),
        )
        score = physical_metrics(spec, candidate)
        hints = tuple(
            RoomPlacementHint(room.id, *xy, position_reference="center")
            for room, xy in zip(rooms, positions, strict=True)
        )
        started = time.perf_counter()
        solved = generate_floor_plan(FloorPlanSolveRequest(spec, solver_config, hints))
        elapsed = time.perf_counter() - started
        actual = []
        if solved.result.floor_plan:
            for room in solved.result.floor_plan.rooms:
                xs = [point.x for point in room.boundary.points]
                ys = [point.y for point in room.boundary.points]
                bounds = (min(xs), min(ys), max(xs), max(ys))
                actual.append(
                    (room.id, (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
                )
        lookup = {str(room_id): (x, y) for room_id, x, y in actual}
        movement = [
            math.hypot(lookup[str(room.id)][0] - x, lookup[str(room.id)][1] - y)
            for room, (x, y) in zip(rooms, positions, strict=True)
            if str(room.id) in lookup
        ]
        solver_results.append(
            {
                "map": label,
                "occupancy_score": score,
                "status": solved.result.status.value,
                "solve_seconds": elapsed,
                "center_movements": movement,
                "mean_center_movement": sum(movement) / len(movement)
                if movement
                else None,
            }
        )
    target.with_name("solver_results.json").write_text(
        json.dumps(solver_results, indent=2) + "\n", encoding="utf-8"
    )
    print("solver checks", json.dumps(solver_results))


if __name__ == "__main__":
    main()
