"""Bounded real-Core integration checks for the current experiment flows."""

import json
import time
from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import select

from fpg_lab.database.maintenance import migrate, seed
from fpg_lab.database.models import E02Run, P01BIteration
from fpg_lab.flows import e02a
from fpg_lab.runtime import LabRuntime
from fpg_lab.services.common import SystemConfigurationService
from scripts.run_experiment import sample_request


def runtime_for(path, *, small=False):
    runtime = LabRuntime(database_url=f"sqlite:///{path}", max_workers=1)
    migrate(runtime.database)
    seed(runtime.database)
    with runtime.database.session_factory() as session:
        service = SystemConfigurationService(session, runtime.codec)
        profile = service.get_active()
        payload = deepcopy(profile.configuration_data)
        for stage in ("initial", "refinement_a"):
            solver = payload["floor_plan_solver"][stage]["solver"]
            solver.update(max_time_seconds=2 if small else 5, num_search_workers=1, random_seed=42)
            if small:
                payload["floor_plan_solver"][stage]["hard_constraints"] = []
                payload["floor_plan_solver"][stage]["soft_constraints"] = []
        document = runtime.codec.validate_payload(payload)
        for key, value in service.configuration_values(document).items():
            setattr(profile, key, value)
        session.commit()
    return runtime


def wait_for(runtime, model, run_id, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with runtime.database.session_factory() as session:
            row = session.get(model, run_id)
            if row.status not in ("queued", "running", "termination_requested"):
                return row
        time.sleep(.05)
    raise AssertionError(f"{model.__name__} exceeded {timeout} seconds")


def test_real_e02a_solver_case(tmp_path, monkeypatch):
    document = json.loads((Path(__file__).parent / "fixtures/small_hint_map.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(e02a, "load_hint_maps", lambda: {"small": document})
    with runtime_for(tmp_path / "e02a.db", small=True) as runtime:
        run_id = e02a.start(runtime, "small", 0, None, 2, 42)
        row = wait_for(runtime, E02Run, run_id)
        assert row.status == "completed", row.error
        case = row.cases[0]
        assert case["status"] == "completed", case.get("error")
        assert case["stages"][0]["data"]["result"]["floor_plan"]
        assert case["scoring"]


@pytest.mark.parametrize("flow", ["p01b", "p01c"])
def test_real_p01_generation(tmp_path, flow):
    from fpg_lab.database.models import P01Experiment

    with runtime_for(tmp_path / f"{flow}.db", small=True) as runtime:
        run_id = runtime.start_experiment(flow, {
            "preset_data": json.loads((Path(__file__).parent / "fixtures/small_hint_map.json").read_text(encoding="utf-8")), "iterations": 1,
            "refinement_rounds": 1, "initial_time_limit": 2, "random_seed": 42,
        })
        row = wait_for(runtime, P01Experiment, run_id)
        assert row.status == "completed", row.error_data
        with runtime.database.session_factory() as session:
            iteration = session.scalar(select(P01BIteration).where(P01BIteration.experiment_id == run_id))
            assert iteration.status == "completed", iteration.error
            assert iteration.stages[0]["data"]["result"]["floor_plan"]
            assert any(stage["name"] == "Refinement 1" for stage in iteration.stages)
            if flow == "p01c":
                assert any(stage["name"] == "Openings" for stage in iteration.stages)
            assert iteration.scoring


def test_real_p01a_candidate(tmp_path):
    from fpg_lab.database.models import P01Experiment
    from scripts.run_experiment import collect

    with runtime_for(tmp_path / "p01a.db") as runtime:
        run_id = runtime.start_experiment("p01a", {"floor_plan_request": sample_request(), "trial_count": 1})
        row = wait_for(runtime, P01Experiment, run_id)
        assert row.status == "completed", row.error_data
        trace = collect(runtime, "p01a", run_id)
        assert len(trace["trials"]) == 1
        assert trace["trials"][0]["status"] == "completed"
        assert trace["trials"][0]["candidate_search_data"]
        assert trace["trials"][0]["final_score"] is not None
