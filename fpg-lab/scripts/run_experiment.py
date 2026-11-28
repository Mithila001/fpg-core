"""Run a research scenario directly through the Lab, without a browser or HTTP API."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from fpg_lab.core.settings import ROOT
from fpg_lab.database.serialization import row_document
from fpg_lab.runtime import FLOW_SERVICES, LabRuntime
from fpg_lab.services.p01_common import TERMINAL_STATUSES


def sample_request() -> dict[str, Any]:
    return {
        "floor_limits": {"max_width": 180, "max_length": 140},
        "aspect_ratio": "4:3",
        "rooms": [
            {
                "room_type": kind,
                "id": identifier,
                "name": kind.replace("_", " ").title(),
                "requested_size": "medium",
            }
            for kind, identifier in (
                ("living_room", "living_1"),
                ("kitchen", "kitchen_1"),
                ("bedroom", "bedroom_1"),
                ("bathroom", "bathroom_1"),
            )
        ],
    }


def sample_hints() -> dict[str, Any]:
    return {
        "rooms": [
            {"room_id": room_id, "x": x, "y": y}
            for room_id, x, y in (
                ("living_1", 20.5, 23.5),
                ("kitchen_1", 60.5, 23.5),
                ("bedroom_1", 20.5, 73.5),
                ("bathroom_1", 60.5, 73.5),
            )
        ],
        "hallways": [{"x": 40.5, "y": 43.5}],
    }


def collect(runtime: LabRuntime, flow: str, experiment_id: int) -> dict[str, Any]:
    with runtime.database.session_factory() as session:
        from sqlalchemy import func, select

        from fpg_lab.database.models import P01BIteration

        service = FLOW_SERVICES[flow](session)
        experiment = service.get_experiment(experiment_id)
        trials, trial_count = service.list_trials(experiment_id=experiment_id, limit=100, offset=0)
        return {
            "collection_limit": 100,
            "trial_count": trial_count,
            "iteration_count": session.scalar(
                select(func.count())
                .select_from(P01BIteration)
                .where(P01BIteration.experiment_id == experiment_id)
            )
            if flow in ("p01b", "p01c")
            else 0,
            "experiment": row_document(experiment),
            "trials": [row_document(t) for t in trials],
            "iterations": [
                row_document(r)
                for r in session.scalars(
                    select(P01BIteration)
                    .where(P01BIteration.experiment_id == experiment_id)
                    .order_by(P01BIteration.number)
                    .limit(100)
                )
            ]
            if flow in ("p01b", "p01c")
            else [],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow", required=True, choices=tuple(FLOW_SERVICES))
    parser.add_argument("--trial-count", type=int, default=10)
    parser.add_argument(
        "--request", type=Path, help="Custom request JSON; otherwise use the research sample"
    )
    parser.add_argument("--preset-id", type=int, help="Saved P01B hint map preset ID")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--refinement-rounds", type=int, default=0)
    parser.add_argument("--initial-time-limit", type=float, default=5)
    parser.add_argument("--disable-hints", action="store_true")
    parser.add_argument("--random-seed", type=int, help="Override the selected profile solver seed")
    parser.add_argument("--configuration-id", type=int)
    parser.add_argument(
        "--database-url", help="Override the configured database, useful for isolated smoke runs"
    )
    parser.add_argument("--no-debug", action="store_true")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--output", type=Path, default=ROOT / "data/experiment-result.json")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    if args.flow in ("p01b", "p01c") and args.preset_id is None:
        parser.error("--preset-id is required for P01B and P01C")
    try:
        with LabRuntime(database_url=args.database_url) as runtime:
            configuration_id = args.configuration_id
            request = (
                json.loads(args.request.read_text(encoding="utf-8"))
                if args.request
                else sample_request()
            )
            payload = {
                "floor_plan_request": request,
                "system_configuration_id": configuration_id,
                "should_save": not args.no_debug,
            }
            if args.flow in ("p01b", "p01c"):
                payload = {
                    "preset_id": args.preset_id,
                    "system_configuration_id": configuration_id,
                    "iterations": args.iterations,
                    "refinement_rounds": args.refinement_rounds,
                    "initial_time_limit": args.initial_time_limit,
                    "disable_hints": args.disable_hints,
                    "random_seed": args.random_seed,
                }
            else:
                payload["trial_count"] = args.trial_count
            experiment_id = runtime.start_experiment(args.flow, payload)
            deadline = time.monotonic() + args.timeout
            timed_out = False
            while True:
                with runtime.database.session_factory() as session:
                    item = FLOW_SERVICES[args.flow](session).get_experiment(experiment_id)
                    status = item.status
                    if status in TERMINAL_STATUSES:
                        break
                    if time.monotonic() >= deadline:
                        FLOW_SERVICES[args.flow](session).request_termination(experiment_id)
                        timed_out = True
                        break
                time.sleep(0.2)
            # Cooperative cancellation waits for the current core stage; retain its final trace.
            runtime.jobs.shutdown(wait=True)
            result = collect(runtime, args.flow, experiment_id)
            result["timed_out"] = timed_out
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.output.with_suffix(args.output.suffix + ".tmp")
            temporary.write_text(
                json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(args.output)
            experiment = result["experiment"]
            print(
                f"{args.flow.upper()} #{experiment_id}: {experiment['status']} · candidate {experiment['best_candidate_score']} · floor plan {experiment['best_floor_plan_score']}"
            )
            print(f"Result: {args.output}")
            if timed_out or experiment["status"] != "completed":
                if experiment["error_data"]:
                    print(json.dumps(experiment["error_data"], indent=2))
                raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as exc:
        print(f"Experiment failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
