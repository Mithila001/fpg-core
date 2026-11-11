"""P01B's independently repeated floor-plan pipeline."""

from dataclasses import replace
from time import perf_counter

from fpg_core.floor_plan_solver import (
    FloorPlanSolveRequest,
    RoomPlacementHint,
    SeedSource,
    build_default_profiles,
    generate_floor_plan,
)

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.database.models import P01BIteration
from fpg_lab.flows.p01 import PipelineTerminated, error_payload, result_document, utc_now
from fpg_lab.integrations.fpg_core.p01b_input import validate_export


def run_p01b(runner, session, experiment):
    try:
        settings = dict(experiment.hint_points)
        preset = settings["preset"]
        spec = validate_export(preset)
        adapter = runner.adapter_factory(
            runner.config_codec.decode_for_flow(experiment.system_configuration_snapshot, experiment.flow_type)
        )
        refinement_document = adapter.core_config.document.experiments.p01b_refinement
        if refinement_document is None:
            refinement_config = build_default_profiles().refinement_a
        else:
            solver_document = adapter.core_config.document.floor_plan_solver
            refinement_config = runner.config_codec._build_solver(
                solver_document.model_copy(update={"refinement_a": refinement_document})
            ).refinement_a
        refinement_config = replace(
            refinement_config,
            seed=replace(
                refinement_config.seed, source=SeedSource.EXISTING_FLOOR_PLAN, require_source=True
            ),
        )
        adapter.core_config = replace(
            adapter.core_config,
            floor_plan_solver=replace(
                adapter.core_config.floor_plan_solver, refinement_a=refinement_config
            ),
        )
        initial_config = adapter.core_config.floor_plan_solver.initial
        seed = replace(
            initial_config.seed,
            source=SeedSource.NONE if settings["disable_hints"] else SeedSource.CANDIDATE_HINTS,
            require_source=not settings["disable_hints"],
            apply_hints=not settings["disable_hints"],
        )
        initial_config = replace(
            initial_config,
            seed=seed,
            solver=replace(initial_config.solver, max_time_seconds=settings["initial_time_limit"]),
        )
        settings["effective_solver"] = to_jsonable(
            {"initial": initial_config, "refinement": refinement_config}
        )
        experiment.hint_points = settings
        session.commit()
        hints = (
            ()
            if settings["disable_hints"]
            else tuple(
                RoomPlacementHint(room_id=p["room_id"], x=p["x"], y=p["y"])
                for p in preset["candidate"]["points"]
            )
        )
        for number in range(1, settings["iterations"] + 1):
            runner._check_termination(experiment.id)
            started = perf_counter()
            row = P01BIteration(
                experiment_id=experiment.id, number=number, status="running", stages=[]
            )
            session.add(row)
            session.commit()
            stage = "initial"
            stage_started = perf_counter()
            try:
                execution = generate_floor_plan(
                    FloorPlanSolveRequest(
                        specification=spec, config=initial_config, candidate_hints=hints
                    ),
                    mode=adapter.execution_mode(debug=True),
                )
                stages = [
                    {
                        "name": "Initial",
                        "data": result_document(execution),
                        "duration_ms": int((perf_counter() - stage_started) * 1000),
                    }
                ]
                row.stages = stages[:]
                session.commit()
                if not execution.result.solved:
                    raise RuntimeError(
                        f"{execution.result.status.value}: {execution.result.message}"
                    )
                plan = execution.result.floor_plan
                for index in range(settings["refinement_rounds"]):
                    runner._check_termination(experiment.id)
                    stage = f"refinement_{index + 1}"
                    stage_started = perf_counter()
                    execution = adapter.refine_floor_plan(
                        spec, plan, profile="refinement_a", debug=True
                    )
                    stages.append(
                        {
                            "name": f"Refinement {index + 1}",
                            "data": result_document(execution),
                            "duration_ms": int((perf_counter() - stage_started) * 1000),
                        }
                    )
                    row.stages = stages[:]
                    session.commit()
                    if not execution.result.solved:
                        raise RuntimeError(
                            f"{execution.result.status.value}: {execution.result.message}"
                        )
                    plan = execution.result.floor_plan
                runner._check_termination(experiment.id)
                stage = "post_processing"
                stage_started = perf_counter()
                execution = adapter.post_process_floor_plan(spec, plan, debug=True)
                stages.append(
                    {
                        "name": "Post-process",
                        "data": result_document(execution),
                        "duration_ms": int((perf_counter() - stage_started) * 1000),
                    }
                )
                row.stages = stages[:]
                session.commit()
                if getattr(execution.result.status, "value", execution.result.status) != "success":
                    raise RuntimeError(str(execution.result.failure))
                plan = execution.result.floor_plan
                if experiment.flow_type == "p01c":
                    runner._check_termination(experiment.id)
                    stage = "openings"
                    stage_started = perf_counter()
                    execution = adapter.generate_floor_plan_openings(plan, debug=True)
                    stages.append({"name": "Openings", "data": result_document(execution),
                                   "duration_ms": int((perf_counter() - stage_started) * 1000)})
                    row.stages = stages[:]
                    session.commit()
                    if getattr(execution.result.status, "value", execution.result.status) not in ("optimal", "feasible") or execution.result.floor_plan is None:
                        raise RuntimeError(str(execution.result.message))
                    plan = execution.result.floor_plan
                runner._check_termination(experiment.id)
                stage = "scoring"
                row.scoring = result_document(
                    adapter.score_completed_floor_plan(
                        plan, spec, debug=True
                    )
                )
                row.status = "completed"
                experiment.successful_trial_count += 1
            except PipelineTerminated:
                row.status = "terminated"
                session.commit()
                raise
            except Exception as exc:
                row.status = "failed"
                row.error = error_payload(exc, stage=stage)
                if stage != "scoring" and (
                    not row.stages
                    or row.stages[-1]["name"]
                    != (
                        "Initial"
                        if stage == "initial"
                        else "Openings" if stage == "openings"
                        else "Post-process"
                        if stage == "post_processing"
                        else stage.replace("refinement_", "Refinement ")
                    )
                ):
                    row.stages = [
                        *row.stages,
                        {
                            "name": "Initial"
                            if stage == "initial"
                            else "Openings" if stage == "openings"
                            else "Post-process"
                            if stage == "post_processing"
                            else stage.replace("refinement_", "Refinement "),
                            "data": {"error": row.error},
                            "duration_ms": int((perf_counter() - stage_started) * 1000),
                        },
                    ]
                experiment.failed_trial_count += 1
            row.duration_ms = int((perf_counter() - started) * 1000)
            experiment.completed_trial_count += 1
            session.commit()
        experiment.status = "completed"
        experiment.stop_reason = "iterations_completed"
        experiment.finished_at = utc_now()
        session.commit()
    except PipelineTerminated:
        runner._finish_terminated(session, experiment)
    except Exception as exc:
        runner._finish_failed(session, experiment, error_payload(exc, stage="p01b_setup"))
