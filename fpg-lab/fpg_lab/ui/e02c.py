"""Setup and inspect opening generation on portable plans."""

import json
from math import hypot

from nicegui import run, ui
from nicegui.elements.dialog import Dialog
from sqlalchemy import select

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.database.models import E02BSavedPlan, E02CRun
from fpg_lab.database.serialization import row_document
from fpg_lab.flows.e02b import delete_layout, save_layout
from fpg_lab.flows.e02c import start
from fpg_lab.integrations.fpg_core.floor_plan import decode_plan
from fpg_lab.services.common import SystemConfigurationService
from fpg_lab.ui.components import (
    action_button,
    db_call,
    editor_value,
    json_panel,
    notify_error,
    profile_picker,
    shell,
)
from fpg_lab.ui.result_layout import ResultWorkspace
from fpg_lab.visualization import e02b as plots
from fpg_lab.visualization import figures

PATH = "/experiments/e02c"


async def main_page(runtime):
    shell("E-02-C - Floor Plan Opening Generation", compact=True, back_link="/")
    plan_state = {"document": None, "layout_id": None}
    import_dialog: Dialog
    config_dialog: Dialog
    history_dialog: Dialog
    with ui.element("div").classes("lab-setup-grid"):
        with ui.column().classes("lab-setup-main"):
            layout_status = ui.label("Select or import a floor plan.").classes("text-sm lab-muted")
            preview = ui.plotly(figures.floor_plan(None)).classes("lab-setup-plot")
        with ui.column().classes("lab-setup-sidebar"):
            profile = await profile_picker(runtime)
            profile.classes("w-full")
            saved = ui.select({}, label="Saved floor plans", clearable=True).props("dense outlined").classes("w-full")
            regenerate = ui.checkbox("Replace existing openings", value=False)
            launch = action_button("Run", role="main").classes("w-full")
            launch.disable()
            action_button("Import", icon="upload", on_click=lambda: import_dialog.open()).props("dense outline")
            remove = action_button("Delete", role="danger").props("dense flat")
            remove.disable()
            ui.separator()
            action_button("Opening settings", role="subtle", on_click=lambda: config_dialog.open()).props("dense")
            action_button("History", role="subtle", on_click=lambda: history_dialog.open()).props("dense")

    with ui.dialog() as import_dialog, ui.card().classes("w-[52rem] max-w-full gap-3"):
        ui.label("Import floor plan").classes("text-lg font-semibold")
        paste = ui.textarea("Portable floor-plan JSON").props("outlined rows=10").classes("w-full")
        with ui.row().classes("w-full items-center"):
            import_button = action_button("Preview").props("dense")
            name = ui.input("Save as").props("dense outlined maxlength=120").classes("flex-1")
            save = action_button("Save").props("dense outline")
            save.disable()
            action_button("Close", role="subtle", on_click=import_dialog.close).props("dense")

    with ui.dialog() as config_dialog, ui.card().classes("w-[60rem] max-w-full max-h-[85vh] overflow-auto"):
        ui.label("Opening settings").classes("text-lg font-semibold")
        config_status = ui.label().classes("text-sm whitespace-pre-wrap")
        with ui.row().classes("gap-2"):
            apply_config = action_button("Save", role="main").props("dense")
            check_config = action_button("Validate").props("dense outline")
            discard_config = action_button("Reload", role="subtle").props("dense")
            action_button("Close", role="subtle", on_click=config_dialog.close).props("dense")
        config_area = ui.column().classes("w-full gap-2")

    with ui.dialog() as history_dialog, ui.card().classes("w-[32rem] max-w-full max-h-[80vh] overflow-auto"):
        ui.label("Recent runs").classes("text-lg font-semibold")
        history = await db_call(runtime, lambda session: session.execute(
            select(E02CRun.id, E02CRun.status).order_by(E02CRun.id.desc()).limit(50)
        ).all())
        if not history:
            ui.label("No saved runs yet.").classes("text-sm lab-muted")
        for run_id, status in history:
            ui.link(f"Run #{run_id} - {plots.label(status)}", f"{PATH}/runs/{run_id}")
        action_button("Close", role="subtle", on_click=history_dialog.close).props("dense")

    def show_document(document, layout_id, name_text):
        plan_state.update(document=document, layout_id=layout_id, configuration_id=profile.value, regenerate=regenerate.value)
        plan = document["floor_plan"] if document else None
        units = document["project_units_per_meter"] if document else None
        preview.figure = figures.floor_plan(
            plan, title="Imported floor plan" if plan else "Floor plan preview"
        )
        if units:
            preview.figure.update_xaxes(title=f"X · project units ({units} u/m)")
        preview.update()
        layout_status.set_text(
            f"{name_text} · {len(plan['rooms'])} rooms · {units} units/m"
            if plan
            else "Select or import a floor plan."
        )
        save.set_enabled(document is not None and layout_id is None)
        launch.set_enabled(document is not None)
        remove.set_enabled(layout_id is not None)

    async def refresh_saved():
        options = await db_call(
            runtime,
            lambda session: dict(
                session.execute(
                    select(E02BSavedPlan.id, E02BSavedPlan.name).order_by(
                        E02BSavedPlan.name, E02BSavedPlan.id
                    )
                ).all()
            ),
        )
        saved.set_options(
            {key: f"{value} · #{key}" for key, value in options.items()},
            value=plan_state["layout_id"],
        )

    async def select_saved(event):
        if event.value == plan_state["layout_id"] or event.value != saved.value:
            return
        try:
            if event.value is None:
                show_document(None, None, "")
                return

            def read(session):
                row = session.get(E02BSavedPlan, event.value)
                if row is None:
                    raise ValueError("The selected floor plan has been deleted")
                return row.document, row.name

            document, saved_name = await db_call(runtime, read)
            if saved.value == event.value:
                show_document(document, event.value, saved_name)
        except Exception as exc:
            if saved.value == event.value:
                show_document(None, None, "")
                await refresh_saved()
            notify_error(exc)

    async def import_plan():
        try:
            document = to_jsonable(json.loads(paste.value))
            await run.io_bound(decode_plan, document)
            show_document(document, None, "Temporary import")
            saved.set_value(None)
        except Exception as exc:
            notify_error(exc)

    async def save_plan():
        try:
            document, title = plan_state["document"], (name.value or "").strip()
            layout_id = await db_call(
                runtime, lambda session: save_layout(session, title, document)
            )
            show_document(document, layout_id, title)
            await refresh_saved()
        except Exception as exc:
            notify_error(exc)

    async def remove_plan():
        item = plan_state["layout_id"]
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Delete saved layout #{item}?")
            with ui.row():
                action_button("Cancel", role="subtle", on_click=lambda: dialog.submit(False))
                action_button("Delete layout", role="danger", on_click=lambda: dialog.submit(True))
        if not await dialog:
            return
        try:
            await db_call(runtime, lambda session: delete_layout(session, item))
            if plan_state["layout_id"] == item:
                show_document(None, None, "")
            await refresh_saved()
        except Exception as exc:
            notify_error(exc)

    async def launch_run():
        launch.disable()
        try:
            layout_id = plan_state["layout_id"]
            document = plan_state["document"] if layout_id is None else None
            run_id = await run.io_bound(start, runtime, document=document, layout_id=layout_id, configuration_id=profile.value, regenerate=regenerate.value)
            ui.navigate.to(f"{PATH}/runs/{run_id}")
        except Exception as exc:
            launch.set_enabled(plan_state["document"] is not None)
            notify_error(exc)

    saved.on_value_change(select_saved)
    import_button.on_click(import_plan)
    save.on_click(save_plan)
    remove.on_click(remove_plan)
    launch.on_click(launch_run)
    await refresh_saved()
    await _config_editor(
        runtime, profile, config_area, config_status, apply_config, check_config, discard_config
    )


