from __future__ import annotations

import json
import math
import sys
from dataclasses import fields, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Any

# Permit direct execution from a source checkout without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
if SOURCE_ROOT.is_dir():
    sys.path.insert(0, str(SOURCE_ROOT))

from fpg_core.domain import (  # noqa: E402
    ConstraintStrength,
    ExecutionMode,
    FloorPlan,
    FloorPlanGenerationSpec,
    FloorSpec,
    MatchPolicy,
    RoomId,
    RoomRelationSpec,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)
from fpg_core.floor_plan_openings import (  # noqa: E402
    DEFAULT_OPENING_PROFILE,
    OpeningGenerationRequest,
    generate_openings,
)
from fpg_core.floor_plan_post_processing import (  # noqa: E402
    INITIAL_GENERATION_PROFILE as POST_PROCESSING_PROFILE,
)
from fpg_core.floor_plan_post_processing import (  # noqa: E402
    PipelineStatus,
    PostProcessingRequest,
    post_process_floor_plan,
)
from fpg_core.floor_plan_scoring import (  # noqa: E402
    FloorPlanScoringInput,
    create_default_profile,
    score_floor_plan,
)
from fpg_core.floor_plan_solver import (  # noqa: E402
    INITIAL_GENERATION_PROFILE,
    REFINEMENT_A_PROFILE,
    REFINEMENT_B_PROFILE,
    FloorPlanSolveRequest,
    RoomPlacementHint,
    SolverStatus,
    generate_floor_plan,
)

HERE = Path(__file__).resolve().parent
INPUT_PATH = HERE / "input.json"
RESULT_PATH = HERE / "result.json"


def load_input() -> dict[str, Any]:
    with INPUT_PATH.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError("input.json must contain a JSON object.")
    return value


def build_specification(data: dict[str, Any]) -> FloorPlanGenerationSpec:
    raw = data["generation_specification"]
    rooms = tuple(
        RoomSpec(
            id=RoomId(item["id"]),
            room_type=RoomType(item["room_type"]),
            name=item["name"],
            size=RoomSizeSpec(
                min_width=item["min_width"],
                max_width=item["max_width"],
                min_area=item["min_area"],
                max_area=item["max_area"],
            ),
        )
        for item in raw["rooms"]
    )
    relations = tuple(
        RoomRelationSpec(
            source_room_id=RoomId(item["source_room_id"]),
            target_room_ids=tuple(RoomId(value) for value in item["target_room_ids"]),
            match_policy=MatchPolicy(item["match_policy"]),
            strength=ConstraintStrength(item["strength"]),
        )
        for item in raw.get("relations", [])
    )
    return FloorPlanGenerationSpec(
        floor=FloorSpec(**raw["floor"]),
        rooms=rooms,
        room_relations=relations,
    )


def build_hints(data: dict[str, Any]) -> tuple[RoomPlacementHint, ...]:
    return tuple(
        RoomPlacementHint(
            room_id=RoomId(item["room_id"]),
            x=item["x"],
            y=item["y"],
            width=item.get("width"),
            length=item.get("length"),
        )
        for item in data.get("candidate_hints", [])
    )


def configured_profile(profile: Any, settings: dict[str, Any]) -> Any:
    solver = replace(
        profile.solver,
        max_time_seconds=(
            settings["initial_max_time_seconds"]
            if profile.name == "initial_generation"
            else settings["refinement_max_time_seconds"]
        ),
        random_seed=settings["random_seed"],
        num_search_workers=settings["num_search_workers"],
    )
    return replace(profile, solver=solver)


def require_solved(stage: str, execution: Any) -> FloorPlan:
    if execution.result.status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        raise RuntimeError(
            f"{stage} did not produce a floor plan: "
            f"{execution.result.status.value}: {execution.result.message}"
        )
    floor_plan = execution.result.floor_plan
    if floor_plan is None:
        raise RuntimeError(f"{stage} returned a solved status without a floor plan")
    return floor_plan


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
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [make_json_safe(item) for item in value]
    raise TypeError(f"Cannot serialize value of type {type(value).__name__}.")


