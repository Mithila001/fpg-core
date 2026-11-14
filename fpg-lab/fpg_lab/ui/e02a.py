"""Setup and inspection for file-backed solver runs."""
from nicegui import app, run, ui
from sqlalchemy import select

from fpg_lab.database.models.e02 import E02Run
from fpg_lab.flows.e02a import CONFIG_PATH, prepare, retry, start
from fpg_lab.integrations.fpg_core.e02a_input import load_hint_maps
from fpg_lab.runtime import row_document
from fpg_lab.visualization import figures
from fpg_lab.ui.components import action_button, db_call, json_panel, notify_error, shell
from fpg_lab.ui.result_layout import ResultWorkspace


async def main_page(runtime):
    await ui.context.client.connected()
    shell("E-02-A · Setup", "Run the solver pipeline with file-backed hint maps.")
    ui.label(f"Configuration: {CONFIG_PATH}").classes("text-sm lab-muted")
    try:
        maps = load_hint_maps()
    except Exception as exc:
        maps = {}
        ui.label(str(exc)).classes("text-rose-300")
    if not maps:
        ui.label("No hint maps are available. Add the supplied portable maps to hint_maps.json.").classes("text-amber-300")
    values = {"__all__": "All maps", **{name: name for name in maps}}
    stored_map = app.storage.tab.get("e02a_hint_map")
    default_map = next(iter(maps), "__all__")
    picker = ui.select(values, label="Hint map", value=stored_map if stored_map in values else default_map).classes("min-w-80")
    stored_count = app.storage.tab.get("e02a_refinement_count", 0)
    refinement_count = ui.radio({count: str(count) for count in range(6)}, value=stored_count if stored_count in range(6) else 0).props("inline")
    ui.label("Refinement stage count")
    feedback = ui.label().classes("text-sm whitespace-pre-wrap")

    def selection():
        if picker.value is None:
            raise ValueError("Select a hint map")
        return None if picker.value == "__all__" else picker.value

    picker.on_value_change(lambda event: app.storage.tab.update(e02a_hint_map=event.value))
    refinement_count.on_value_change(
        lambda event: app.storage.tab.update(e02a_refinement_count=event.value)
    )

    async def validate():
        try:
            await run.io_bound(prepare, runtime.codec, selection(), refinement_count.value)
            feedback.set_text("Configuration and selected maps are valid.")
        except Exception as exc:
            feedback.set_text(str(exc))

    async def submit():
        try:
            run_id = await run.io_bound(start, runtime, selection(), refinement_count.value)
            ui.navigate.to(f"/experiments/e02a/runs/{run_id}")
        except Exception as exc:
            feedback.set_text(str(exc))

    with ui.row():
        action_button("Validate", on_click=validate)
        action_button("Start generation", role="main", on_click=submit)
    ui.label("Run history").classes("text-lg font-semibold mt-4")
    records = await db_call(runtime, lambda session: [row_document(row) for row in session.scalars(select(E02Run).order_by(E02Run.id.desc()).limit(50))])
    for record in records:
        ui.link(f"Run #{record['id']} · {record['status']}", f"/experiments/e02a/runs/{record['id']}")


async def run_page(runtime, experiment_id):
    state = {"record": None, "case": None, "stage": None}
    workspace = ResultWorkspace(f"E-02-A run #{experiment_id}", back_link="/experiments/e02a", views=("Canvas", "Scores", "Diagnostics"))
    with workspace.main("Canvas"):
        chart = ui.plotly(figures.floor_plan(None)).classes("lab-primary-plot")
    with workspace.main("Scores"):
        scores = ui.column().classes("w-full")
    with workspace.main("Diagnostics"):
        diagnostics = ui.column().classes("w-full")
    with workspace.controls:
        status = ui.label("Loading…")
        case_picker = ui.select({}, label="Case").classes("w-full")
        stage_picker = ui.radio({}, value=None).props("inline")
        stage_label = ui.label("Stage").classes("font-semibold text-sm")
        terminate = action_button("Terminate run", role="danger").props("outline dense")
        retry_button = action_button("Retry run", role="main").props("dense")
    with workspace.context("Canvas"):
        details = ui.column().classes("w-full")

    def render():
        item = state["record"]
        if not item:
            return
        cases = item["cases"]
        status.set_text(f"{item['status']} · {len(cases)} / {len(item['snapshot']['maps'])} cases")
        terminate.set_enabled(item["status"] in ("queued", "running", "termination_requested"))
        retry_button.set_enabled(item["status"] not in ("queued", "running", "termination_requested"))
        case_picker.options = {i: case["name"] for i, case in enumerate(cases)}
        if case_picker.value not in case_picker.options:
            case_picker.value = 0 if cases else None
        case_picker.update()
        case = cases[case_picker.value] if case_picker.value is not None else None
        stages = case["stages"] if case else []
        stage_picker.options = {stage["name"]: stage["name"] for stage in stages}
        if stage_picker.value not in stage_picker.options:
            stage_picker.value = stages[0]["name"] if stages else None
        stage_label.set_visibility(bool(stages))
        stage_picker.set_visibility(bool(stages))
        stage_picker.update()
        stage = next((entry for entry in stages if entry["name"] == stage_picker.value), None)
        data = stage["data"] if stage else {}
        chart.figure = figures.floor_plan((data.get("result") or {}).get("floor_plan"))
        chart.update()
        details.clear()
        with details:
            if case:
                score = ((case.get("scoring") or {}).get("result") or {}).get("total_score")
                ui.label(f"{case['status']} · score {score if score is not None else '—'} · {case.get('duration_ms', 0)} ms")
                if case.get("error"):
                    ui.label(f"{case['error']['stage']}: {case['error']['message']}").classes("text-amber-300")
            else:
                ui.label("Waiting for a case.")
            if item.get("error"):
                ui.label(item["error"]["message"]).classes("text-rose-300")
        scores.clear()
        with scores:
            if case and case.get("scoring"):
                scoring = case["scoring"].get("result") or case["scoring"]
                ui.plotly(figures.score_breakdown(scoring)).classes("w-full h-[32rem]")
                json_panel("Scoring details", case["scoring"])
            else:
                ui.label("No score recorded.")
        diagnostics.clear()
        with diagnostics:
            json_panel("Run snapshot", item["snapshot"])
            if case:
                json_panel("Case and stage diagnostics", case)

    async def refresh():
        try:
            def read(session):
                row = session.get(E02Run, experiment_id)
                if row is None:
                    raise ValueError("Run not found")
                return row_document(row)
            item = await db_call(runtime, read)
            if item != state["record"]:
                state["record"] = item
                render()
            if item["status"] not in ("queued", "running", "termination_requested"):
                timer.deactivate()
        except Exception as exc:
            timer.deactivate()
            notify_error(exc)

    async def stop():
        def request(session):
            row = session.get(E02Run, experiment_id)
            if row and row.status in ("queued", "running"):
                row.status = "termination_requested"
                session.commit()
        await db_call(runtime, request)
        timer.activate()

    async def rerun():
        try:
            new_run_id = await run.io_bound(retry, runtime, experiment_id)
            ui.navigate.to(f"/experiments/e02a/runs/{new_run_id}")
        except Exception as exc:
            notify_error(exc)

    case_picker.on_value_change(lambda _: render())
    stage_picker.on_value_change(lambda _: render())
    terminate.on_click(stop)
    retry_button.on_click(rerun)
    timer = ui.timer(1, refresh, immediate=False)
    await refresh()