async def _config_editor(runtime, profile, area, feedback, save, validate, discard):
    loaded = None
    editor = None
    load_number = 0

    async def load_saved():
        nonlocal loaded, editor, load_number
        load_number += 1
        current = load_number
        loaded = None
        area.clear()
        save.disable()
        try:
            def read(session):
                record, validated = SystemConfigurationService(session, runtime.codec).for_flow(profile.value, "e02c")
                return record.id, record.config_hash, validated.payload
            profile_id, expected, payload = await db_call(runtime, read)
            if current != load_number:
                return
            loaded = (profile_id, expected, payload)
            with area:
                ui.label("Dimensions, geometry, room connections, accessibility, priorities and solver settings").classes("text-sm lab-muted")
                editor = ui.json_editor({"content": {"json": payload["openings"]}, "mode": "tree"}).classes("w-full")
            save.enable()
            feedback.set_text("Saved opening settings loaded.")
        except Exception as exc:
            if current == load_number:
                feedback.set_text(str(exc))

    async def check():
        try:
            payload = {**loaded[2], "openings": await editor_value(editor)}
            await run.io_bound(runtime.codec.validate_for_flow, payload, "e02c")
            feedback.set_text("Configuration is valid.")
        except Exception as exc:
            feedback.set_text(str(exc))

    async def persist():
        nonlocal loaded
        if loaded is None:
            return
        saved = loaded
        save.disable()
        try:
            value = await editor_value(editor)
            new_hash = await db_call(runtime, lambda session: SystemConfigurationService(session, runtime.codec).save_section(saved[0], "openings", value, expected_hash=saved[1]).config_hash)
            if loaded == saved:
                loaded = (saved[0], new_hash, {**saved[2], "openings": value})
                feedback.set_text("Opening settings saved.")
        except Exception as exc:
            feedback.set_text(str(exc))
        finally:
            if loaded and loaded[0] == saved[0]:
                save.enable()

    save.on_click(persist)
    validate.on_click(check)
    discard.on_click(load_saved)
    profile.on_value_change(load_saved)
    await load_saved()


