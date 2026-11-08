from __future__ import annotations

import json
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Event, Thread
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from fpg_lab.core.exceptions import AppError
from fpg_lab.core.serialization import to_jsonable
from fpg_lab.core.settings import ROOT
from fpg_lab.database.models import P01Experiment
from fpg_lab.flows.p01 import P01FlowRunner, recover_interrupted_experiments, result_document
from fpg_lab.inputs import ManualHints, P01AInput, SystemConfigurationCreate
from fpg_lab.integrations.fpg_core.adapter import FpgCoreAdapter, FpgCoreCandidateRejected
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec
from fpg_lab.integrations.fpg_core.config_models import SystemConfigurationDocument
from fpg_lab.runtime import LabRuntime
from fpg_lab.services.common import SystemConfigurationService
from fpg_lab.services.p01_common import TERMINAL_STATUSES
from fpg_lab.visualization.figures import candidate_map, floor_plan, score_breakdown
from fpg_lab.workers.p01_jobs import P01JobManager
from scripts.run_experiment import collect, sample_hints, sample_request


class Status(StrEnum):
    OPTIMAL = "optimal"


@dataclass
class Execution:
    result: Any
    details: Any = None
    mode: str = "debug"


@dataclass
class CandidateResult:
    candidate: Any


@dataclass
class Score:
    total_score: float
    new_core_diagnostic: str = "retained without a schema change"


@dataclass
class Solve:
    floor_plan: Any
    solved: bool = True
    status: Status = Status.OPTIMAL
    message: str = "solved"


@dataclass
class Post:
    floor_plan: Any
    status: str = "success"


PLAN = {
    "boundary": {
        "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}, {"x": 0, "y": 10}]
    },
    "rooms": [
        {
            "id": "living_1",
            "name": "Living",
            "room_type": "living_room",
            "boundary": {
                "points": [
                    {"x": 0, "y": 0},
                    {"x": 10, "y": 0},
                    {"x": 10, "y": 10},
                    {"x": 0, "y": 10},
                ]
            },
        }
    ],
    "openings": [],
}


class RecordingAdapter(FpgCoreAdapter):
    """Keep real preprocessing/search and isolate expensive solver stages."""

    score = 80.0
    reject = False
    fail_branch = False
    entered: Event | None = None
    release: Event | None = None

    def __init__(self, configuration: Any) -> None:
        super().__init__(configuration)
        self.calls: list[str] = []

    def run_circulation(self, candidate: Any, *, debug: bool) -> Any:
        self.calls.append("circulation")
        if self.entered is not None:
            self.entered.set()
            assert self.release is not None and self.release.wait(5)
        if self.reject:
            raise FpgCoreCandidateRejected(
                "candidate rejected", cause_type="CandidateCirculationError"
            )
        return Execution(CandidateResult(candidate))

    def score_candidate(
        self, specification: Any, circulation_execution: Any, *, debug: bool
    ) -> Any:
        self.calls.append("candidate_score")
        return Score(self.score)

    def solve_initial_floor_plan(self, specification: Any, candidate: Any, *, debug: bool) -> Any:
        self.calls.append("initial")
        if self.fail_branch:
            raise RuntimeError("solver branch failed")
        return Execution(Solve(PLAN))

    def refine_floor_plan(
        self, specification: Any, floor_plan: Any, *, profile: str, debug: bool
    ) -> Any:
        self.calls.append(profile)
        return Execution(Solve(PLAN))

    def post_process_floor_plan(self, specification: Any, floor_plan: Any, *, debug: bool) -> Any:
        self.calls.append("post")
        return Execution(Post(PLAN))

    def generate_floor_plan_openings(self, floor_plan: Any, *, debug: bool) -> Any:
        self.calls.append("openings")
        return Execution(Solve(PLAN))

    def score_completed_floor_plan(
        self, floor_plan: Any, specification: Any, *, debug: bool
    ) -> Any:
        self.calls.append("floor_score")
        return Execution(Score(90.0))


def create_profile(runtime: LabRuntime, *, threshold: float = 79) -> int:
    document = runtime.codec.default_configuration().payload
    document["experiments"]["p01c"]["floor_plan_generation_score_threshold"] = threshold
    with runtime.database.session_factory() as session:
        profile = SystemConfigurationService(session, runtime.codec).create(
            SystemConfigurationCreate(
                name="test", configuration_data=SystemConfigurationDocument.model_validate(document)
            )
        )
        SystemConfigurationService(session, runtime.codec).activate(profile.id)
        return profile.id


def payload(flow: str, *, debug: bool = True) -> dict[str, Any]:
    value = {"floor_plan_request": sample_request(), "should_save": debug}
    if flow == "p01b":
        value["hint_points"] = sample_hints()
    else:
        value["trial_count"] = 2
    return value


