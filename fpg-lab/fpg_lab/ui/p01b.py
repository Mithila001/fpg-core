"""Preset management and geometry inspection for P01B."""

import json
import math
from typing import Any

import plotly.graph_objects as go
from nicegui import run, ui
from sqlalchemy import select

from fpg_lab.database.models import FloorPlanTemplate, P01BIteration, P01BPreset
from fpg_lab.integrations.fpg_core.p01b_input import validate_export
from fpg_lab.runtime import row_document
from fpg_lab.services.common import SystemConfigurationService
from fpg_lab.services.p01b import P01BService, next_preset_name, save_preset
from fpg_lab.services.p01c import P01CService
from fpg_lab.ui.components import db_call, json_panel, notify_error, shell
from fpg_lab.ui.result_layout import ResultWorkspace
from fpg_lab.visualization import figures


async def main_page(runtime, flow="p01b"):
    service_type = P01CService if flow == "p01c" else P01BService
    shell(f"{flow.upper()} · Setup", "Configure repeated floor-plan generation and refinement.")
    state: dict[str, Any] = {"data": None}
    with ui.element("div").classes("w-full grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"):
        with ui.column().classes("w-full gap-4") as controls:
            presets = ui.select({}, label="Hint map preset").classes("w-full")
            configs = ui.select({}, label="System configuration").classes("w-full")
            disable = ui.checkbox("Disable hint points", value=False)
            with ui.element("div").classes("w-full grid grid-cols-2 gap-4"):
                rounds = ui.number("Refinement rounds", min=0, max=5, value=0, precision=0).classes(
                    "w-full"
                )
                iterations = ui.number("Iterations", min=1, max=100, value=1, precision=0).classes(
                    "w-full"
                )
            seconds = ui.number("Initial solver time limit (seconds)", min=0.01, value=5).classes(
                "w-full"
            )
        preview = ui.column().classes("w-full min-w-0")
    history = ui.column().classes("w-full")
    history_page = ui.number("History page", min=1, value=1, precision=0).classes("w-36")
    with ui.dialog() as dialog, ui.card().classes("w-[50rem] max-w-full"):
        name = ui.input("Preset name").classes("w-full")
        pasted = ui.textarea("Paste P01A cleaned hint map JSON").classes("w-full")
        validation = ui.label()
        import_preview = ui.column().classes("w-full")

        def inspect():
            state["data"] = None
            import_preview.clear()
            try:
                data = json.loads(pasted.value or "")
                validate_export(data)
                state["data"] = data
                validation.set_text("Valid hint map")
                with import_preview:
                    ui.plotly(figures.candidate_map(data["candidate"])).classes("w-full h-80")
            except Exception as exc:
                validation.set_text(f"Invalid hint map: {exc}")

        pasted.on_value_change(inspect)

        async def save():
            try:
                inspect()
                if (
                    not state["data"]
                    or not (name.value or "").strip()
                    or len(name.value.strip()) > 128
                ):
                    raise ValueError("Enter a name and a valid hint map")

                def create(session):
                    return save_preset(session, name.value, state["data"])

                selected = await db_call(runtime, create)
                dialog.close()
                await refresh()
                presets.set_value(selected)
            except Exception as exc:
                notify_error(exc)

        ui.button("Save preset", on_click=save)

    quick = {"job": None, "cancel": None, "suggested": None, "timer": None}
    with (
        ui.dialog() as quick_dialog,
        ui.card().classes("w-[80vw] h-[80vh] max-w-none overflow-auto"),
    ):
        ui.label("Quick Hint Map").classes("text-xl")
        quick_config = ui.label()
        templates = ui.select({}, label="Existing template").classes("w-full")
        count = ui.number("Trial count", value=100, min=1, max=100000, precision=0)
        score = ui.number("Required Best Score", value=70, min=0, max=100)
        progress = ui.linear_progress(value=0).classes("w-full")
        status = ui.label()
        quick_name = ui.input("Preset name (optional)").classes("w-full")

        async def open_quick():
            try:
                if quick.get("job") and quick["job"]["status"] == "running":
                    raise ValueError("The previous search is still stopping")
                selected = next(
                    (c for c in state.get("configurations", []) if c["id"] == configs.value), None
                )
                if selected is None:
                    raise ValueError("Select a system configuration first")
                rows, suggested = await db_call(
                    runtime,
                    lambda session: (
                        [
                            (t.id, t.name)
                            for t in session.scalars(
                                select(FloorPlanTemplate).order_by(FloorPlanTemplate.name)
                            )
                        ],
                        next_preset_name(session),
                    ),
                )
                templates.options = dict(rows)
                templates.value = None
                templates.update()
                quick_config.set_text(f"System configuration: {selected['name']}")
                quick["suggested"] = suggested
                quick_name.set_value(suggested)
                stored = await ui.run_javascript("sessionStorage.getItem('fpg_quick_hint_score')")
                score.set_value(float(stored) if stored is not None else 70)
                status.set_text("")
                progress.set_value(0)
                quick["job"] = None
                apply_button.disable()
                save_button.disable()
                start_button.enable()
                quick_dialog.open()
            except Exception as exc:
                notify_error(exc)

        async def start_quick():
            try:
                if (
                    templates.value is None
                    or count.value is None
                    or int(count.value) != count.value
                ):
                    raise ValueError("Select a template and enter a whole trial count")
                if score.value is None:
                    raise ValueError("Enter a required score")
                job, cancel = await run.io_bound(
                    runtime.start_quick_hint,
                    templates.value,
                    configs.value,
                    int(count.value),
                    float(score.value),
                )
                quick.update(job=job, cancel=cancel)
                await ui.run_javascript(
                    f"sessionStorage.setItem('fpg_quick_hint_score', {json.dumps(str(score.value))})"
                )
                for item in (templates, count, score, start_button):
                    item.disable()
                apply_button.disable()
                save_button.disable()
                quick["timer"].active = True
            except Exception as exc:
                notify_error(exc)

        def poll_quick():
            job = quick["job"]
            if job is None:
                return
            progress.set_value(job["completed"] / job["count"])
            status.set_text(
                f"{job['completed']} / {job['count']} trials · Best: {job['best_score'] if job['best_score'] is not None else '—'} · {job.get('stop_reason') or job.get('error') or job['status']}"
            )
            if job["status"] != "running":
                quick["timer"].active = False
                for item in (templates, count, score, start_button):
                    item.enable()
                if job["status"] == "completed":
                    apply_button.enable()
                    save_button.enable()

        def cancel_quick():
            if quick.get("cancel") and quick.get("job", {}).get("status") == "running":
                quick["cancel"].set()
            apply_button.disable()
            save_button.disable()

        def remember_score(e):
            if e.value is not None and math.isfinite(e.value) and 0 <= e.value <= 100:
                ui.run_javascript(
                    f"sessionStorage.setItem('fpg_quick_hint_score', {json.dumps(str(e.value))})"
                )

        score.on_value_change(remember_score)

        def apply_quick():
            state["temporary_preset"] = quick["job"]["result"]
            presets.options = {**presets.options, "temporary": "Unsaved hint map"}
            presets.update()
            presets.set_value("temporary")
            quick_dialog.close()

        async def save_quick():
            try:
                selected = await db_call(
                    runtime,
                    lambda session: save_preset(
                        session, quick_name.value, quick["job"]["result"], quick["suggested"]
                    ),
                )
                state.pop("temporary_preset", None)
                await refresh()
                presets.set_value(selected)
                quick_dialog.close()
            except Exception as exc:
                notify_error(exc)

        with ui.row():
            start_button = ui.button("Start", on_click=start_quick)
            ui.button("Cancel", on_click=lambda: (cancel_quick(), quick_dialog.close())).props(
                "outline"
            )
            apply_button = ui.button("Quick Apply", on_click=apply_quick)
            save_button = ui.button("Save and Apply", on_click=save_quick)
        quick["timer"] = ui.timer(0.5, poll_quick, active=False)
        quick_dialog.on("hide", cancel_quick)

    async def refresh():
        def read(session):
            return (
                [
                    row_document(p)
                    for p in session.scalars(
                        select(P01BPreset).order_by(P01BPreset.name, P01BPreset.id)
                    )
                ],
                [
                    row_document(c)
                    for c in SystemConfigurationService(session, runtime.codec).list(
                        limit=500, offset=0
                    )[0]
                ],
                [
                    row_document(e)
                    for e in service_type(session).list_experiments(
                        status=None,
                        limit=100,
                        offset=(max(1, int(history_page.value or 1)) - 1) * 100,
                    )[0]
                ],
            )

        saved, configurations, experiments = await db_call(runtime, read)
        state["presets"] = saved
        presets.options = {p["id"]: p["name"] for p in saved}
        if state.get("temporary_preset") is not None:
            presets.options["temporary"] = "Unsaved hint map"
        presets.update()
        configs.options = {c["id"]: c["name"] for c in configurations}
        if configs.value is None:
            configs.value = next((c["id"] for c in configurations if c["is_active"]), None)
        configs.update()
        state["configurations"] = configurations
        update_time()
        history.clear()
        with history:
            ui.label("Experiment history").classes("text-xl")
            for experiment in experiments:
                ui.link(
                    f"#{experiment['id']} · {experiment['status']} · {experiment['completed_trial_count']}/{experiment['requested_trial_count'] or 0} iterations",
                    f"/experiments/{flow}/runs/{experiment['id']}",
                )
        show_preset()

    def show_preset():
        preview.clear()
        selected = next((p for p in state.get("presets", []) if p["id"] == presets.value), None)
        if presets.value == "temporary" and state.get("temporary_preset") is not None:
            selected = {"data": state["temporary_preset"]}
        if selected:
            with preview:
                ui.plotly(figures.candidate_map(selected["data"]["candidate"])).classes(
                    "w-full h-80"
                )
        else:
            with preview:
                ui.label("Select a preset to preview its hint map.").classes("lab-muted")

    def update_time():
        selected = next(
            (c for c in state.get("configurations", []) if c["id"] == configs.value), None
        )
        if selected:
            solver = selected["configuration_data"].get("floor_plan_solver") or {}
            seconds.set_value(
                ((solver.get("initial") or {}).get("solver") or {}).get("max_time_seconds", 5)
            )

    async def delete():
        try:

            def remove(session):
                item = session.get(P01BPreset, presets.value)
                if item:
                    session.delete(item)
                    session.commit()

            await db_call(runtime, remove)
            presets.set_value(None)
            await refresh()
        except Exception as exc:
            notify_error(exc)

    async def start():
        try:
            if (
                rounds.value is None
                or iterations.value is None
                or int(rounds.value) != rounds.value
                or int(iterations.value) != iterations.value
            ):
                raise ValueError("Refinement rounds and iterations must be integers")
            payload = {
                "preset_id": None if presets.value == "temporary" else presets.value,
                "preset_data": state.get("temporary_preset")
                if presets.value == "temporary"
                else None,
                "system_configuration_id": configs.value,
                "disable_hints": disable.value,
                "refinement_rounds": int(rounds.value),
                "iterations": int(iterations.value),
                "initial_time_limit": seconds.value,
            }
            experiment_id = await run.io_bound(runtime.start_experiment, flow, payload)
            ui.navigate.to(f"/experiments/{flow}/runs/{experiment_id}")
        except Exception as exc:
            notify_error(exc)

    def preset_changed():
        if presets.value != "temporary" and state.pop("temporary_preset", None) is not None:
            presets.options.pop("temporary", None)
            presets.update()
        show_preset()

    presets.on_value_change(preset_changed)
    configs.on_value_change(update_time)
    history_page.on_value_change(refresh)
    with controls, ui.row():
        ui.button("Quick Hint Map", on_click=open_quick)
        ui.button("Import preset", on_click=dialog.open)
        ui.button("Delete preset", on_click=delete).props("outline")
        ui.button("Start experiment", on_click=start)
        ui.button("Refresh history", on_click=refresh).props("flat")
    await refresh()


