"""Setup and run inspection for the final floor-plan scoring experiment."""

import asyncio
import json
from typing import Any

from nicegui import run, ui
from nicegui.elements.dialog import Dialog
from sqlalchemy import select

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.database.models import E02BRun, E02BSavedPlan
from fpg_lab.database.serialization import row_document
from fpg_lab.flows.e02b import delete_layout, save_layout, start
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

PATH = "/experiments/e02b"
VIEWS = {
    "Overview": None,
    "Geometry integrity": "geometry_integrity",
    "Required adjacency": "required_adjacency",
    "Enclosed voids": "enclosed_voids",
    "Inward recesses": "inward_recess",
    "Room size consistency": "room_size_consistency",
    "Kitchen–dining proximity": "kitchen_dining_proximity",
}


async def main_page(runtime):
    shell("E-02-B - Floor plan evaluation", compact=True, back_link="/")
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
            launch = action_button("Run", role="main").classes("w-full")
            launch.disable()
            action_button("Import", icon="upload", on_click=lambda: import_dialog.open()).props("dense outline")
            remove = action_button("Delete", role="danger").props("dense flat")
            remove.disable()
            ui.separator()
            action_button("Scoring settings", role="subtle", on_click=lambda: config_dialog.open()).props("dense")
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
        ui.label("Scoring settings").classes("text-lg font-semibold")
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
            select(E02BRun.id, E02BRun.status).order_by(E02BRun.id.desc()).limit(50)
        ).all())
        if not history:
            ui.label("No saved runs yet.").classes("text-sm lab-muted")
        for run_id, status in history:
            ui.link(f"Run #{run_id} - {plots.label(status)}", f"{PATH}/runs/{run_id}")
        action_button("Close", role="subtle", on_click=history_dialog.close).props("dense")

    def show_document(document, layout_id, name_text):
        plan_state.update(document=document, layout_id=layout_id, configuration_id=profile.value)
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
            run_id = await run.io_bound(start, runtime, document=document, layout_id=layout_id, configuration_id=profile.value)
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
    load_number = 0
    groups: list[tuple[dict[str, Any], ui.checkbox, ui.number]] = []
    rules: list[
        tuple[dict[str, Any], ui.checkbox, ui.number, ui.number | None, ui.json_editor]
    ] = []

    def show(document):
        area.clear()
        groups.clear()
        rules.clear()
        with area:
            ui.label("Groups").classes("font-semibold")
            for group in document["groups"]:
                with ui.row().classes("w-full items-center justify-between"):
                    enabled = ui.checkbox(
                        plots.label(group["key"]).capitalize(), value=group["enabled"]
                    )
                    if group["key"] == "critical":
                        enabled.disable()
                    weight = (
                        ui.number("Group weight", value=group["weight"])
                        .props("dense outlined")
                        .classes("w-28")
                    )
                groups.append((group, enabled, weight))
            ui.separator()
            ui.label("Evaluators").classes("font-semibold")
            for rule in document["evaluators"]:
                with ui.row().classes("w-full items-center gap-2"):
                    enabled = ui.checkbox(
                        plots.label(rule["key"]).capitalize(), value=rule["enabled"]
                    ).classes("flex-1")
                    weight = (
                        ui.number("Weight", value=rule["weight"])
                        .props("dense outlined")
                        .classes("w-20")
                    )
                    threshold = None
                    if rule["group_key"] == "critical":
                        threshold = (
                            ui.number("Threshold", value=rule["minimum_score"], min=0, max=100)
                            .props("dense outlined")
                            .classes("w-24")
                        )
                with (
                    ui.expansion(f"{plots.label(rule['key']).capitalize()} settings")
                    .props("dense")
                    .classes("w-full lab-panel")
                ):
                    editor = ui.json_editor(
                        {"content": {"json": rule["settings"]}, "mode": "tree"}
                    ).classes("w-full max-h-64")
                rules.append((rule, enabled, weight, threshold, editor))

    async def draft():
        settings = await asyncio.gather(*(editor_value(item[-1]) for item in rules))
        return {
            "groups": [
                {**group, "enabled": enabled.value, "weight": weight.value}
                for group, enabled, weight in groups
            ],
            "evaluators": [
                {
                    **rule,
                    "enabled": enabled.value,
                    "weight": weight.value,
                    "minimum_score": threshold.value if threshold else None,
                    "settings": values,
                }
                for (rule, enabled, weight, threshold, _), values in zip(
                    rules, settings, strict=True
                )
            ],
        }

    async def load_saved():
        nonlocal loaded, load_number
        load_number += 1
        current = load_number
        profile_id = profile.value
        loaded = None
        area.clear()
        save.disable()
        try:
            def read(session):
                record, validated = SystemConfigurationService(session, runtime.codec).for_flow(
                    profile_id, "e02b"
                )
                return record.id, record.config_hash, validated.payload["floor_plan_scoring"]

            profile_id, expected, document = await db_call(runtime, read)
            if current == load_number:
                loaded = profile_id, expected
                show(document)
                save.enable()
                feedback.set_text("Saved scoring settings loaded.")
        except Exception as exc:
            if current == load_number:
                feedback.set_text(str(exc))

    async def check():
        try:
            await run.io_bound(runtime.codec.decode_floor_scoring, await draft())
            feedback.set_text("Configuration is valid.")
        except Exception as exc:
            feedback.set_text(str(exc))

    async def persist():
        nonlocal loaded
        if loaded is None:
            return
        saved_profile = loaded
        profile_id, expected = saved_profile
        save.disable()
        try:
            document = await draft()
            new_hash = await db_call(runtime, lambda session: (
                SystemConfigurationService(session, runtime.codec).save_section(
                    profile_id, "floor_plan_scoring", document, expected_hash=expected
                ).config_hash
            ))
            if loaded == saved_profile:
                loaded = profile_id, new_hash
                feedback.set_text("Scoring settings saved.")
        except Exception as exc:
            if loaded == saved_profile:
                feedback.set_text(str(exc))
        finally:
            if loaded and loaded[0] == profile_id:
                save.enable()

    save.on_click(persist)
    validate.on_click(check)
    discard.on_click(load_saved)
    profile.on_value_change(load_saved)
    await load_saved()