def wait(runtime: LabRuntime, flow: str, experiment_id: int) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with runtime.database.session_factory() as session:
            item = session.get(P01Experiment, experiment_id)
            assert item is not None
            if item.status in TERMINAL_STATUSES:
                return collect(runtime, flow, experiment_id)
        time.sleep(0.01)
    raise AssertionError("Experiment did not finish")


def test_current_core_configuration() -> None:
    codec = CoreConfigCodec()
    default = codec.default_configuration()
    seed = json.loads((ROOT / "seed/system_configuration.default.json").read_text(encoding="utf-8"))
    assert codec.validate_payload(seed["configuration_data"]).payload == default.payload
    assert "required_room_access" in default.payload["openings"]["enabled_constraints"]
    assert any(
        rule["key"] == "room_size_consistency"
        for rule in default.payload["floor_plan_scoring"]["evaluators"]
    )
    for flow in ("p01a", "p01b", "p01c"):
        codec.decode_for_flow(default.payload, flow)
    encoded = default.payload
    encoded["openings"]["enabled_constraints"].remove("required_room_access")
    with pytest.raises(Exception, match="required_room_access"):
        codec.validate_payload(encoded)


@pytest.mark.parametrize("flow", ["p01a", "p01c"])
@pytest.mark.parametrize("debug", [True, False])
def test_flows_and_persistence(tmp_path: Path, flow: str, debug: bool) -> None:
    adapters = []

    def factory(configuration: Any) -> RecordingAdapter:
        adapter = RecordingAdapter(configuration)
        adapters.append(adapter)
        return adapter

    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=factory
    ) as runtime:
        profile_id = create_profile(runtime)
        experiment_id = runtime.start_experiment(flow, payload(flow, debug=debug))
        trace = wait(runtime, flow, experiment_id)
        experiment = trace["experiment"]
        assert experiment["status"] == "completed", experiment["error_data"]
        assert experiment["system_configuration_id"] == profile_id
        assert (
            experiment["preprocessing_result"] is not None
            if debug
            else experiment["preprocessing_result"] is None
        )
        if flow != "p01b":
            assert experiment["completed_trial_count"] == 2
            assert experiment["best_candidate_score"] == 80
            assert len(trace["trials"]) == (0 if flow == "p01a" and not debug else 2)
        if flow != "p01a":
            assert experiment["best_floor_plan_score"] == 90
            assert len(trace["floor_plan_runs"]) == (1 if flow == "p01b" else 2)
            assert [
                "initial",
                "refinement_a",
                "refinement_b",
                "post",
                "openings",
                "floor_score",
            ] == adapters[-1].calls[-6:]
        if debug and flow != "p01b":
            assert trace["trials"][0]["candidate_scoring_data"]["new_core_diagnostic"]
        with runtime.database.session_factory() as session:
            profile = SystemConfigurationService(session, runtime.codec).get(profile_id)
            profile.configuration_data = {
                **profile.configuration_data,
                "project_units_per_meter": 20,
            }
            session.commit()
        assert (
            collect(runtime, flow, experiment_id)["experiment"]["system_configuration_snapshot"][
                "project_units_per_meter"
            ]
            == 10
        )


@pytest.mark.parametrize("threshold,fail_branch,count", [(80, False, 0), (79, True, 2)])
def test_threshold_and_branch_failure(
    tmp_path: Path, threshold: float, fail_branch: bool, count: int
) -> None:
    class Adapter(RecordingAdapter):
        pass

    Adapter.fail_branch = fail_branch
    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=Adapter
    ) as runtime:
        create_profile(runtime, threshold=threshold)
        experiment_id = runtime.start_experiment("p01c", payload("p01c"))
        result = wait(runtime, "p01c", experiment_id)
        assert result["experiment"]["status"] == "completed"
        assert result["experiment"]["completed_trial_count"] == 2
        assert len(result["floor_plan_runs"]) == count
        if fail_branch:
            assert all(
                run["status"] == "failed" and run["error_data"] for run in result["floor_plan_runs"]
            )


def test_rejected_candidate(tmp_path: Path) -> None:
    class Adapter(RecordingAdapter):
        reject = True

    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=Adapter
    ) as runtime:
        create_profile(runtime)
        result = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        assert result["experiment"]["best_candidate_score"] == 0
        assert all(t["error_data"]["rejected"] and t["final_score"] == 0 for t in result["trials"])


def test_submission_failure_and_invalid_input(tmp_path: Path) -> None:
    with LabRuntime(database_url=f"sqlite:///{tmp_path / 'lab.db'}") as runtime:
        create_profile(runtime)
        with pytest.raises(ValidationError):
            runtime.start_experiment("p01a", {**payload("p01a"), "trial_count": 0})
        with pytest.raises(ValidationError):
            runtime.start_experiment("p01b", {"preset_id": 1, "initial_time_limit": 1, "iterations": 101})
        with runtime.database.session_factory() as session:
            assert list(session.scalars(select(P01Experiment))) == []
        runtime.jobs.shutdown()
        with pytest.raises(AppError, match="could not be queued"):
            runtime.start_experiment("p01a", payload("p01a"))
        with runtime.database.session_factory() as session:
            item = session.scalar(select(P01Experiment))
            assert item is not None
            assert item.status == "failed" and item.finished_at is not None
            assert item.error_data is not None
            assert item.error_data["stage"] == "job_submission"


