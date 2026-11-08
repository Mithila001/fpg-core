from sqlalchemy import select
from test_lab import PLAN, Execution, RecordingAdapter, Solve, create_profile, payload, wait

from fpg_lab.database.models import P01BIteration, P01BPreset
from fpg_lab.integrations.fpg_core.p01b_input import export_trial, validate_export
from fpg_lab.runtime import LabRuntime


def test_export_and_independent_iterations(tmp_path, monkeypatch):
    calls = []

    def solve(request, *, mode):
        calls.append(request)
        return Execution(Solve(PLAN))

    monkeypatch.setattr("fpg_lab.flows.p01b.generate_floor_plan", solve)
    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=RecordingAdapter
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        older_trial = dict(source["trials"][0])
        older_trial["circulation_data"] = dict(older_trial["circulation_data"])
        older_trial["circulation_data"].pop("lab_generation_specification")
        assert (
            export_trial(source["experiment"], older_trial)["specification"]
            == document["specification"]
        )
        spec = validate_export(document)
        assert {p["room_id"] for p in document["candidate"]["points"]} == {r.id for r in spec.rooms}
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="test", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        experiment_id = runtime.start_experiment(
            "p01b",
            {
                "preset_id": preset_id,
                "initial_time_limit": 1,
                "iterations": 2,
                "refinement_rounds": 2,
                "disable_hints": True,
            },
        )
        result = wait(runtime, "p01b", experiment_id)
        assert result["experiment"]["status"] == "completed"
        with runtime.database.session_factory() as session:
            session.delete(session.get(P01BPreset, preset_id))
            session.commit()
            rows = list(
                session.scalars(
                    select(P01BIteration)
                    .where(P01BIteration.experiment_id == experiment_id)
                    .order_by(P01BIteration.number)
                )
            )
            assert len(rows) == 2
            assert all(row.status == "completed" for row in rows), [row.error for row in rows]
            assert all(
                [s["name"] for s in row.stages]
                == ["Initial", "Refinement 1", "Refinement 2", "Post-process"]
                for row in rows
            )
            assert all(row.scoring["result"]["total_score"] == 90 for row in rows)
        assert len(calls) == 2 and all(not call.candidate_hints for call in calls)
        assert calls[0].config == calls[1].config


def test_failed_refinement_keeps_initial_and_continues(tmp_path, monkeypatch):
    class FailingAdapter(RecordingAdapter):
        def refine_floor_plan(self, specification, floor_plan, *, profile, debug):
            raise RuntimeError("refinement broke")

    monkeypatch.setattr(
        "fpg_lab.flows.p01b.generate_floor_plan", lambda request, *, mode: Execution(Solve(PLAN))
    )
    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=FailingAdapter
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="test", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        experiment_id = runtime.start_experiment(
            "p01b",
            {
                "preset_id": preset_id,
                "initial_time_limit": 1,
                "iterations": 2,
                "refinement_rounds": 1,
            },
        )
        result = wait(runtime, "p01b", experiment_id)
        assert result["experiment"]["failed_trial_count"] == 2
        with runtime.database.session_factory() as session:
            rows = list(
                session.scalars(
                    select(P01BIteration).where(P01BIteration.experiment_id == experiment_id)
                )
            )
            assert len(rows) == 2
            assert all(
                row.status == "failed" and row.error["stage"] == "refinement_1" for row in rows
            )
            assert all(row.stages[0]["data"]["result"]["floor_plan"] == PLAN for row in rows)


def test_real_initial_solver_with_and_without_hints(tmp_path):
    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'real.db'}", adapter_factory=RecordingAdapter
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="real", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        for disabled in (False, True):
            experiment_id = runtime.start_experiment(
                "p01b",
                {"preset_id": preset_id, "initial_time_limit": 0.2, "disable_hints": disabled},
            )
            result = wait(runtime, "p01b", experiment_id)
            assert result["experiment"]["status"] == "completed"
            with runtime.database.session_factory() as session:
                row = session.scalar(
                    select(P01BIteration).where(P01BIteration.experiment_id == experiment_id)
                )
                assert row.stages[0]["name"] == "Initial"
                assert "result" in row.stages[0]["data"], row.error


def test_scoring_failure_retains_post_processed_plan(tmp_path, monkeypatch):
    class FailingScore(RecordingAdapter):
        def score_completed_floor_plan(self, floor_plan, specification, *, debug):
            raise RuntimeError("scoring unavailable")

    monkeypatch.setattr(
        "fpg_lab.flows.p01b.generate_floor_plan", lambda request, *, mode: Execution(Solve(PLAN))
    )
    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'score.db'}", adapter_factory=FailingScore
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="test", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        experiment_id = runtime.start_experiment(
            "p01b", {"preset_id": preset_id, "initial_time_limit": 1, "refinement_rounds": 0}
        )
        wait(runtime, "p01b", experiment_id)
        with runtime.database.session_factory() as session:
            row = session.scalar(
                select(P01BIteration).where(P01BIteration.experiment_id == experiment_id)
            )
            assert row.error["stage"] == "scoring"
            assert [stage["name"] for stage in row.stages] == ["Initial", "Post-process"]
            assert row.stages[-1]["data"]["result"]["floor_plan"] == PLAN
