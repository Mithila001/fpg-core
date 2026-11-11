"""Preset management and geometry inspection for P01B."""

import json
from typing import Any

import plotly.graph_objects as go
from nicegui import run, ui
from sqlalchemy import select

from fpg_lab.database.models import P01BIteration, P01BPreset
from fpg_lab.integrations.fpg_core.p01b_input import validate_export
from fpg_lab.runtime import row_document
from fpg_lab.services.common import SystemConfigurationService
from fpg_lab.services.p01b import P01BService
from fpg_lab.services.p01c import P01CService
from fpg_lab.ui.components import db_call, json_panel, notify_error, shell
from fpg_lab.visualization import figures


async def main_page(runtime, flow="p01b"):
    service_type = P01CService if flow == "p01c" else P01BService
    shell(f"{flow.upper()} experiments", "Inspect repeated floor-plan generation and refinement.")
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
                    row = P01BPreset(name=name.value.strip(), data=state["data"])
                    session.add(row)
                    session.commit()
                    return row.id

                selected = await db_call(runtime, create)
                dialog.close()
                await refresh()
                presets.set_value(selected)
            except Exception as exc:
                notify_error(exc)

        ui.button("Save preset", on_click=save)

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
                "preset_id": presets.value,
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

    presets.on_value_change(show_preset)
    configs.on_value_change(update_time)
    history_page.on_value_change(refresh)
    with controls, ui.row():
        ui.button("Import preset", on_click=dialog.open)
        ui.button("Delete preset", on_click=delete).props("outline")
        ui.button("Start experiment", on_click=start)
        ui.button("Refresh history", on_click=refresh).props("flat")
    await refresh()


async def run_page(runtime, experiment_id, flow="p01b"):
    service_type = P01CService if flow == "p01c" else P01BService
    shell(f"{flow.upper()} run #{experiment_id}", compact=True, back_link=f"/experiments/{flow}")
    state: dict[str, Any] = {"iteration": 0, "stage": 0, "rows": [], "experiment": None}
    status = ui.label()
    with ui.row().classes("items-center"):
        previous = ui.button("Previous")
        position = ui.label()
        following = ui.button("Next")
        overlay = ui.checkbox("Show original hint points", value=False)
    stages_area = ui.row()
    result_area = ui.column().classes("w-full")

    def render():
        rows = state["rows"]
        item = state["experiment"]
        if not item:
            return
        if not item.get("hint_points") or "preset" not in item["hint_points"]:
            status.set_text("This is a legacy P01B run and cannot be displayed by the replacement.")
            return
        status.set_text(
            f"{item['status']} · {item['completed_trial_count']}/{item['requested_trial_count']} iterations"
        )
        overlay.set_enabled(not item["hint_points"]["disable_hints"])
        previous.set_enabled(state["iteration"] > 0)
        following.set_enabled(state["iteration"] + 1 < len(rows))
        position.set_text(f"Iteration {state['iteration'] + 1} / {item['requested_trial_count']}")
        stages_area.clear()
        result_area.clear()
        if not rows:
            return
        row = rows[state["iteration"]]
        stages = row["stages"]
        selected_name = state.get("selected_stage", "Initial")
        state["stage"] = next(
            (i for i, stage in enumerate(stages) if stage["name"] == selected_name), 0
        )
        with stages_area:
            for index, stage in enumerate(stages):
                ui.button(stage["name"], on_click=lambda index=index: select_stage(index)).props(
                    "outline" if index != state["stage"] else ""
                )
        with result_area:
            score = ((row.get("scoring") or {}).get("result") or {}).get("total_score")
            ui.label(
                f"{row['status']} · score: {score if score is not None else 'unavailable'} · {row['duration_ms']} ms"
            )
            if row.get("error"):
                ui.label(f"{row['error']['stage']}: {row['error']['message']}").classes(
                    "text-amber-300"
                )
            data = stages[state["stage"]]["data"] if stages else None
            if stages:
                ui.label(
                    f"Stage duration: {stages[state['stage']].get('duration_ms', 0)} ms"
                ).classes("text-sm")
            plan = ((data or {}).get("result") or {}).get("floor_plan")
            chart = figures.floor_plan(plan)
            if overlay.value and not item["hint_points"]["disable_hints"]:
                for trace in chart.data:
                    trace.opacity = 0.35
                for point in item["hint_points"]["preset"]["candidate"]["points"]:
                    chart.add_trace(
                        go.Scatter(
                            x=[point["x"]],
                            y=[point["y"]],
                            mode="markers+text",
                            text=[point["room_id"]],
                            textposition="top center",
                            name=point["room_id"],
                            marker={"size": 12, "color": figures.color(point["room_id"])},
                        )
                    )
            chart.update_layout(showlegend=False)
            with ui.element("div").classes(
                "w-full grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(15rem,1fr)] gap-5 items-start"
            ):
                ui.plotly(chart).classes("w-full h-[36rem] min-w-0")
                with ui.column().classes("w-full gap-2"):
                    ui.label("Rooms").classes("text-lg font-semibold")
                    for room in (plan or {}).get("rooms", []):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon(
                                "square",
                                color=figures.color(str(room.get("room_type", room["id"]))),
                            )
                            ui.label(room.get("name") or room["id"])
                    if not plan:
                        ui.label("No floor plan available for this stage.").classes("lab-muted")
            if flow == "p01c":
                opening_stage = next((stage for stage in stages if stage["name"] == "Openings"), None)
                final_plan = (((opening_stage or {}).get("data") or {}).get("result") or {}).get("floor_plan")
                if final_plan:
                    document = {"version": 1, "project_units_per_meter": item["system_configuration_snapshot"]["project_units_per_meter"], "floor_plan": final_plan}
                    def copy_plan():
                        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(json.dumps(document))})")
                        ui.notify("Floor plan and openings copied")
                    ui.button("Copy final floor plan", icon="content_copy", on_click=copy_plan).props("outline")
            if data:
                json_panel("Stage details", data)
            if row.get("scoring"):
                json_panel("Scoring details", row["scoring"])

    def select_stage(index):
        state["stage"] = index
        state["selected_stage"] = state["rows"][state["iteration"]]["stages"][index]["name"]
        render()

    def move(delta):
        state["iteration"] += delta
        render()

    async def refresh():
        try:

            def read(session):
                experiment = service_type(session).get_experiment(experiment_id)
                rows = session.scalars(
                    select(P01BIteration)
                    .where(P01BIteration.experiment_id == experiment_id)
                    .order_by(P01BIteration.number)
                )
                return row_document(experiment), [row_document(row) for row in rows]

            state["experiment"], state["rows"] = await db_call(runtime, read)
            render()
            if state["experiment"]["status"] not in ("queued", "running", "termination_requested"):
                timer.deactivate()
        except Exception as exc:
            timer.deactivate()
            notify_error(exc)

    async def terminate():
        await db_call(
            runtime, lambda session: service_type(session).request_termination(experiment_id)
        )

    previous.on_click(lambda: move(-1))
    following.on_click(lambda: move(1))
    overlay.on_value_change(render)
    ui.button("Terminate", on_click=terminate).props("outline")
    timer = ui.timer(1, refresh, immediate=False)
    await refresh()
