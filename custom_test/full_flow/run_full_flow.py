from __future__ import annotations

import argparse
import dataclasses
import json
import math
import re
import sys
import traceback
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, TypeVar

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
SRC_DIR = PROJECT_ROOT / "src"
OUTPUT_DIR = PROJECT_ROOT / "custom_test" / "outputs"
if SRC_DIR.is_dir() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fpg_core import __version__ as FPG_CORE_VERSION
from fpg_core.buildable_land import BuildableLandInput, calculate_buildable_land
from fpg_core.candidate_circulation import CandidateCirculationInput, refine_candidate_circulation
from fpg_core.candidate_scoring import CandidateScoringInput, create_default_registry, evaluate_candidate
from fpg_core.candidate_search import CandidateSearchInput, build_candidate_search_targets, search_candidates
from fpg_core.domain import ExecutionMode, OpeningPurpose, OpeningType, RoomType, RoomWidthAxis
from fpg_core.floor_plan_preprocessing import (
    FloorLimits,
    PreprocessingInput,
    PreprocessingRequest,
    RequestedRoom,
    prepare_generation_input,
)
from fpg_core.usable_land import UsableLandInput, find_usable_land

from scenario import (
    PROJECT_UNITS_PER_METER,
    TEST_TYPE,
    build_buildable_land_config,
    build_candidate_circulation_config,
    build_candidate_scoring_config,
    build_candidate_search_config,
    build_final_scoring_config,
    build_land_request,
    build_opening_config,
    build_preprocessing_config,
    build_route_rules,
    build_solver_profiles,
    build_usable_land_config,
)