def opening_label(opening, rooms):
    names = [rooms.get(room_id, str(room_id)) for room_id in opening.get("connected_room_ids", [])]
    connection = " ? ".join(names) if names else "Exterior"
    if len(names) == 1:
        connection += " ? Exterior"
    return f"{connection} ? {plots.label(opening['purpose'])}"


def opening_figure(plan, generated, original, show_doors, show_windows, show_original, selected):
    chart = figures.floor_plan({**plan, "openings": []})
    chart.update_traces(showlegend=False)
    chart.update_layout(
        title=None, uirevision="e02c-plan", margin=dict(l=10, r=10, t=10, b=10),
        dragmode="pan", legend=dict(orientation="h", x=0, y=1, yanchor="top",
                                    itemclick=False, itemdoubleclick=False),
    )
    chart.update_xaxes(title=None, showgrid=False, showticklabels=False, ticks="")
    chart.update_yaxes(title=None, showgrid=False, showticklabels=False, ticks="")
    points = [point for polygon in [plan.get("boundary"), *(r.get("boundary") for r in plan.get("rooms", []))]
              for point in (polygon or {}).get("points", [])]
    if points:
        xs, ys = [p["x"] for p in points], [p["y"] for p in points]
        padding = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.03 or 1
        chart.update_xaxes(range=[min(xs) - padding, max(xs) + padding])
        chart.update_yaxes(range=[min(ys) - padding, max(ys) + padding])
    seen = set()
    for source, openings in (("Generated", generated), ("Original", original)):
        for index, opening in enumerate(openings):
            kind = opening["opening_type"]
            visible = (show_doors if kind == "door" else show_windows) and (source == "Generated" or show_original)
            start, end = opening["start"], opening["end"]
            focused = visible and selected == (source, index)
            chart.add_scatter(
                x=[start["x"], end["x"]], y=[start["y"], end["y"]], mode="lines",
                name=kind.title(), legendgroup=kind, showlegend=visible and kind not in seen,
                visible=visible,
                line=dict(color="#ffffff" if focused else ("#75beff" if kind == "window" else "#dcdcaa"),
                          width=10 if focused else 6, dash="dash" if source == "Original" else "solid"),
                hovertext=f"{source} {kind}", hoverinfo="text",
            )
            if visible:
                seen.add(kind)
    return chart