def _table(rows):
    columns = [{"name": key, "label": key, "field": key, "align": "left"} for key in rows[0]]
    table = (
        ui.table(columns=columns, rows=rows, row_key=columns[0]["name"], pagination=0)
        .props("dense flat bordered hide-bottom")
        .classes("w-full")
    )
    for column in ("Gate", "Status"):
        if column not in rows[0]:
            continue
        table.add_slot(
            f"body-cell-{column}",
            f"""
            <q-td :props="props" :style="{{color: ({{
                'Passed': '{plots.PASS}', 'Satisfied': '{plots.PASS}',
                'Failed': '{plots.FAIL}', 'failed': '{plots.FAIL}',
                'Outside preference': '{plots.FAIL}', 'unavailable': '{plots.WARN}'
            }})[props.value]}}">{{{{ props.value }}}}</q-td>
        """,
        )


def _measurements(data):
    with ui.element("dl").classes(
        "grid w-full grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-2 gap-y-1 text-sm"
    ):
        for key, value in data.items():
            with ui.element("dt").classes("lab-muted"):
                ui.label(key)
            with ui.element("dd").classes("text-right break-words"):
                ui.label(str(value))


def _overview(workspace, official, diagnostic, snapshot):
    result, details = official["result"], official["details"]
    completed = [item for item in details["evaluator_results"] if item["raw_score"] is not None]
    officially_listed = {item["evaluator_key"] for item in details["evaluator_results"]}
    with workspace.main("Overview"):
        ui.label("Official scoring").classes("text-lg font-semibold")
        score_plot = figures.score_breakdown(
            {
                "evaluator_results": [
                    {**item, "evaluator_key": plots.label(item["evaluator_key"])}
                    for item in completed
                ]
            }
        )
        score_plot.update_layout(title=None, margin={"t": 10, "b": 85}, yaxis_range=[0, 105])
        ui.plotly(score_plot).classes("w-full h-[290px]")
        configured = {group["key"]: group for group in snapshot["configuration"]["groups"]}
        _table(
            [
                {
                    "Group": plots.label(group["group_key"]),
                    "Status": plots.label(group["status"]),
                    "Raw score": plots.number(group["raw_score"]),
                    "Weight": plots.number(configured[group["group_key"]]["weight"]),
                    "Allocation": plots.number(group["normalized_maximum"]),
                    "Contribution": plots.number(group["contribution"])
                    if group["raw_score"] is not None
                    else "—",
                }
                for group in details["group_results"]
            ]
        )
        _table(
            [
                {
                    "Evaluator": plots.label(item["evaluator_key"]),
                    "Group": plots.label(item["group_key"]),
                    "Status": plots.label(item["status"]),
                    "Raw score": plots.number(item["raw_score"]),
                    "Threshold": plots.number(item["threshold"]),
                    "Gate": {True: "Passed", False: "Failed", None: "—"}[item["passed_threshold"]],
                    "Weight": plots.number(item["configured_weight"]),
                    "Contribution": plots.number(item["contribution"])
                    if item["raw_score"] is not None
                    else "—",
                }
                for item in details["evaluator_results"]
            ]
            + [
                {
                    "Evaluator": plots.label(rule["key"]),
                    "Group": plots.label(rule["group_key"]),
                    "Status": "disabled",
                    "Raw score": "—",
                    "Threshold": plots.number(rule["minimum_score"]),
                    "Gate": "—",
                    "Weight": plots.number(rule["weight"]),
                    "Contribution": "—",
                }
                for rule in snapshot["configuration"]["evaluators"]
                if rule["key"] not in officially_listed
            ]
        )
        ui.label("Independent diagnostics").classes("text-lg font-semibold mt-2")
        if diagnostic:
            _table(
                [
                    {
                        "Evaluator": plots.label(key),
                        "Status": plots.label(item["status"]),
                        "Diagnostic score": plots.number(
                            (item["evaluation"] or {}).get("raw_score")
                        ),
                        "Details": item["error"] or "—",
                    }
                    for key, item in diagnostic.items()
                ]
            )
        else:
            ui.label("No independent diagnostic results.").classes("lab-muted")
    with workspace.context("Overview"):
        ui.label(f"{result['total_score']:.2f} / 100").classes("text-3xl font-semibold")
        status = ui.label(
            "Critical gate passed" if result["passed_critical"] else "Critical gate failed"
        )
        status.style(f"color: {plots.PASS if result['passed_critical'] else plots.FAIL}")
        if result["critical_failure"]:
            ui.label(result["critical_failure"]["message"]).classes("text-sm")
        json_panel("Run snapshot", snapshot)