async def run_page(runtime, experiment_id, flow="p01b"):
    """Inspect a saved P01B/P01C run without shrinking the primary floor plan."""
    service_type = P01CService if flow == "p01c" else P01BService
    state: dict[str, Any] = {
        "iteration": 0, "stage": 0, "rows": [], "experiment": None,
        "selected_stage": "Initial",
    }
    workspace = ResultWorkspace(
        f"{flow.upper()} run #{experiment_id}",
        back_link=f"/experiments/{flow}",
        views=("Canvas", "Scores", "Diagnostics"),
    )
    with workspace.main("Canvas"):
        chart = ui.plotly(figures.floor_plan(None)).classes("lab-primary-plot")
    with workspace.main("Scores"):
        score_area = ui.column().classes("w-full min-w-0 gap-3")
    with workspace.main("Diagnostics"):
        diagnostics_area = ui.column().classes("w-full min-w-0 gap-3")
    with workspace.controls:
        status = ui.label("Loading run…").classes("text-sm lab-muted")
        with ui.row().classes("items-center gap-2 w-full"):
            previous = ui.button("Previous").props("dense outline")
            position = ui.label().classes("text-sm font-medium")
            following = ui.button("Next").props("dense outline")
        stages_area = ui.column().classes("w-full gap-1")
        overlay = ui.checkbox("Show original hint points", value=False).props("dense")
        ui.button("Refresh", on_click=lambda: timer.activate()).props("dense flat")
        terminate_button = ui.button("Terminate run").props("dense outline")
    with workspace.context("Canvas"):
        details_area = ui.column().classes("w-full gap-2")
        room_area = ui.column().classes("w-full gap-1")
    with workspace.context("Scores"):
        ui.label("Stored scoring data for the selected iteration.").classes("lab-muted text-sm")
    with workspace.context("Diagnostics"):
        ui.label("Saved stage data, errors and iteration provenance.").classes(
            "lab-muted text-sm"
        )

    def render() -> None:
        item = state["experiment"]
        if not item:
            return
        rows = state["rows"]
        status.set_text(
            f"{item['status']} · {item['completed_trial_count']}/{item['requested_trial_count']} iterations"
        )
        terminate_button.set_enabled(item["status"] in ("queued", "running", "termination_requested"))
        if not item.get("hint_points") or "preset" not in item["hint_points"]:
            details_area.clear()
            with details_area:
                ui.label("Legacy run: its original hint data cannot be displayed here.").classes(
                    "text-amber-300"
                )
            return
        overlay.set_enabled(not item["hint_points"]["disable_hints"])
        if rows:
            state["iteration"] = max(0, min(state["iteration"], len(rows) - 1))
        previous.set_enabled(bool(rows) and state["iteration"] > 0)
        following.set_enabled(state["iteration"] + 1 < len(rows))
        position.set_text(
            f"{state['iteration'] + 1} / {item['requested_trial_count']}"
            if rows else "No iterations yet"
        )
        stages_area.clear()
        score_area.clear()
        diagnostics_area.clear()
        details_area.clear()
        room_area.clear()
        if not rows:
            chart.figure = figures.floor_plan(None)
            chart.update()
            with details_area:
                ui.label("Waiting for the first completed stage.").classes("lab-muted")
            return

        row = rows[state["iteration"]]
        stages = row["stages"]
        state["stage"] = next(
            (index for index, stage in enumerate(stages)
             if stage["name"] == state["selected_stage"]), 0,
        )
        if stages:
            state["selected_stage"] = stages[state["stage"]]["name"]
        with stages_area:
            ui.label("Pipeline stage").classes("font-semibold text-sm")
            with ui.row().classes("w-full gap-1"):
                for index, stage in enumerate(stages):
                    ui.button(
                        stage["name"], on_click=lambda index=index: select_stage(index)
                    ).props("dense " + ("" if index == state["stage"] else "outline"))
        stage = stages[state["stage"]] if stages else None
        data = stage["data"] if stage else None
        plan = ((data or {}).get("result") or {}).get("floor_plan")
        figure = figures.floor_plan(plan)
        if overlay.value and not item["hint_points"]["disable_hints"]:
            for trace in figure.data:
                trace.opacity = 0.35
            for point in item["hint_points"]["preset"]["candidate"]["points"]:
                figure.add_trace(
                    go.Scatter(
                        x=[point["x"]], y=[point["y"]], mode="markers+text",
                        text=[point["room_id"]], textposition="top center",
                        name=point["room_id"],
                        marker={"size": 12, "color": figures.color(point["room_id"])},
                    )
                )
        figure.update_layout(showlegend=False)
        chart.figure = figure
        chart.update()
        score = ((row.get("scoring") or {}).get("result") or {}).get("total_score")
        with details_area:
            ui.label(f"{row['status']} · score {score if score is not None else '—'}").classes(
                "text-sm font-medium"
            )
            ui.label(
                f"Iteration {row['duration_ms']} ms · "
                f"stage {(stage or {}).get('duration_ms', 0)} ms"
            ).classes("lab-muted text-sm")
            if row.get("error"):
                ui.label(
                    f"{row['error']['stage']}: {row['error']['message']}"
                ).classes("text-amber-300 text-sm")
            if not plan:
                ui.label("No floor plan saved for this stage.").classes("lab-muted text-sm")
            if flow == "p01c":
                opening_stage = next(
                    (candidate for candidate in stages if candidate["name"] == "Openings"), None
                )
                final_plan = (((opening_stage or {}).get("data") or {}).get("result") or {}).get(
                    "floor_plan"
                )
                if final_plan:
                    document = {
                        "version": 1,
                        "project_units_per_meter": item["system_configuration_snapshot"][
                            "project_units_per_meter"
                        ],
                        "floor_plan": final_plan,
                    }

                    def copy_plan() -> None:
                        ui.run_javascript(
                            f"navigator.clipboard.writeText({json.dumps(json.dumps(document))})"
                        )
                        ui.notify("Floor plan and openings copied")

                    ui.button("Copy final floor plan", icon="content_copy", on_click=copy_plan).props(
                        "dense outline"
                    )
        with room_area:
            if plan:
                ui.label("Rooms").classes("font-semibold text-sm")
                for room in plan.get("rooms", []):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("square", color=figures.color(str(room.get("room_type", room["id"]))))
                        ui.label(room.get("name") or room["id"]).classes("text-sm")
        with score_area:
            if row.get("scoring"):
                scoring = row["scoring"].get("result") or row["scoring"]
                ui.plotly(figures.score_breakdown(scoring)).classes("w-full h-[32rem]")
                json_panel("Saved scoring details", row["scoring"])
            else:
                ui.label("Scoring has not been recorded for this iteration.").classes("lab-muted")
        with diagnostics_area:
            if data:
                json_panel(f"{(stage or {}).get('name', 'Stage')} details", data)
            if row.get("error"):
                json_panel("Iteration error", row["error"])
            if row.get("scoring"):
                json_panel("Iteration scoring", row["scoring"])
            json_panel("Run input and configuration", {
                "hint_points": item.get("hint_points"),
                "system_configuration_snapshot": item.get("system_configuration_snapshot"),
            })

    def select_stage(index: int) -> None:
        stages = state["rows"][state["iteration"]]["stages"]
        state["stage"] = index
        state["selected_stage"] = stages[index]["name"]
        render()

    def move(delta: int) -> None:
        state["iteration"] += delta
        render()

    async def refresh() -> None:
        try:
            def read(session):
                experiment = service_type(session).get_experiment(experiment_id)
                rows = session.scalars(
                    select(P01BIteration)
                    .where(P01BIteration.experiment_id == experiment_id)
                    .order_by(P01BIteration.number)
                )
                return row_document(experiment), [row_document(row) for row in rows]

            old = (state["experiment"], state["rows"])
            state["experiment"], state["rows"] = await db_call(runtime, read)
            if old != (state["experiment"], state["rows"]):
                render()
            if state["experiment"]["status"] not in ("queued", "running", "termination_requested"):
                timer.deactivate()
        except Exception as exc:
            timer.deactivate()
            notify_error(exc)

    async def terminate() -> None:
        try:
            await db_call(
                runtime, lambda session: service_type(session).request_termination(experiment_id)
            )
            timer.activate()
        except Exception as exc:
            notify_error(exc)

    previous.on_click(lambda: move(-1))
    following.on_click(lambda: move(1))
    overlay.on_value_change(lambda _: render())
    terminate_button.on_click(terminate)
    timer = ui.timer(1, refresh, immediate=False)
    await refresh()