async def run_page(runtime, run_id):
    workspace = ResultWorkspace(f"E-02-C run #{run_id}", back_link=PATH)
    workspace.main("Canvas").classes("lab-replay-pane")
    with workspace.controls:
        status = ui.label("Loading run?").classes("font-semibold")
        provenance = ui.label().classes("text-sm lab-muted")
        error = ui.label().classes("text-sm whitespace-pre-wrap").style(f"color: {plots.FAIL}")
    with workspace.main("Canvas"):
        chart = ui.plotly(figures.floor_plan(None)).classes("lab-primary-plot")
    context = workspace.context("Canvas")

    async def refresh():
        record = await db_call(runtime, lambda session: row_document(row) if (row := session.get(E02CRun, run_id)) else None)
        if record is None:
            status.set_text("Run not found")
            timer.deactivate()
            return
        snapshot = record["snapshot"]
        status.set_text(plots.label(record["status"]).capitalize())
        provenance.set_text(f"{snapshot['layout_name']} ? Core {snapshot['core_version']} ? {snapshot['configuration_hash'][:12]}")
        original = snapshot["input"]
        plan = original["floor_plan"]
        if record["status"] in {"queued", "running"}:
            chart.figure = opening_figure(plan, [], plan.get("openings", []), True, True, True, None)
            chart.update()
            timer.activate()
            return
        timer.deactivate()
        if record["duration_seconds"] is not None:
            status.set_text(f"{status.text} ? {record['duration_seconds']:.3f} s")
        if record["error"]:
            error.set_text(f"{plots.label(record['error']['stage'])} ? {record['error']['message']}")
        result = record["result"] or {}
        generated_plan = result.get("floor_plan") if record["status"] == "completed" else None
        generated = (generated_plan or {}).get("openings", [])
        original_openings = plan.get("openings", [])
        rooms = {room["id"]: room.get("name") or room["id"] for room in plan.get("rooms", [])}
        choices = [(source, i, opening) for source, openings in (("Generated", generated), ("Original", original_openings))
                   for i, opening in enumerate(openings)]
        with context:
            ui.label(f"{sum(o['opening_type'] == 'door' for o in generated)} doors ? {sum(o['opening_type'] == 'window' for o in generated)} windows").classes("text-sm font-medium")
            ui.label("Opening visibility").classes("font-semibold text-sm")
            doors = ui.checkbox("Doors", value=True).props("dense")
            windows = ui.checkbox("Windows", value=True).props("dense")
            show_original = ui.checkbox("Original openings", value=not bool(generated_plan)).props("dense") if original_openings else None
            ui.label("Inspect opening").classes("font-semibold text-sm")
            picker = ui.select(
                {f"{source}:{i}": f"{opening_label(opening, rooms)} ? {source} {opening['opening_type']}"
                 for source, i, opening in choices}, label="Opening", clearable=True,
            ).props("dense outlined").classes("w-full")
            details = ui.column().classes("w-full gap-1")
            if generated_plan:
                document = {**original, "floor_plan": generated_plan}
                def copy_plan():
                    ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(json.dumps(document))})")
                    ui.notify("Generated floor plan copied")
                action_button("Copy generated plan", icon="content_copy", on_click=copy_plan).props("dense outline")
            with ui.expansion("Diagnostics").props("dense").classes("w-full"):
                json_panel("Generation result", result)
                json_panel("Core diagnostics", record["diagnostics"])
                json_panel("Run snapshot", snapshot)
                if record["error"]:
                    json_panel("Error details", record["error"])

        def redraw():
            selected = next(((source, i, opening) for source, i, opening in choices if picker.value == f"{source}:{i}"), None)
            chart.figure = opening_figure(plan, generated, original_openings, doors.value, windows.value,
                                          show_original.value if show_original else False,
                                          selected[:2] if selected else None)
            chart.update()
            details.clear()
            if selected:
                opening = selected[2]
                start, end = opening["start"], opening["end"]
                width = hypot(end["x"] - start["x"], end["y"] - start["y"])
                with details:
                    ui.label(opening_label(opening, rooms)).classes("text-sm font-medium")
                    ui.label(f"{opening['opening_type'].title()} ? {width:.3g} project units").classes("text-sm")
                    json_panel("Technical details", opening)
        doors.on_value_change(redraw)
        windows.on_value_change(redraw)
        if show_original:
            show_original.on_value_change(redraw)
        def select_opening():
            selected = next(((source, opening) for source, i, opening in choices if picker.value == f"{source}:{i}"), None)
            if selected:
                source, opening = selected
                (doors if opening["opening_type"] == "door" else windows).set_value(True)
                if source == "Original" and show_original:
                    show_original.set_value(True)
            redraw()
        picker.on_value_change(select_opening)
        redraw()

    timer = ui.timer(0.75, refresh, active=False, immediate=False)
    await refresh()
