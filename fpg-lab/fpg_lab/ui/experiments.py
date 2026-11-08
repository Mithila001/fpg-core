from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from nicegui import run, ui
from sqlalchemy import select

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.core.settings import ROOT
from fpg_lab.database.models import P01CandidateTrial, P01FloorPlanRun
from fpg_lab.flows.p01 import ACTIVE_STATUSES
from fpg_lab.inputs import FloorPlanRequest
from fpg_lab.runtime import FLOW_SERVICES, LabRuntime, row_document
from fpg_lab.services.common import FloorPlanTemplateService, SystemConfigurationService
from fpg_lab.ui.components import db_call, editor_value, json_panel, notify_error, set_editor, shell
from fpg_lab.ui.replay import candidate_replay
from fpg_lab.visualization import figures

STAGES = {
    "initial_solver_data": "Initial",
    "refinement_a_data": "Refinement A",
    "refinement_b_data": "Refinement B",
    "post_processing_data": "Post-processing",
    "opening_generation_data": "Openings",
    "final_floor_plan": "Final",
}


def table(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
    link_prefix: str,
    on_trial: Callable[[int], None] | None = None,
) -> None:
    columns = [
        {
            "name": field,
            "label": field.replace("_", " ").title(),
            "field": field,
            "sortable": True,
            "align": "left",
        }
        for field in fields
    ]
    widget = ui.table(
        columns=columns,
        rows=[{key: row.get(key) for key in fields} for row in rows],
        row_key="id",
        pagination=25,
    ).classes("w-full")
    if on_trial is not None:
        widget.add_slot(
            "body-cell-id",
            '<q-td :props="props"><q-btn flat dense color="primary" '
            ':label="props.row.id" @click="$parent.$emit(\'seek-trial\', props.row.trial_no)" /></q-td>',
        )
        widget.on("seek-trial", lambda event: on_trial(int(event.args)))
        return
    widget.add_slot(
        "body-cell-id",
        '<q-td :props="props"><a class="text-primary underline" :href="\''
        + link_prefix
        + "' + props.row.id\">{{ props.row.id }}</a></q-td>",
    )