T = TypeVar("T")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_key(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {json_key(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return [to_jsonable(item) for item in sorted(value, key=str)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_jsonable(item) for item in value]
    return repr(value)


def next_round_number(output_dir: Path, test_type: str) -> int:
    pattern = re.compile(rf"^{re.escape(test_type)}_(\d+)\.json$")
    found = []
    if output_dir.exists():
        for path in output_dir.iterdir():
            match = pattern.match(path.name)
            if match:
                found.append(int(match.group(1)))
    return max(found, default=0) + 1


def resolve_output_path(round_number: int | None) -> tuple[int, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    round_number = round_number or next_round_number(OUTPUT_DIR, TEST_TYPE)
    output_path = OUTPUT_DIR / f"{TEST_TYPE}_{round_number}.json"
    if output_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing output: {output_path}. "
            "Choose another --round value or omit --round for automatic numbering."
        )
    return round_number, output_path


def write_output(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def record_step(
    payload: dict[str, Any],
    name: str,
    operation: Callable[[], T],
) -> T:
    started = utc_now()
    started_clock = perf_counter()
    try:
        result = operation()
    except Exception as exc:
        payload["steps"].append(
            {
                "name": name,
                "status": "failed",
                "started_at_utc": started,
                "completed_at_utc": utc_now(),
                "duration_seconds": perf_counter() - started_clock,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
        )
        raise
    payload["steps"].append(
        {
            "name": name,
            "status": "completed",
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "duration_seconds": perf_counter() - started_clock,
            "execution": to_jsonable(result),
        }
    )
    return result


def build_preprocessing_request(usable_land) -> PreprocessingRequest:
    return PreprocessingRequest(
        floor_limits=FloorLimits(
            max_width=float(usable_land.width),
            max_length=float(usable_land.length),
        ),
        aspect_ratio="1:1",
        rooms=(
            RequestedRoom(RoomType.BEDROOM, id="bedroom-1", name="Bedroom 1", requested_size="regular"),
            RequestedRoom(RoomType.BEDROOM, id="bedroom-2", name="Bedroom 2", requested_size="regular"),
            RequestedRoom(RoomType.BATHROOM, id="bathroom-1", name="Common Bathroom", requested_size="regular"),
            RequestedRoom(RoomType.LIVING_ROOM, id="living-room-1", name="Living Room", requested_size="regular"),
            RequestedRoom(RoomType.KITCHEN, id="kitchen-1", name="Kitchen", requested_size="regular"),
            RequestedRoom(RoomType.DINING_ROOM, id="dining-room-1", name="Dining Room", requested_size="regular"),
            RequestedRoom(RoomType.VERANDA, id="veranda-1", name="Front Veranda", requested_size="regular"),
        ),
    )


def evaluator_summary(result) -> dict[str, Any]:
    return {
        "total_score": result.total_score,
        "passed_critical_checks": result.passed_critical_checks,
        "stopped_early": result.stopped_early,
        "stop_reason": result.stop_reason,
        "evaluators": [
            {
                "key": str(item.evaluator_key),
                "status": item.status.value,
                "raw_score": item.raw_score,
                "contribution": item.contribution,
            }
            for item in result.evaluator_results
        ],
    }


def polygon_bounds(points) -> tuple[float, float, float, float]:
    xs = [float(point.x) for point in points]
    ys = [float(point.y) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def rectangle_shared_wall_length(room_a, room_b, tolerance: float = 1e-6) -> float:
    ax1, ay1, ax2, ay2 = polygon_bounds(room_a.boundary.points)
    bx1, by1, bx2, by2 = polygon_bounds(room_b.boundary.points)
    shared = 0.0
    if abs(ax2 - bx1) <= tolerance or abs(bx2 - ax1) <= tolerance:
        shared = max(shared, max(0.0, min(ay2, by2) - max(ay1, by1)))
    if abs(ay2 - by1) <= tolerance or abs(by2 - ay1) <= tolerance:
        shared = max(shared, max(0.0, min(ax2, bx2) - max(ax1, bx1)))
    return shared


def geometry_validations(floor_plan, specification) -> list[dict[str, Any]]:
    validations: list[dict[str, Any]] = []
    fx1, fy1, fx2, fy2 = polygon_bounds(floor_plan.boundary.points)
    tolerance = 1e-6

    outside: list[str] = []
    overlaps: list[tuple[str, str]] = []
    room_bounds = {}
    for room in floor_plan.rooms:
        bounds = polygon_bounds(room.boundary.points)
        room_bounds[str(room.id)] = bounds
        x1, y1, x2, y2 = bounds
        if x1 < fx1 - tolerance or y1 < fy1 - tolerance or x2 > fx2 + tolerance or y2 > fy2 + tolerance:
            outside.append(str(room.id))

    for index, room_a in enumerate(floor_plan.rooms):
        ax1, ay1, ax2, ay2 = room_bounds[str(room_a.id)]
        for room_b in floor_plan.rooms[index + 1 :]:
            bx1, by1, bx2, by2 = room_bounds[str(room_b.id)]
            overlap_x = min(ax2, bx2) - max(ax1, bx1)
            overlap_y = min(ay2, by2) - max(ay1, by1)
            if overlap_x > tolerance and overlap_y > tolerance:
                overlaps.append((str(room_a.id), str(room_b.id)))

    size_specs = {str(room.id): room.size for room in specification.rooms}
    size_violations: list[dict[str, Any]] = []
    for room in floor_plan.rooms:
        size = size_specs.get(str(room.id))
        if size is None:
            continue
        x1, y1, x2, y2 = room_bounds[str(room.id)]
        width = x2 - x1
        length = y2 - y1
        area = width * length
        short_side = min(width, length)
        min_dimension_ok = width >= size.min_width - tolerance and length >= size.min_width - tolerance
        if size.width_axis is RoomWidthAxis.X:
            max_dimension_ok = width <= size.max_width + tolerance
        elif size.width_axis is RoomWidthAxis.Y:
            max_dimension_ok = length <= size.max_width + tolerance
        else:
            max_dimension_ok = short_side <= size.max_width + tolerance
        area_ok = size.min_area - tolerance <= area <= size.max_area + tolerance
        if not (min_dimension_ok and max_dimension_ok and area_ok):
            size_violations.append(
                {
                    "room_id": str(room.id),
                    "width": width,
                    "length": length,
                    "area": area,
                    "min_width": size.min_width,
                    "max_width": size.max_width,
                    "width_axis": size.width_axis.value,
                    "min_area": size.min_area,
                    "max_area": size.max_area,
                }
            )

    hallways = [room for room in floor_plan.rooms if room.room_type is RoomType.HALLWAY]
    hallway_wall_violations: list[dict[str, Any]] = []
    for index, room_a in enumerate(hallways):
        for room_b in hallways[index + 1 :]:
            shared = rectangle_shared_wall_length(room_a, room_b)
            if shared > 12.0 + tolerance:
                hallway_wall_violations.append(
                    {
                        "room_a": str(room_a.id),
                        "room_b": str(room_b.id),
                        "shared_wall": shared,
                        "maximum": 12.0,
                    }
                )

    validations.extend(
        (
            {
                "name": "rooms_inside_floor",
                "status": "passed" if not outside else "failed",
                "details": {"outside_room_ids": outside},
            },
            {
                "name": "room_non_overlap",
                "status": "passed" if not overlaps else "failed",
                "details": {"overlapping_room_pairs": overlaps},
            },
            {
                "name": "room_size_bounds",
                "status": "passed" if not size_violations else "failed",
                "details": {"violations": size_violations},
            },
            {
                "name": "hallway_shared_wall_limit",
                "status": "passed" if not hallway_wall_violations else "failed",
                "details": {"violations": hallway_wall_violations, "maximum_shared_wall": 12.0},
            },
        )
    )
    return validations


def run(round_number: int | None = None) -> tuple[dict[str, Any], Path]:
    round_number, output_path = resolve_output_path(round_number)
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "test_type": TEST_TYPE,
        "test_round": round_number,
        "fpg_core_version": FPG_CORE_VERSION,
        "project_units_per_meter": PROJECT_UNITS_PER_METER,
        "started_at_utc": utc_now(),
        "completed_at_utc": None,
        "status": "running",
        "output_file": str(output_path),
        "scenario": {},
        "steps": [],
        "candidate_trials": [],
        "validations": [],
        "visualization": {
            "candidate": None,
            "floor_plans": {},
        },
        "errors": [],
    }
    write_output(output_path, payload)

    try:
        buildable_config = build_buildable_land_config()
        usable_config = build_usable_land_config()
        preprocessing_config = build_preprocessing_config()
        circulation_config = build_candidate_circulation_config()
        candidate_scoring_config = build_candidate_scoring_config()
        candidate_search_config = build_candidate_search_config()
        solver_profiles = build_solver_profiles()
        opening_config = build_opening_config()
        final_scoring_config = build_final_scoring_config()
        land_request = build_land_request()

        payload["scenario"] = {
            "land_request": to_jsonable(land_request),
            "buildable_land_config": to_jsonable(buildable_config),
            "usable_land_config": to_jsonable(usable_config),
            "preprocessing_config": to_jsonable(preprocessing_config),
            "candidate_search_config": to_jsonable(candidate_search_config),
            "candidate_circulation_config": to_jsonable(circulation_config),
            "candidate_scoring_config": to_jsonable(candidate_scoring_config),
            "solver_profiles": to_jsonable(solver_profiles),
            "opening_config": to_jsonable(opening_config),
            "final_scoring_config": to_jsonable(final_scoring_config),
            "route_rules": to_jsonable(build_route_rules()),
        }
        write_output(output_path, payload)

        buildable_execution = record_step(
            payload,
            "buildable_land",
            lambda: calculate_buildable_land(
                BuildableLandInput(request=land_request, config=buildable_config),
                mode=ExecutionMode.DEBUG,
            ),
        )
        write_output(output_path, payload)

        usable_execution = record_step(
            payload,
            "usable_land",
            lambda: find_usable_land(
                UsableLandInput(
                    buildable_land=buildable_execution.result.buildable_land,
                    land=buildable_execution.result.normalized_land,
                    config=usable_config,
                ),
                mode=ExecutionMode.DEBUG,
            ),
        )
        write_output(output_path, payload)

        preprocessing_request = build_preprocessing_request(usable_execution.result)
        payload["scenario"]["preprocessing_request"] = to_jsonable(preprocessing_request)
        preprocessing_execution = record_step(
            payload,
            "preprocessing",
            lambda: prepare_generation_input(
                PreprocessingInput(
                    request=preprocessing_request,
                    config=preprocessing_config,
                ),
                mode=ExecutionMode.DEBUG,
            ),
        )
        prepared = preprocessing_execution.result
        write_output(output_path, payload)

        candidate_registry = create_default_registry()
        trial_counter = 0

        def search_evaluator(candidate) -> float:
            nonlocal trial_counter
            trial_counter += 1
            record: dict[str, Any] = {
                "trial": trial_counter,
                "input_hallway_count": sum(
                    point.room_type is RoomType.HALLWAY for point in candidate.points
                ),
            }
            try:
                circulation_execution = refine_candidate_circulation(
                    CandidateCirculationInput(candidate=candidate, config=circulation_config),
                    mode=ExecutionMode.PRODUCTION,
                )
                cleaned = circulation_execution.result
                candidate_spec = prepared.generation_spec_for_candidate(cleaned.candidate)
                scoring_result = evaluate_candidate(
                    CandidateScoringInput(
                        specification=candidate_spec,
                        candidate=cleaned.candidate,
                        hallway_classifications=cleaned.hallway_classifications,
                    ),
                    registry=candidate_registry,
                    config=candidate_scoring_config,
                    mode=ExecutionMode.PRODUCTION,
                )
                record.update(
                    {
                        "status": "scored",
                        "output_hallway_count": sum(
                            point.room_type is RoomType.HALLWAY
                            for point in cleaned.candidate.points
                        ),
                        "score": scoring_result.total_score,
                        "passed_critical_checks": scoring_result.passed_critical_checks,
                    }
                )
                return float(scoring_result.total_score)
            except Exception as exc:
                record.update(
                    {
                        "status": "rejected_by_evaluator",
                        "score": 0.0,
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                        },
                    }
                )
                return 0.0
            finally:
                payload["candidate_trials"].append(record)

        search_execution = record_step(
            payload,
            "candidate_search",
            lambda: search_candidates(
                CandidateSearchInput(
                    targets=build_candidate_search_targets(prepared.generation_spec),
                    grid=prepared.candidate_grid,
                    hallway_room_count_range=prepared.hallway_room_count_range,
                    evaluator=search_evaluator,
                    config=candidate_search_config,
                ),
                mode=ExecutionMode.DEBUG,
            ),
        )
        write_output(output_path, payload)

        selected_circulation = record_step(
            payload,
            "selected_candidate_circulation",
            lambda: refine_candidate_circulation(
                CandidateCirculationInput(
                    candidate=search_execution.result.candidate,
                    config=circulation_config,
                ),
                mode=ExecutionMode.DEBUG,
            ),
        )
        selected_candidate = selected_circulation.result.candidate
        selected_spec = prepared.generation_spec_for_candidate(selected_candidate)
        payload["visualization"]["candidate"] = {
            "grid": to_jsonable(selected_candidate.grid),
            "candidate": to_jsonable(selected_candidate),
            "circulation_details": to_jsonable(selected_circulation.details),
            "hallway_classifications": to_jsonable(
                selected_circulation.result.hallway_classifications
            ),
        }
        write_output(output_path, payload)

        selected_candidate_score = record_step(
            payload,
            "selected_candidate_scoring",
            lambda: evaluate_candidate(
                CandidateScoringInput(
                    specification=selected_spec,
                    candidate=selected_candidate,
                    hallway_classifications=selected_circulation.result.hallway_classifications,
                ),
                registry=candidate_registry,
                config=candidate_scoring_config,
                mode=ExecutionMode.DEBUG,
            ),
        )
        payload["selected_candidate_score"] = evaluator_summary(selected_candidate_score)
        write_output(output_path, payload)

        # Import OR-Tools-backed features only when the flow reaches them. Keeping
        # this import inside the recorded stage means dependency/import failures are
        # visible as an initial_generation failure in the output JSON.
        def run_initial_generation():
            from fpg_core.floor_plan_solver import (
                FloorPlanSolveRequest,
                RoomPlacementHint,
                generate_floor_plan,
            )

            candidate_hints = tuple(
                RoomPlacementHint(room_id=point.room_id, x=point.x, y=point.y)
                for point in selected_candidate.points
            )
            return generate_floor_plan(
                FloorPlanSolveRequest(
                    specification=selected_spec,
                    candidate_hints=candidate_hints,
                    config=solver_profiles.initial,
                ),
                mode=ExecutionMode.DEBUG,
            )

        initial_execution = record_step(
            payload,
            "initial_generation",
            run_initial_generation,
        )

        from fpg_core.floor_plan_solver import FloorPlanSolveRequest, generate_floor_plan
        if not initial_execution.result.solved:
            raise RuntimeError(
                "Initial solver did not produce a floor plan: "
                f"{initial_execution.result.status.value}: {initial_execution.result.message}"
            )
        floor_plan = initial_execution.result.floor_plan
        payload["visualization"]["floor_plans"]["initial_generation"] = to_jsonable(floor_plan)
        write_output(output_path, payload)

        refinement_a_execution = record_step(
            payload,
            "refinement_a",
            lambda: generate_floor_plan(
                FloorPlanSolveRequest(
                    specification=selected_spec,
                    existing_floor_plan=floor_plan,
                    config=solver_profiles.refinement_a,
                ),
                mode=ExecutionMode.DEBUG,
            ),
        )
        if not refinement_a_execution.result.solved:
            raise RuntimeError(
                "Refinement A did not produce a floor plan: "
                f"{refinement_a_execution.result.status.value}: {refinement_a_execution.result.message}"
            )
        floor_plan = refinement_a_execution.result.floor_plan
        payload["visualization"]["floor_plans"]["refinement_a"] = to_jsonable(floor_plan)
        write_output(output_path, payload)

        refinement_b_execution = record_step(
            payload,
            "refinement_b",
            lambda: generate_floor_plan(
                FloorPlanSolveRequest(
                    specification=selected_spec,
                    existing_floor_plan=floor_plan,
                    config=solver_profiles.refinement_b,
                ),
                mode=ExecutionMode.DEBUG,
            ),
        )
        if not refinement_b_execution.result.solved:
            raise RuntimeError(
                "Refinement B did not produce a floor plan: "
                f"{refinement_b_execution.result.status.value}: {refinement_b_execution.result.message}"
            )
        floor_plan = refinement_b_execution.result.floor_plan
        payload["visualization"]["floor_plans"]["refinement_b"] = to_jsonable(floor_plan)
        write_output(output_path, payload)

        from fpg_core.floor_plan_post_processing import (
            INITIAL_GENERATION_PROFILE as POST_PROCESSING_CONFIG,
            PostProcessingRequest,
            post_process_floor_plan,
        )

        post_processing_execution = record_step(
            payload,
            "post_processing",
            lambda: post_process_floor_plan(
                PostProcessingRequest(
                    floor_plan=floor_plan,
                    specification=selected_spec,
                    config=POST_PROCESSING_CONFIG,
                ),
                mode=ExecutionMode.DEBUG,
            ),
        )
        if post_processing_execution.result.status.value != "success":
            failure = post_processing_execution.result.failure
            message = failure.message if failure is not None else "unknown post-processing failure"
            raise RuntimeError(f"Post-processing failed: {message}")
        floor_plan = post_processing_execution.result.floor_plan
        payload["visualization"]["floor_plans"]["post_processing"] = to_jsonable(floor_plan)
        write_output(output_path, payload)

        from fpg_core.floor_plan_openings import OpeningGenerationRequest, generate_openings

        openings_execution = record_step(
            payload,
            "openings",
            lambda: generate_openings(
                OpeningGenerationRequest(
                    floor_plan=floor_plan,
                    config=opening_config,
                ),
                mode=ExecutionMode.DEBUG,
            ),
        )
        if not openings_execution.result.solved:
            raise RuntimeError(
                "Opening generation did not produce a floor plan: "
                f"{openings_execution.result.status.value}: {openings_execution.result.message}"
            )
        floor_plan = openings_execution.result.floor_plan
        payload["visualization"]["floor_plans"]["openings"] = to_jsonable(floor_plan)
        write_output(output_path, payload)

        from fpg_core.floor_plan_scoring import FloorPlanScoringInput, score_floor_plan

        final_scoring_execution = record_step(
            payload,
            "final_scoring",
            lambda: score_floor_plan(
                FloorPlanScoringInput(
                    floor_plan=floor_plan,
                    specification=selected_spec,
                    config=final_scoring_config,
                ),
                mode=ExecutionMode.DEBUG,
            ),
        )
        payload["visualization"]["floor_plans"]["final"] = to_jsonable(floor_plan)

        payload["validations"].extend(geometry_validations(floor_plan, selected_spec))
        final_score = final_scoring_execution.result
        payload["validations"].extend(
            (
                {
                    "name": "final_scoring_critical_checks",
                    "status": "passed" if final_score.passed_critical else "failed",
                    "details": {
                        "total_score": final_score.total_score,
                        "critical_failure": to_jsonable(final_score.critical_failure),
                    },
                },
                {
                    "name": "opening_main_entrance",
                    "status": "passed"
                    if sum(
                        opening.opening_type is OpeningType.DOOR
                        and opening.purpose is OpeningPurpose.MAIN_ENTRANCE
                        for opening in floor_plan.openings
                    )
                    == 1
                    else "failed",
                    "details": {
                        "main_entrance_count": sum(
                            opening.opening_type is OpeningType.DOOR
                            and opening.purpose is OpeningPurpose.MAIN_ENTRANCE
                            for opening in floor_plan.openings
                        ),
                        "opening_count": len(floor_plan.openings),
                    },
                },
            )
        )

        failed_validations = [
            item["name"] for item in payload["validations"] if item["status"] != "passed"
        ]
        payload["status"] = "completed" if not failed_validations else "completed_with_validation_failures"
        payload["completed_at_utc"] = utc_now()
        write_output(output_path, payload)
        return payload, output_path

    except Exception as exc:
        payload["status"] = "failed"
        payload["completed_at_utc"] = utc_now()
        payload["errors"].append(
            {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        write_output(output_path, payload)
        return payload, output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the fpg-core package-only full-flow manual verification."
    )
    parser.add_argument(
        "--round",
        type=int,
        default=None,
        help="Optional explicit round number. By default the next available number is used.",
    )
    args = parser.parse_args()
    if args.round is not None and args.round < 1:
        parser.error("--round must be at least 1")

    payload, output_path = run(args.round)
    print(f"Output: {output_path}")
    print(f"Status: {payload['status']}")
    if payload["errors"]:
        print(f"Error: {payload['errors'][-1]['message']}")
    print(f"Viewer: {HERE / 'viewer.html'}")
    return 0 if payload["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