def run() -> dict[str, Any]:
    raw = load_input()
    specification = build_specification(raw)
    hints = build_hints(raw)
    solver_settings = raw["solver"]
    started_at = datetime.now(UTC)
    timer = perf_counter()

    print("1/6 Solving with the initial-generation profile...")
    initial = generate_floor_plan(
        FloorPlanSolveRequest(
            specification=specification,
            config=configured_profile(INITIAL_GENERATION_PROFILE, solver_settings),
            candidate_hints=hints,
        ),
        mode=ExecutionMode.DEBUG,
    )
    initial_plan = require_solved("initial_generation", initial)

    print("2/6 Refining with profile A...")
    refinement_a = generate_floor_plan(
        FloorPlanSolveRequest(
            specification=specification,
            config=configured_profile(REFINEMENT_A_PROFILE, solver_settings),
            existing_floor_plan=initial_plan,
        ),
        mode=ExecutionMode.DEBUG,
    )
    refinement_a_plan = require_solved("refinement_a", refinement_a)

    print("3/6 Refining with profile B...")
    refinement_b = generate_floor_plan(
        FloorPlanSolveRequest(
            specification=specification,
            config=configured_profile(REFINEMENT_B_PROFILE, solver_settings),
            existing_floor_plan=refinement_a_plan,
        ),
        mode=ExecutionMode.DEBUG,
    )
    refinement_b_plan = require_solved("refinement_b", refinement_b)

    print("4/6 Post-processing solved geometry...")
    post_processing = post_process_floor_plan(
        PostProcessingRequest(
            floor_plan=refinement_b_plan,
            config=POST_PROCESSING_PROFILE,
            specification=specification,
        ),
        mode=ExecutionMode.DEBUG,
    )
    if post_processing.result.status is not PipelineStatus.SUCCESS:
        failure = post_processing.result.failure
        message = failure.message if failure is not None else "unknown failure"
        raise RuntimeError(f"post-processing failed: {message}")

    print("5/6 Generating doors and windows...")
    openings = generate_openings(
        OpeningGenerationRequest(
            floor_plan=post_processing.result.floor_plan,
            config=DEFAULT_OPENING_PROFILE,
        ),
        mode=ExecutionMode.DEBUG,
    )
    if not openings.result.solved:
        raise RuntimeError(
            "opening generation did not produce a plan: "
            f"{openings.result.status.value}: {openings.result.message}"
        )
    final_plan = openings.result.floor_plan
    if final_plan is None:
        raise RuntimeError("opening generation returned solved without a floor plan")

    print("6/6 Scoring the completed floor plan...")
    scoring = score_floor_plan(
        FloorPlanScoringInput(
            floor_plan=final_plan,
            specification=specification,
            config=create_default_profile(),
        ),
        mode=ExecutionMode.DEBUG,
    )

    completed_at = datetime.now(UTC)
    payload = {
        "run": {
            "input_file": INPUT_PATH.name,
            "started_at_utc": started_at.isoformat(),
            "completed_at_utc": completed_at.isoformat(),
            "duration_seconds": perf_counter() - timer,
        },
        "summary": {
            "initial_status": initial.result.status,
            "refinement_a_status": refinement_a.result.status,
            "refinement_b_status": refinement_b.result.status,
            "post_processing_status": post_processing.result.status,
            "opening_status": openings.result.status,
            "room_count": len(final_plan.rooms),
            "opening_count": len(final_plan.openings),
            "total_score": scoring.result.total_score,
            "passed_critical": scoring.result.passed_critical,
        },
        "generation_specification": specification,
        "initial_solve": initial,
        "refinement_a": refinement_a,
        "refinement_b": refinement_b,
        "post_processing": post_processing,
        "opening_generation": openings,
        "floor_plan_scoring": scoring,
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
        f"Rooms: {summary['room_count']} | Openings: {summary['opening_count']} | "
        f"Score: {summary['total_score']:.3f} | "
        f"Critical checks passed: {summary['passed_critical']}"
    )


if __name__ == "__main__":
    main()