def _inspection(workspace, title, key, official, diagnostic, document):
    plan = document["floor_plan"]
    evaluation = (diagnostic or {}).get("evaluation") or official or {"findings": []}
    payload = evaluation.get("visualization_payload") or {}
    items = plots.observations(key, evaluation, plan)
    overlays = sorted({layer.overlay for item in items for layer in item.layers})
    enabled = set(overlays) - {"Room boundaries", "Branch links"}

    with workspace.main(title):
        if key != "room_size_consistency" or not payload.get("rules"):
            workspace.main(title).classes("lab-replay-pane")
        chart = ui.plotly(
            plots.inspection_plot(
                plan, title, document["project_units_per_meter"], items, evaluation, None, enabled
            )
        ).classes("lab-primary-plot")
        if key == "room_size_consistency" and payload.get("rules"):
            chart.classes(remove="lab-primary-plot", add="w-full h-[360px]")
            _table(plots.size_matrix(payload))

    with workspace.context(title):
        _measurements(
            {
                "Official status": plots.label(official["status"]) if official else "Disabled",
                "Official score": plots.number(official["raw_score"]) if official else "—",
                **(
                    {
                        "Critical threshold": plots.number(official["threshold"]),
                        "Gate result": {True: "Passed", False: "Failed", None: "—"}[
                            official["passed_threshold"]
                        ],
                    }
                    if official and official["threshold"] is not None
                    else {}
                ),
                **(
                    {
                        "Diagnostic status": plots.label(diagnostic["status"]),
                        "Diagnostic score": plots.number(
                            (diagnostic["evaluation"] or {}).get("raw_score")
                        ),
                    }
                    if diagnostic
                    else {}
                ),
            }
        )
        if diagnostic and diagnostic["error"]:
            ui.label(diagnostic["error"]).classes("text-sm").style(f"color: {plots.WARN}")
        if key == "kitchen_dining_proximity" and payload:
            ui.label("Score rule").classes("font-semibold")
            ui.label(
                "Any pair meeting the shared-wall minimum earns 100. Otherwise the score decreases linearly from 100 to 0 over the maximum centroid distance."
            ).classes("text-sm")
            _measurements(
                {
                    "Applied rule": plots.label(payload["applied_rule"]),
                    "Shared-wall minimum": plots.length(
                        payload["settings"]["minimum_shared_boundary"]
                    ),
                    "Shared-wall tolerance": plots.length(payload["settings"]["tolerance"]),
                    "Maximum distance": plots.length(payload["settings"]["maximum_distance"]),
                    "Longest shared wall": plots.length(payload["maximum_shared_boundary"]),
                    "Shortest distance": plots.length(payload["minimum_centroid_distance"]),
                }
            )
        if key == "inward_recess" and payload:
            _measurements(
                {
                    "Maximum depth / width": plots.number(
                        payload["settings"]["max_depth_to_width_ratio"]
                    ),
                    "Maximum levels and branches": payload["settings"]["max_recess_levels"],
                }
            )
        if key == "enclosed_voids" and payload:
            _measurements(
                {
                    "Total detected area": plots.area(
                        sum(item["area"] for item in payload["voids"])
                    ),
                    "Area tolerance": plots.area(payload["area_tolerance"]),
                }
            )
        if key == "geometry_integrity" and payload:
            _measurements({"Geometry tolerance": plots.number(payload["tolerance"])})
        if items:
            ui.label("Findings and measurements").classes("font-semibold text-sm")
            picker = ui.radio(
                {-1: "No highlight", **{index: item.label for index, item in enumerate(items)}},
                value=-1,
            ).props("dense").classes("w-full max-h-64 overflow-auto")
            if overlays:
                with (
                    ui.expansion("Plot overlays", value=len(overlays) <= 3)
                    .props("dense")
                    .classes("w-full")
                ):
                    for overlay in overlays:
                        ui.checkbox(overlay, value=overlay in enabled).on_value_change(
                            lambda event, name=overlay: toggle(name, event.value)
                        )
            details = ui.column().classes("w-full")
            picker.on_value_change(lambda _: draw())
        elif evaluation.get("raw_score") is not None:
            ui.label("No individual findings or measurements recorded.").classes(
                "text-sm lab-muted"
            )
        if evaluation.get("findings") and key != "geometry_integrity":
            with ui.expansion("Evaluator findings").props("dense").classes("w-full"):
                for finding in evaluation["findings"]:
                    ui.label(finding["message"]).classes("text-sm")
        if evaluation.get("metrics"):
            with ui.expansion("Evaluator metrics").props("dense").classes("w-full"):
                _measurements(
                    {
                        plots.label(
                            metric["name"]
                        ): f"{plots.number(metric['value'])} {metric['unit'] or ''}"
                        for metric in evaluation["metrics"]
                    }
                )

    def draw():
        selected = None if picker.value == -1 else picker.value
        chart.figure = plots.inspection_plot(
            plan, title, document["project_units_per_meter"], items, evaluation, selected, enabled
        )
        chart.update()
        details.clear()
        if selected is not None:
            item = items[selected]
            with details:
                ui.label(item.label).classes("font-semibold").style(f"color: {item.color}")
                _measurements(item.measurements)

    def toggle(name, checked):
        enabled.add(name) if checked else enabled.discard(name)
        draw()


