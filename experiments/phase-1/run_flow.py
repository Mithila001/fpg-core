from __future__ import annotations

import argparse
import dataclasses
import json
import math
import traceback
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE.parent / "outputs" / "phase-1"


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(key.value if isinstance(key, Enum) else key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [jsonable(item) for item in value]
    return repr(value)


def run(target_score: float, max_trials: int) -> dict[str, Any]:
    from scenario import (
        build_candidate_circulation_config,
        build_candidate_scoring_config,
        build_candidate_search_config,
        build_preprocessing_config,
        build_preprocessing_request,
    )

    from fpg_core import __version__
    from fpg_core.candidate_circulation import (
        CandidateCirculationInput,
        refine_candidate_circulation,
    )
    from fpg_core.candidate_scoring import (
        CandidateScoringInput,
        create_default_registry,
        evaluate_candidate,
    )
    from fpg_core.candidate_search import (
        CandidateSearchInput,
        CandidateSearchSession,
        build_candidate_search_targets,
    )
    from fpg_core.domain import ExecutionMode
    from fpg_core.floor_plan_preprocessing import (
        PreprocessingInput,
        prepare_generation_input,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rounds = [int(path.stem.split("_")[-1]) for path in OUTPUT_DIR.glob("phase-1_*.json")]
    output_path = OUTPUT_DIR / f"phase-1_{max(rounds, default=0) + 1}.json"
    payload: dict[str, Any] = {
        "test_type": "phase-1",
        "started_at_utc": datetime.now(UTC).isoformat(),
        "status": "running",
        "fpg_core_version": __version__,
        "target_score": target_score,
        "max_trials": max_trials,
        "steps": [],
        "candidate_trials": [],
        "errors": [],
        "visualization": {"candidate": None},
    }

    def save() -> None:
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    try:
        preprocessing = prepare_generation_input(
            PreprocessingInput(
                request=build_preprocessing_request(180.0, 160.0),
                config=build_preprocessing_config(),
            ),
            mode=ExecutionMode.DEBUG,
        )
        prepared = preprocessing.result
        payload["steps"].append({"name": "preprocessing", "execution": jsonable(preprocessing)})

        circulation_config = build_candidate_circulation_config()
        scoring_config = build_candidate_scoring_config()
        registry = create_default_registry()

        def score_candidate(candidate) -> float:
            entry = {
                "trial": len(payload["candidate_trials"]) + 1,
                "search_candidate": {"points": jsonable(candidate.points)},
            }
            try:
                circulation_execution = refine_candidate_circulation(
                    CandidateCirculationInput(candidate=candidate, config=circulation_config),
                    mode=ExecutionMode.DEBUG,
                )
                circulation = circulation_execution.result
                entry.update({
                    "candidate": {"points": jsonable(circulation.candidate.points)},
                    "circulation_details": jsonable(circulation_execution.details),
                    "hallway_classifications": jsonable(circulation.hallway_classifications),
                })
                specification = prepared.generation_spec_for_candidate(circulation.candidate)
                result = evaluate_candidate(
                    CandidateScoringInput(
                        specification=specification,
                        candidate=circulation.candidate,
                        hallway_classifications=circulation.hallway_classifications,
                    ),
                    registry=registry,
                    config=scoring_config,
                    mode=ExecutionMode.DEBUG,
                )
                entry.update({
                    "status": "scored",
                    "score": result.total_score,
                    "passed_critical_checks": result.passed_critical_checks,
                    "evaluators": jsonable(result.evaluator_results),
                })
            except Exception as exc:
                entry.update({"status": "rejected", "score": 0.0, "error": {"type": type(exc).__name__, "message": str(exc)}})
            payload["candidate_trials"].append(entry)
            save()
            return float(entry["score"])

        search_config = dataclasses.replace(
            build_candidate_search_config(), trial_count=max_trials
        )
        session = CandidateSearchSession(CandidateSearchInput(
            targets=build_candidate_search_targets(prepared.generation_spec),
            grid=prepared.candidate_grid,
            hallway_room_count_range=prepared.hallway_room_count_range,
            evaluator=score_candidate,
            config=search_config,
        ))
        while session.has_remaining_trials:
            trial = session.run_next_trial()
            if trial.score >= target_score:
                break

        best = session.best_result()
        payload["steps"].append({
            "name": "candidate_search_circulation_scoring",
            "completed_trials": session.completed_trials,
            "best_score": best.score,
            "target_reached": best.score >= target_score,
        })
        best_trial = max(payload["candidate_trials"], key=lambda item: item["score"])
        payload["visualization"]["candidate"] = {
            "candidate": best_trial["candidate"],
            "grid": jsonable(prepared.candidate_grid),
            "score": best.score,
        }
        payload["status"] = "target_reached" if best.score >= target_score else "trial_limit_reached"
    except Exception as exc:
        payload["status"] = "failed"
        payload["errors"].append({"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})

    payload["completed_at_utc"] = datetime.now(UTC).isoformat()
    payload["output_file"] = str(output_path)
    save()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run preprocessing through candidate scoring until the target score is reached.")
    parser.add_argument("--target-score", type=float, default=100.0, help="Candidate score to stop at (0 to 100).")
    parser.add_argument("--max-trials", type=int, default=500, help="Maximum candidate trials if the target is not reached.")
    args = parser.parse_args()
    if not 0 <= args.target_score <= 100:
        parser.error("--target-score must be between 0 and 100")
    if args.max_trials < 1:
        parser.error("--max-trials must be at least 1")
    payload = run(args.target_score, args.max_trials)
    print(f"Status: {payload['status']} | trials: {len(payload['candidate_trials'])} | best: {payload.get('steps', [{}])[-1].get('best_score', 'n/a')}")
    print(f"Output: {payload['output_file']}")
    return 0 if payload["status"] == "target_reached" else 1


if __name__ == "__main__":
    raise SystemExit(main())