def register_experiments(runtime: LabRuntime) -> None:
    @ui.page("/experiments/{flow}")
    async def experiment_page(flow: str) -> None:
        if flow == "p01b":
            from fpg_lab.ui.p01b import main_page

            await main_page(runtime)
            return
        if flow not in FLOW_SERVICES:
            shell("Unknown experiment")
            return
        shell(
            f"{flow.upper()} experiments",
            "Choose a profile and request, then run the pipeline in the background.",
        )
        try:
            configurations, templates = await db_call(
                runtime,
                lambda session: (
                    [
                        row_document(r)
                        for r in SystemConfigurationService(session, runtime.codec).list(
                            limit=500, offset=0
                        )[0]
                    ],
                    [
                        row_document(r)
                        for r in FloorPlanTemplateService(session).list(limit=500, offset=0)[0]
                    ],
                ),
            )
        except Exception as exc:
            ui.label(str(exc)).classes("text-rose-300")
            return
        state: dict[str, Any] = {"preview": None, "request": None, "hints": None}
        default_template = next(
            (t for t in templates if t["name"] == "Full Template (Default)"), None
        )

        def invalidate() -> None:
            state["preview"] = None
            preview_area.clear()
            hint_area.clear()
            state["hints"] = None

        def apply_template() -> None:
            selected = next((t for t in templates if t["id"] == template.value), None)
            if selected:
                set_editor(request_editor, selected["template_data"])
                if flow == "p01b":
                    invalidate()

        with ui.card().classes("w-full p-5 gap-4"):
            with ui.row().classes("w-full items-center"):
                profile = ui.select(
                    {
                        c["id"]: c["name"] + (" · active" if c["is_active"] else "")
                        for c in configurations
                    },
                    value=next((c["id"] for c in configurations if c["is_active"]), None),
                    label="System configuration",
                    on_change=lambda: invalidate() if flow == "p01b" else None,
                ).classes("min-w-80")
                template = ui.select(
                    {t["id"]: t["name"] for t in templates},
                    value=default_template["id"] if default_template else None,
                    label="Load a template",
                    on_change=apply_template,
                ).classes("min-w-80")
                trial_count = (
                    ui.number("Trials", value=100, min=1, max=100000, precision=0).classes("w-32")
                    if flow != "p01b"
                    else None
                )
                debug = ui.checkbox("Store debug data", value=True)
            if not configurations:
                ui.label(
                    "Create and activate a configuration before running an experiment."
                ).classes("text-amber-300")
                ui.link("Open configurations", "/configurations")
            request_editor = ui.json_editor(
                {
                    "content": {
                        "json": default_template["template_data"]
                        if default_template
                        else json.loads(
                            (ROOT / "seed/floor_plan_template.example.json").read_text(
                                encoding="utf-8"
                            )
                        )["template_data"]
                    }
                },
                schema=FloorPlanRequest.model_json_schema(),
                on_change=lambda: invalidate() if flow == "p01b" else None,
            ).classes("nicegui-json-editor w-full min-h-72")
            preview_area = ui.column().classes("w-full")
            hint_area = ui.column().classes("w-full")

            async def preview() -> None:
                try:
                    if profile.value is None:
                        raise ValueError("Select a system configuration")
                    request = await editor_value(request_editor)
                    prepared = await run.io_bound(runtime.preview_p01b, request, profile.value)
                    if prepared is None:
                        raise ValueError("Preview returned no result")
                    state["preview"], state["request"] = prepared, request
                    result = prepared["preprocessing"]["result"]
                    grid = result["candidate_grid"]
                    xs, ys = grid["x_positions"], grid["y_positions"]
                    rooms = [
                        r for r in result["generation_spec"]["rooms"] if r["room_type"] != "hallway"
                    ]
                    hints: dict[str, Any] = {
                        "rooms": [
                            {
                                "room_id": r["id"],
                                "x": xs[min(len(xs) - 1, round((i % 3 + 1) * (len(xs) - 1) / 4))],
                                "y": ys[min(len(ys) - 1, round((i // 3 + 1) * (len(ys) - 1) / 3))],
                            }
                            for i, r in enumerate(rooms)
                        ],
                        "hallways": [{"x": xs[len(xs) // 2], "y": ys[len(ys) // 2]}],
                    }
                    state["hints"] = hints
                    preview_area.clear()
                    with preview_area:
                        ui.plotly(
                            figures.candidate_map(
                                {"grid": grid, "points": []}, title="Prepared candidate grid"
                            )
                        ).classes("w-full h-80")
                        ui.label(
                            "Starter hint positions are editable. Coordinates must use the prepared grid."
                        ).classes("lab-muted")
                    hint_area.clear()
                    with hint_area:
                        for point in hints["rooms"]:
                            with ui.row().classes("items-center"):
                                ui.label(point["room_id"]).classes("w-48")
                                ui.number("X").bind_value(point, "x").classes("w-32")
                                ui.number("Y").bind_value(point, "y").classes("w-32")
                        hallways = ui.column()

                        @ui.refreshable
                        def hallway_rows() -> None:
                            for i, point in enumerate(hints["hallways"]):
                                with ui.row().classes("items-center"):
                                    ui.label(f"Hallway {i + 1}").classes("w-48")
                                    ui.number("X").bind_value(point, "x").classes("w-32")
                                    ui.number("Y").bind_value(point, "y").classes("w-32")

                        with hallways:
                            hallway_rows()

                        def add_hallway() -> None:
                            maximum = result["hallway_room_count_range"]["maximum"]
                            if len(hints["hallways"]) >= maximum:
                                ui.notify(f"Maximum {maximum} hallway hints", type="warning")
                                return
                            hints["hallways"].append({"x": xs[len(xs) // 2], "y": ys[len(ys) // 2]})
                            hallway_rows.refresh()

                        def remove_hallway() -> None:
                            if (
                                len(hints["hallways"])
                                > result["hallway_room_count_range"]["minimum"]
                            ):
                                hints["hallways"].pop()
                                hallway_rows.refresh()

                        with ui.row():
                            ui.button("Add hallway", on_click=add_hallway).props("outline")
                            ui.button("Remove last hallway", on_click=remove_hallway).props("flat")

                        async def inspect_hints() -> None:
                            try:
                                checked = await run.io_bound(
                                    runtime.preview_p01b, request, profile.value, hints
                                )
                                if checked is None or checked["candidate"] is None:
                                    raise ValueError("Hint validation returned no candidate")
                                preview_area.clear()
                                with preview_area:
                                    ui.plotly(
                                        figures.candidate_map(
                                            checked["candidate"], title="Validated manual hints"
                                        )
                                    ).classes("w-full h-96")
                            except Exception as exc:
                                notify_error(exc)

                        ui.button("Validate and inspect hints", on_click=inspect_hints).props(
                            "outline"
                        )
                except Exception as exc:
                    invalidate()
                    notify_error(exc)

            async def start() -> None:
                start_button.disable()
                try:
                    if profile.value is None:
                        raise ValueError("Select a system configuration")
                    request = await editor_value(request_editor)
                    payload = {
                        "floor_plan_request": request,
                        "system_configuration_id": profile.value,
                        "should_save": debug.value,
                    }
                    if flow == "p01b":
                        prepared = state["preview"]
                        if not prepared or request != state["request"]:
                            raise ValueError("Preview the current request before starting P01B")
                        current = await db_call(
                            runtime,
                            lambda session: (
                                SystemConfigurationService(session, runtime.codec)
                                .get(profile.value)
                                .config_hash
                            ),
                        )
                        if current != prepared["configuration_hash"]:
                            invalidate()
                            raise ValueError("The saved profile changed; preview it again")
                        payload["hint_points"] = state["hints"]
                    else:
                        assert trial_count is not None
                        payload["trial_count"] = trial_count.value
                    experiment_id = await run.io_bound(runtime.start_experiment, flow, payload)
                    ui.navigate.to(f"/experiments/{flow}/runs/{experiment_id}")
                except Exception as exc:
                    notify_error(exc)
                finally:
                    start_button.enable()

            with ui.row():
                if flow == "p01b":
                    ui.button("Preview request and edit hints", on_click=preview).props("outline")
                start_button = ui.button(f"Start {flow.upper()}", on_click=start)

        area = ui.column().classes("w-full")
        page = ui.number("History page", value=1, min=1, precision=0).classes("w-36")
        timer: ui.timer

        async def refresh_history() -> None:
            try:
                items, total = await db_call(
                    runtime, lambda session: _history(session, flow, int(page.value or 1))
                )
                area.clear()
                with area:
                    ui.label(f"Saved experiments · {total} total").classes("text-xl font-semibold")
                    table(
                        items,
                        (
                            "id",
                            "status",
                            "completed_trial_count",
                            "requested_trial_count",
                            "best_candidate_score",
                            "best_floor_plan_score",
                            "created_at",
                        ),
                        f"/experiments/{flow}/runs/",
                    )
                if not any(item["status"] in ACTIVE_STATUSES for item in items):
                    timer.deactivate()
            except Exception as exc:
                timer.deactivate()
                notify_error(exc)

        page.on_value_change(refresh_history)
        ui.button("Refresh history", on_click=lambda: timer.activate())
        timer = ui.timer(1.0, refresh_history, immediate=False)
        await refresh_history()

    @ui.page("/experiments/{flow}/runs/{experiment_id}")
    async def run_page(flow: str, experiment_id: int) -> None:
        if flow == "p01b":
            from fpg_lab.ui.p01b import run_page as p01b_run_page

            await p01b_run_page(runtime, experiment_id)
            return
        if flow not in FLOW_SERVICES:
            shell("Unknown experiment")
            return
        shell(
            f"{flow.upper()} run #{experiment_id}", compact=True, back_link=f"/experiments/{flow}"
        )
        replay_area = ui.column().classes("w-full gap-3")
        replay_loaded = False
        replay_seek: Callable[[int], None] | None = None

        def seek_saved_trial(trial_no: int) -> None:
            if replay_seek is not None:
                replay_seek(trial_no)

        area = ui.column().classes("w-full gap-5")
        trial_page = ui.number("Trial page", value=1, min=1, precision=0).classes("w-36")
        timer: ui.timer

        async def terminate() -> None:
            try:
                await db_call(
                    runtime,
                    lambda session: FLOW_SERVICES[flow](session).request_termination(experiment_id),
                )
                timer.activate()
                ui.notify("Termination requested; the current core stage will finish first")
            except Exception as exc:
                notify_error(exc)

        async def refresh_run() -> None:
            nonlocal replay_loaded, replay_seek
            try:
                item, trials, scores, runs = await db_call(
                    runtime,
                    lambda session: _run_data(
                        session, flow, experiment_id, int(trial_page.value or 1)
                    ),
                )
                if item["status"] not in ACTIVE_STATUSES and flow == "p01a" and not replay_loaded:
                    replay_area.clear()
                    with replay_area:
                        replay_seek = await candidate_replay(runtime, item)
                    replay_loaded = True
                area.clear()
                with area:
                    with ui.card().classes("w-full p-5"):
                        ui.label(item["status"].replace("_", " ").title()).classes(
                            "text-2xl font-semibold lab-accent"
                        )
                        ui.label(
                            f"Trials {item['completed_trial_count']}/{item['requested_trial_count'] or '—'} · best candidate {item['best_candidate_score']} · best floor plan {item['best_floor_plan_score']}"
                        )
                        if item["requested_trial_count"]:
                            ui.linear_progress(
                                value=min(
                                    1, item["completed_trial_count"] / item["requested_trial_count"]
                                )
                            )
                        if item["status"] in ACTIVE_STATUSES:
                            ui.button("Terminate", on_click=terminate, color="negative").props(
                                "outline"
                            )
                        ui.label(
                            f"Stop reason: {item['stop_reason'] or '—'} · core {item['fpg_core_version']}"
                        ).classes("text-sm lab-muted")
                    if scores:
                        with ui.row().classes("w-full"):
                            if replay_seek is None:
                                ui.plotly(figures.score_history(scores)).classes(
                                    "flex-1 min-w-80 h-72"
                                )
                            ui.plotly(figures.score_distribution(scores)).classes(
                                "flex-1 min-w-80 h-72"
                            )
                    if flow != "p01b":
                        ui.label("Stored candidate trials · 100 per history page").classes(
                            "text-lg font-semibold"
                        )
                        if not item["persist_trial_data"]:
                            ui.label(
                                "Debug data was disabled; P01A has no stored trials and P01C retains score/status metadata."
                            ).classes("text-amber-300")
                        table(
                            trials,
                            ("id", "trial_no", "status", "final_score", "duration_ms"),
                            f"/experiments/{flow}/runs/{experiment_id}/trials/",
                            on_trial=seek_saved_trial if replay_seek else None,
                        )
                    if runs:
                        ui.label("Floor-plan runs").classes("text-lg font-semibold")
                        table(
                            runs,
                            ("id", "source_trial_id", "status", "final_score", "duration_ms"),
                            f"/experiments/{flow}/runs/{experiment_id}/floor-plan-runs/",
                        )
                    json_panel(
                        "Request and configuration provenance",
                        {
                            k: item[k]
                            for k in (
                                "floor_plan_request",
                                "system_configuration_snapshot",
                                "system_configuration_hash",
                                "fpg_core_version",
                                "hint_points",
                            )
                        },
                    )
                    json_panel("Preprocessing", item["preprocessing_result"])
                    if item["error_data"]:
                        json_panel("Experiment error", item["error_data"])
                if item["status"] not in ACTIVE_STATUSES:
                    timer.deactivate()
            except Exception as exc:
                timer.deactivate()
                area.clear()
                with area:
                    ui.label(str(exc)).classes("text-rose-300")

        ui.button("Refresh results", on_click=lambda: timer.activate()).props("outline")
        trial_page.on_value_change(refresh_run)
        timer = ui.timer(1.0, refresh_run, immediate=False)
        await refresh_run()

    @ui.page("/experiments/{flow}/runs/{experiment_id}/trials/{trial_id}")
    async def trial_page(flow: str, experiment_id: int, trial_id: int) -> None:
        shell(f"Candidate trial #{trial_id}")
        ui.link("Back to run", f"/experiments/{flow}/runs/{experiment_id}")
        try:
            if flow not in ("p01a", "p01c"):
                raise ValueError("This flow has no candidate trials")

            def read(session: Any) -> Any:
                trial, linked = FLOW_SERVICES[flow](session).get_trial(trial_id)
                if trial.experiment_id != experiment_id:
                    raise ValueError("Trial does not belong to this run")
                return row_document(trial), linked

            item, linked = await db_call(runtime, read)
            if flow == "p01a":
                from fpg_lab.integrations.fpg_core.p01b_input import export_trial

                experiment = await db_call(
                    runtime,
                    lambda session: row_document(
                        FLOW_SERVICES[flow](session).get_experiment(experiment_id)
                    ),
                )
                try:
                    exported = export_trial(experiment, item)
                    ui.button(
                        icon="content_copy",
                        on_click=lambda: ui.run_javascript(
                            f"navigator.clipboard.writeText({json.dumps(json.dumps(exported))})"
                        ),
                    ).props("flat dense").tooltip("Copy cleaned hint map")
                except Exception:
                    ui.button(icon="content_copy").props("flat dense disable").tooltip(
                        "Cleaned candidate specification was not saved"
                    )
            candidate = item["candidate_search_data"]
            if candidate:
                ui.plotly(figures.candidate_map(candidate)).classes("w-full h-[32rem]")
            else:
                ui.label("Candidate geometry was not stored.").classes("text-amber-300")
            if linked:
                ui.link(
                    "Open floor-plan branch",
                    f"/experiments/{flow}/runs/{experiment_id}/floor-plan-runs/{linked}",
                )
            if item["candidate_scoring_data"]:
                ui.plotly(figures.score_breakdown(item["candidate_scoring_data"])).classes(
                    "w-full h-72"
                )
            json_panel("Candidate, circulation, scoring, and errors", item)
        except Exception as exc:
            ui.label(str(exc)).classes("text-rose-300")

    @ui.page("/experiments/{flow}/runs/{experiment_id}/floor-plan-runs/{run_id}")
    async def floor_page(flow: str, experiment_id: int, run_id: int) -> None:
        shell(f"Floor-plan run #{run_id}")
        ui.link("Back to experiment", f"/experiments/{flow}/runs/{experiment_id}")
        if flow not in ("p01b", "p01c"):
            ui.label("This flow has no floor-plan runs")
            return
        state: dict[str, Any] = {"run": None}
        selector = ui.select(STAGES, value="final_floor_plan", label="Pipeline stage").classes(
            "w-64"
        )
        area = ui.column().classes("w-full")
        timer: ui.timer

        def render() -> None:
            item = state["run"]
            if item is None:
                return
            stage = selector.value
            data = item.get(stage)
            plan = (
                data
                if stage == "final_floor_plan"
                else ((data or {}).get("result") or {}).get("floor_plan")
            )
            area.clear()
            with area:
                ui.label(
                    f"{item['status']} · final score {item['final_score']} · {item['duration_ms']} ms"
                ).classes("text-lg")
                if plan:
                    ui.plotly(figures.floor_plan(plan, title=STAGES[stage])).classes(
                        "w-full h-[36rem]"
                    )
                else:
                    ui.label(
                        "No floor plan is available at this stage; choose another stage or inspect diagnostics."
                    ).classes("text-amber-300")
                if item["floor_plan_scoring_data"]:
                    ui.plotly(figures.score_breakdown(item["floor_plan_scoring_data"])).classes(
                        "w-full h-72"
                    )
                json_panel(f"{STAGES[stage]} result and diagnostics", data)
                json_panel("All saved pipeline stages", item)

        async def refresh_floor() -> None:
            try:

                def read(session: Any) -> Any:
                    item = FLOW_SERVICES[flow](session).get_floor_plan_run(run_id)
                    if item.experiment_id != experiment_id:
                        raise ValueError("Floor-plan run does not belong to this experiment")
                    return row_document(item)

                state["run"] = await db_call(runtime, read)
                render()
                if state["run"]["status"] != "running":
                    timer.deactivate()
            except Exception as exc:
                timer.deactivate()
                notify_error(exc)

        selector.on_value_change(render)
        ui.button("Refresh", on_click=lambda: timer.activate()).props("outline")
        timer = ui.timer(1.0, refresh_floor, immediate=False)
        await refresh_floor()


def _history(session: Any, flow: str, page: int) -> Any:
    records, total = FLOW_SERVICES[flow](session).list_experiments(
        status=None, limit=50, offset=(max(1, page) - 1) * 50
    )
    return [row_document(record) for record in records], total


def _run_data(session: Any, flow: str, experiment_id: int, page: int) -> Any:
    item = FLOW_SERVICES[flow](session).get_experiment(experiment_id)
    columns = (
        P01CandidateTrial.id,
        P01CandidateTrial.trial_no,
        P01CandidateTrial.status,
        P01CandidateTrial.final_score,
        P01CandidateTrial.duration_ms,
    )
    query = (
        select(*columns)
        .where(P01CandidateTrial.experiment_id == experiment_id)
        .order_by(P01CandidateTrial.trial_no)
    )
    trials = [
        dict(row)
        for row in session.execute(query.limit(100).offset((max(1, page) - 1) * 100)).mappings()
    ]
    scores = [
        dict(row)
        for row in session.execute(
            select(P01CandidateTrial.trial_no, P01CandidateTrial.final_score)
            .where(P01CandidateTrial.experiment_id == experiment_id)
            .order_by(P01CandidateTrial.trial_no)
        ).mappings()
    ]
    runs = [
        dict(row)
        for row in session.execute(
            select(
                P01FloorPlanRun.id,
                P01FloorPlanRun.source_trial_id,
                P01FloorPlanRun.status,
                P01FloorPlanRun.final_score,
                P01FloorPlanRun.duration_ms,
            )
            .where(P01FloorPlanRun.experiment_id == experiment_id)
            .order_by(P01FloorPlanRun.id)
        ).mappings()
    ]
    return row_document(item), to_jsonable(trials), to_jsonable(scores), to_jsonable(runs)