async def run_page(runtime, run_id):
    workspace = ResultWorkspace(f"E-02-B run #{run_id}", back_link=PATH, views=tuple(VIEWS))
    with workspace.controls:
        status = ui.label("Loading run…").classes("font-semibold")
        provenance = ui.label().classes("text-sm lab-muted")
        error = ui.label().classes("text-sm whitespace-pre-wrap").style(f"color: {plots.FAIL}")

    async def refresh():
        try:

            def read(session):
                row = session.get(E02BRun, run_id)
                return row_document(row) if row else None

            record = await db_call(runtime, read)
            if record is None:
                status.set_text("Run not found")
                timer.deactivate()
                return
            snapshot = record["snapshot"]
            status.set_text(plots.label(record["status"]).capitalize())
            provenance.set_text(
                f"{snapshot['layout_name']} · Core {snapshot['core_version']} · {snapshot['configuration_hash'][:12]}"
            )
            if record["status"] in {"queued", "running"}:
                timer.activate()
                return
            timer.deactivate()
            if record["duration_seconds"] is not None:
                status.set_text(f"{status.text} · {record['duration_seconds']:.3f} s")
            if record["error"]:
                error.set_text(
                    f"{plots.label(record['error']['stage'])} · {record['error']['message']}"
                )
            official = record["official"]
            if not official:
                with workspace.context("Overview"):
                    json_panel("Run snapshot", snapshot)
                return
            diagnostic = {item["evaluator_key"]: item for item in record["diagnostics"] or []}
            _overview(workspace, official, diagnostic, snapshot)
            evaluators = {
                item["evaluator_key"]: item for item in official["details"]["evaluator_results"]
            }
            for title, key in VIEWS.items():
                if key:
                    _inspection(
                        workspace,
                        title,
                        key,
                        evaluators.get(key),
                        diagnostic.get(key),
                        snapshot["input"],
                    )
        except Exception as exc:
            timer.deactivate()
            error.set_text(str(exc))
            raise

    timer = ui.timer(0.75, refresh, active=False, immediate=False)
    await refresh()