def test_termination_and_queued_job(tmp_path: Path) -> None:
    from fpg_lab.services.p01a import P01AService

    class Adapter(RecordingAdapter):
        entered = Event()
        release = Event()

    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=Adapter
    ) as runtime:
        create_profile(runtime)
        first = runtime.start_experiment("p01a", payload("p01a"))
        assert Adapter.entered is not None
        assert Adapter.entered.wait(5)
        second = runtime.start_experiment("p01a", payload("p01a"))
        with runtime.database.session_factory() as session:
            P01AService(session).request_termination(first)
            P01AService(session).request_termination(second)
        assert Adapter.release is not None
        Adapter.release.set()
        assert wait(runtime, "p01a", first)["experiment"]["status"] == "terminated"
        assert wait(runtime, "p01a", second)["experiment"]["status"] == "terminated"


def test_shutdown_terminates_active_and_queued_jobs(tmp_path: Path) -> None:
    class Adapter(RecordingAdapter):
        entered = Event()
        release = Event()

    runtime = LabRuntime(database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=Adapter)
    runtime.start()
    create_profile(runtime)
    first = runtime.start_experiment("p01a", payload("p01a"))
    assert Adapter.entered is not None
    assert Adapter.entered.wait(5)
    second = runtime.start_experiment("p01a", payload("p01a"))
    closer = Thread(target=runtime.close, daemon=True)
    closer.start()
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with runtime.database.session_factory() as session:
                item = session.get(P01Experiment, first)
                assert item is not None
                if item.status == "termination_requested":
                    break
            time.sleep(0.01)
        else:
            pytest.fail("Shutdown did not request cooperative termination")
    finally:
        assert Adapter.release is not None
        Adapter.release.set()
        closer.join(5)
    assert not closer.is_alive()
    assert collect(runtime, "p01a", first)["experiment"]["status"] == "terminated"
    assert collect(runtime, "p01a", second)["experiment"]["status"] == "terminated"
    with pytest.raises(RuntimeError, match="runtime before submitting"):
        runtime.start_experiment("p01a", payload("p01a"))


def test_restart_recovery(tmp_path: Path) -> None:
    from fpg_lab.services.p01a import P01AService

    with LabRuntime(database_url=f"sqlite:///{tmp_path / 'lab.db'}") as runtime:
        create_profile(runtime)
        with runtime.database.session_factory() as session:
            item = P01AService(session, runtime.codec).create_experiment(
                P01AInput.model_validate(payload("p01a"))
            )
            assert recover_interrupted_experiments(session) == 1
            session.refresh(item)
            assert item.status == "interrupted" and item.stop_reason == "lab_restart"


def test_immediate_completion_no_deadlock() -> None:
    class Runner:
        def run(self, *_: Any) -> None:
            pass

    class Executor:
        def submit(self, *_: Any) -> Future:
            future: Future = Future()
            future.set_result(None)
            return future

        def shutdown(self, **_: Any) -> None:
            pass

    manager = P01JobManager(cast(P01FlowRunner, Runner()))
    manager._executor.shutdown()
    manager._executor = cast(ThreadPoolExecutor, Executor())
    thread = Thread(target=manager.submit, args=(1, "p01a"), daemon=True)
    thread.start()
    thread.join(1)
    assert not thread.is_alive()
    assert manager.active_ids() == ()
    manager.shutdown()


def test_serialization_and_figures() -> None:
    assert result_document(Score(80))["new_core_diagnostic"]
    with pytest.raises(TypeError, match="Unsupported result"):
        to_jsonable(object())
    with pytest.raises(ValueError, match="Non-finite"):
        to_jsonable(float("nan"))
    with pytest.raises(ValidationError):
        ManualHints.model_validate(
            {
                "rooms": [{"room_id": "r", "x": 1, "y": 2}, {"room_id": "r", "x": 2, "y": 3}],
                "hallways": [{"x": 1, "y": 1}],
            }
        )
    plan = floor_plan(PLAN)
    layout = plan.layout.to_plotly_json()
    assert layout["paper_bgcolor"] == "#252526"
    assert layout["plot_bgcolor"] == "#1e1e1e"
    assert layout["font"]["color"] == "#d4d4d4"
    assert layout["yaxis"]["scaleanchor"] == "x"
    assert list(plan.data[0].x) == [0, 10, 10, 0, 0]
    assert len(candidate_map(None).data) == 0
    assert len(score_breakdown(None).data) == 0
    json.dumps(plan.to_plotly_json())
