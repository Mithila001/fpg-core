from __future__ import annotations

import json
import tempfile
import zipfile
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.responses import FileResponse
from nicegui import app, run, ui
from sqlalchemy import select
from starlette.background import BackgroundTask

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.core.settings import ROOT
from fpg_lab.database.models import P01CandidateTrial
from fpg_lab.database.serialization import row_document
from fpg_lab.flows.p01 import ACTIVE_STATUSES
from fpg_lab.inputs import FloorPlanRequest, SystemConfigurationUpdate
from fpg_lab.runtime import FLOW_SERVICES, LabRuntime
from fpg_lab.services.common import FloorPlanTemplateService, SystemConfigurationService
from fpg_lab.ui.components import (
    action_button,
    db_call,
    format_experiment_code,
    json_panel,
    notify_error,
    set_editor,
    shell,
)
from fpg_lab.ui.replay import candidate_replay
from fpg_lab.ui.result_layout import ResultWorkspace
from fpg_lab.visualization import figures


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
            "body-cell-trial_no",
            '<q-td :props="props"><q-btn flat dense color="primary" '
            ':label="props.row.trial_no" @click="$parent.$emit(\'seek-trial\', props.row.trial_no)" /></q-td>',
        )
        widget.on("seek-trial", lambda event: on_trial(int(event.args)))
    widget.add_slot(
        "body-cell-id",
        '<q-td :props="props"><a class="text-primary underline" :href="\''
        + link_prefix
        + "' + props.row.id\">{{ props.row.id }}</a></q-td>",
    )


def register_experiments(runtime: LabRuntime) -> None:
    @ui.page("/experiments/{flow}")
    async def experiment_page(flow: str) -> None:
        if flow == "e03a":
            from fpg_lab.ui.e03a import setup_page

            await setup_page(runtime)
            return
        if flow == "e02a":
            from fpg_lab.ui.e02a import main_page as e02a_page

            await e02a_page(runtime)
            return
        if flow == "e02c":
            from fpg_lab.ui.e02c import main_page

            await main_page(runtime)
            return
        if flow == "e02b":
            from fpg_lab.ui.e02b import main_page as e02b_page

            await e02b_page(runtime)
            return
        if flow == "e01a":
            from fpg_lab.ui.e01a import main_page as e01a_page

            await e01a_page()
            return
        if flow in ("p01b", "p01c"):
            from fpg_lab.ui.p01b import main_page as p01b_page

            await p01b_page(runtime, flow)
            return
        if flow not in FLOW_SERVICES:
            shell("Unknown experiment")
            return
        shell(
            f"{format_experiment_code(flow)} · Setup",
            "Choose a configuration and request, then start a run.",
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
        default_template = next(
            (t for t in templates if t["name"] == "Full Template (Default)"), None
        )

        def apply_template() -> None:
            selected = next((t for t in templates if t["id"] == template.value), None)
            if selected:
                request_content["content"] = {"json": deepcopy(selected["template_data"])}
                set_editor(request_editor, selected["template_data"])

        request_content: dict[str, Any] = {}

        def remember_request(event: Any) -> None:
            request_content["content"] = event.content
            request_editor.properties["content"] = event.content

        with ui.card().classes("w-full p-5 gap-4"):
            with ui.row().classes("w-full items-center"):
                profile = ui.select(
                    {
                        c["id"]: c["name"] + (" · active" if c["is_active"] else "")
                        for c in configurations
                    },
                    value=next((c["id"] for c in configurations if c["is_active"]), None),
                    label="System configuration",
                ).classes("min-w-80")
                template = ui.select(
                    {t["id"]: t["name"] for t in templates},
                    value=default_template["id"] if default_template else None,
                    label="Load a template",
                    on_change=apply_template,
                ).classes("min-w-80")
                trial_count = ui.number(
                    "Trials", value=100, min=1, max=100000, precision=0
                ).classes("w-32")
                debug = ui.checkbox("Store debug data", value=True)
            if not configurations:
                ui.label(
                    "Create and activate a configuration before running an experiment."
                ).classes("text-amber-300")
                ui.link("Open configurations", "/configurations")
            with (
                ui.dialog() as request_dialog,
                ui.card().classes("w-[90vw] max-w-5xl max-h-[85vh] overflow-auto"),
            ):
                ui.label("Floor-plan request").classes("text-xl font-semibold")
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
                    on_change=remember_request,
                ).classes("nicegui-json-editor w-full min-h-72")
                request_content["content"] = request_editor.properties["content"]
                action_button("Close", role="subtle", on_click=request_dialog.close)
            action_button("Edit floor-plan request", role="general", on_click=request_dialog.open)

            state: dict[str, Any] = {"profile": None, "loading": False}
            with ui.card().classes("w-full p-4"):
                ui.label("System configuration quick settings").classes("font-semibold")
                with ui.row().classes("items-center"):
                    seed = ui.number("Random seed", min=0, precision=0)
                    spacing = ui.number("Grid spacing", min=2, precision=0)
                    save_settings = action_button("Save", role="general")
                    settings_status = ui.label().classes("text-amber-300")

            def dirty() -> bool:
                record = state["profile"]
                if record is None:
                    return False
                config = record["configuration_data"]
                return (
                    seed.value != config["candidate_search"]["random_seed"]
                    or spacing.value != config["preprocessing"]["candidate_search_grid_spacing"]
                )

            def mark_settings() -> None:
                if not state["loading"]:
                    settings_status.set_text("Unsaved changes" if dirty() else "")

            async def load_profile() -> None:
                try:
                    state["loading"] = True
                    profile_id = profile.value
                    record = (
                        await db_call(
                            runtime,
                            lambda session: row_document(
                                SystemConfigurationService(session, runtime.codec).resolve(
                                    profile_id
                                )
                            ),
                        )
                        if profile_id is not None
                        else None
                    )
                    if profile.value != profile_id:
                        return
                    state["profile"] = record
                    seed.set_value(
                        record["configuration_data"]["candidate_search"]["random_seed"]
                        if record
                        else None
                    )
                    spacing.set_value(
                        record["configuration_data"]["preprocessing"][
                            "candidate_search_grid_spacing"
                        ]
                        if record
                        else None
                    )
                    settings_status.set_text("")
                except Exception as exc:
                    state["profile"] = None
                    notify_error(exc)
                finally:
                    state["loading"] = False

            async def save_profile() -> None:
                try:
                    record = state["profile"]
                    if record is None or record["id"] != profile.value:
                        raise ValueError("Select a system configuration")
                    if seed.value is not None and (seed.value < 0 or int(seed.value) != seed.value):
                        raise ValueError("Random seed must be a non-negative integer or empty")
                    if (
                        spacing.value is None
                        or spacing.value <= 0
                        or int(spacing.value) != spacing.value
                        or int(spacing.value) % 2
                    ):
                        raise ValueError("Grid spacing must be a positive even integer")
                    config = deepcopy(record["configuration_data"])
                    config["candidate_search"]["random_seed"] = (
                        int(seed.value) if seed.value is not None else None
                    )
                    config["preprocessing"]["candidate_search_grid_spacing"] = int(spacing.value)
                    payload = SystemConfigurationUpdate(
                        name=record["name"],
                        description=record["description"],
                        configuration_data=config,
                    )
                    state["profile"] = await db_call(
                        runtime,
                        lambda session: row_document(
                            SystemConfigurationService(session, runtime.codec).save(
                                record["id"], payload, expected_hash=record["config_hash"]
                            )
                        ),
                    )
                    mark_settings()
                    ui.notify("Configuration saved", type="positive")
                except Exception as exc:
                    notify_error(exc)

            seed.on_value_change(mark_settings)
            spacing.on_value_change(mark_settings)
            profile.on_value_change(load_profile)
            save_settings.on_click(save_profile)
            await load_profile()

            async def remember_trials() -> None:
                value = trial_count.value
                if value is not None and 1 <= value <= 100000 and int(value) == value:
                    await ui.run_javascript(
                        f"sessionStorage.setItem('fpg_p01a_trial_count', {json.dumps(str(int(value)))})"
                    )

            try:
                stored = await ui.run_javascript("sessionStorage.getItem('fpg_p01a_trial_count')")
                if stored is not None and str(stored).isdigit() and 1 <= int(stored) <= 100000:
                    trial_count.set_value(int(stored))
            except Exception:
                pass
            trial_count.on_value_change(remember_trials)

            async def start() -> None:
                start_button.disable()
                try:
                    if profile.value is None:
                        raise ValueError("Select a system configuration")
                    if (
                        state["loading"]
                        or state["profile"] is None
                        or state["profile"]["id"] != profile.value
                        or dirty()
                    ):
                        raise ValueError(
                            "Save or reload the system configuration quick settings before starting"
                        )
                    if (
                        trial_count.value is None
                        or not 1 <= trial_count.value <= 100000
                        or int(trial_count.value) != trial_count.value
                    ):
                        raise ValueError("Trials must be an integer between 1 and 100,000")
                    content = request_content["content"]
                    request = (
                        content["json"]
                        if "json" in content
                        else json.loads(content.get("text", ""))
                    )
                    if not isinstance(request, dict):
                        raise ValueError("Enter a JSON object")
                    payload = {
                        "floor_plan_request": request,
                        "system_configuration_id": profile.value,
                        "should_save": debug.value,
                    }
                    payload["trial_count"] = trial_count.value
                    experiment_id = await run.io_bound(runtime.start_experiment, flow, payload)
                    ui.navigate.to(f"/experiments/{flow}/runs/{experiment_id}")
                except Exception as exc:
                    notify_error(exc)
                finally:
                    start_button.enable()

            with ui.row():
                start_button = action_button(
                    f"Start {format_experiment_code(flow)}", role="main", on_click=start
                )

        selected: set[int] = set()
        exporting = False
        with ui.row().classes("w-full items-center justify-between"):
            history_title = ui.label("Saved experiments").classes("text-xl font-semibold")
            with ui.row().classes("items-center"):
                compact = ui.checkbox("Compact", value=True)
                export_button = action_button("Export (0)", role="general")
        fields = (
            "id",
            "status",
            "completed_trial_count",
            "requested_trial_count",
            "best_candidate_score",
            "created_at",
        )
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
        columns.append(
            {"name": "selected", "label": "Select", "field": "selected", "align": "right"}
        )
        widget = ui.table(columns=columns, rows=[], row_key="id", pagination=25).classes("w-full")
        widget.add_slot(
            "body-cell-id",
            '<q-td :props="props"><a class="text-primary underline" :href="\'/experiments/'
            + flow
            + "/runs/' + props.row.id\">{{ props.row.id }}</a></q-td>",
        )
        widget.add_slot(
            "body-cell-selected",
            '<q-td :props="props"><q-checkbox :model-value="props.row.selected" @update:model-value="$parent.$emit(\'select-record\', {id: props.row.id, selected: $event})" /></q-td>',
        )
        page = ui.number("History page", value=1, min=1, precision=0).classes("w-36")
        timer: ui.timer

        def update_export() -> None:
            if export_button is not None:
                export_button.set_text(f"Export ({len(selected)})")
                export_button.set_enabled(bool(selected) and not exporting)

        async def export() -> None:
            nonlocal exporting
            if not selected or exporting:
                return
            exporting = True
            update_export()
            path = None
            ids, is_compact = sorted(selected), bool(compact.value)
            mode = "compact" if is_compact else "full"
            stem = f"p01a-{mode}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            try:
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
                    path = Path(temporary.name)

                def write(session: Any) -> None:
                    with tempfile.TemporaryDirectory() as directory:
                        json_path = Path(directory) / f"{stem}.json"
                        with json_path.open("w", encoding="utf-8", newline="") as output:
                            FLOW_SERVICES[flow](session).export_history(ids, is_compact, output)
                        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                            archive.write(json_path, arcname=json_path.name)

                await db_call(runtime, write)
                filename = f"{stem}.zip"
                url = f"/p01a-export/{uuid4().hex}"
                claimed = False

                @app.get(url, include_in_schema=False)
                def download() -> FileResponse:
                    nonlocal claimed
                    claimed = True
                    app.remove_route(url)
                    return FileResponse(
                        path,
                        filename=filename,
                        media_type="application/zip",
                        background=BackgroundTask(path.unlink, missing_ok=True),
                    )

                def cleanup() -> None:
                    if not claimed:
                        app.remove_route(url)
                        path.unlink(missing_ok=True)

                ui.context.client.on_delete(cleanup)
                ui.download.from_url(url, filename)
                ui.notify("Download prepared. Incomplete histories are identified in the export.")
            except Exception as exc:
                if path is not None:
                    path.unlink(missing_ok=True)
                notify_error(exc)
            finally:
                exporting = False
                update_export()

        export_button.on_click(export)

        def select_record(event: Any) -> None:
            record_id = int(event.args["id"])
            if event.args["selected"]:
                selected.add(record_id)
            else:
                selected.discard(record_id)
            for row in widget.rows:
                if row["id"] == record_id:
                    row["selected"] = record_id in selected
            widget.update()
            update_export()

        widget.on("select-record", select_record)
        update_export()

        async def refresh_history() -> None:
            try:
                items, total = await db_call(
                    runtime, lambda session: _history(session, flow, int(page.value or 1))
                )
                history_title.set_text(f"Saved experiments · {total} total")
                widget.rows = [
                    {**{key: item.get(key) for key in fields}, "selected": item["id"] in selected}
                    for item in items
                ]
                widget.update()
                if not any(item["status"] in ACTIVE_STATUSES for item in items):
                    timer.deactivate()
            except Exception as exc:
                timer.deactivate()
                notify_error(exc)

        page.on_value_change(refresh_history)
        action_button("Refresh history", role="subtle", on_click=lambda: timer.activate())
        timer = ui.timer(1.0, refresh_history, immediate=False)
        await refresh_history()

    @ui.page("/experiments/e01a/runs/{run_id}")
    async def e01a_run_page(run_id: str) -> None:
        from fpg_lab.ui.e01a import result_page

        await result_page(run_id)

    @ui.page("/experiments/{flow}/runs/{experiment_id}")
    async def run_page(flow: str, experiment_id: int) -> None:
        timer: ui.timer
        if flow == "e02c":
            from fpg_lab.ui.e02c import run_page as e02c_run_page

            await e02c_run_page(runtime, experiment_id)
            return
        if flow == "e02b":
            from fpg_lab.ui.e02b import run_page as e02b_run_page

            await e02b_run_page(runtime, experiment_id)
            return
        if flow == "e02a":
            from fpg_lab.ui.e02a import run_page as e02a_run_page

            await e02a_run_page(runtime, experiment_id)
            return
        if flow in ("p01b", "p01c"):
            from fpg_lab.ui.p01b import run_page as p01b_run_page

            await p01b_run_page(runtime, experiment_id, flow)
            return
        if flow not in FLOW_SERVICES:
            shell("Unknown experiment")
            return
        workspace = ResultWorkspace(
            f"{format_experiment_code(flow)} run #{experiment_id}",
            back_link=f"/experiments/{flow}",
            views=("Canvas", "Charts", "Trials", "Diagnostics"),
        )
        workspace.main("Canvas").classes("lab-replay-pane")
        with workspace.main("Canvas"):
            replay_area = ui.column().classes("lab-replay-canvas")
            with replay_area:
                ui.label("Waiting for saved replay geometry…").classes("lab-muted text-sm")
        with workspace.main("Charts"):
            charts_area = ui.column().classes("w-full min-w-0")
        with workspace.main("Trials"):
            trial_area = ui.column().classes("w-full gap-3")
        with workspace.main("Diagnostics"):
            provenance_area = ui.column().classes("w-full gap-3")
        with workspace.controls:
            status = ui.label("Loading run…").classes("font-semibold text-sm")
            counters = ui.label().classes("text-sm")
            progress = ui.linear_progress(value=0).classes("w-full")
            with ui.row().classes("w-full gap-2 items-center"):
                action_button("Refresh", role="subtle", on_click=lambda: timer.activate()).props(
                    "dense flat"
                )
                terminate_button = action_button("Terminate", role="danger").props("dense outline")
            trial_page = (
                ui.number("Trial history page", value=1, min=1, precision=0)
                .classes("w-full")
                .props("dense")
            )
            replay_controls = ui.column().classes("w-full gap-2")
        with workspace.context("Canvas"):
            replay_context = ui.column().classes("w-full gap-2")
        with workspace.context("Charts"):
            ui.label("Score histories and evaluator progression for this run.").classes(
                "text-sm lab-muted"
            )
        with workspace.context("Trials"):
            ui.label(
                "Choose a trial to seek its replay frame, or open the saved trial record."
            ).classes("text-sm lab-muted")
        with workspace.context("Diagnostics"):
            ui.label("Saved request, preprocessing, configuration and errors.").classes(
                "text-sm lab-muted"
            )
        replay_loaded = False
        replay_seek: Callable[[int], None] | None = None
        last_snapshot: tuple[Any, ...] | None = None

        def seek_saved_trial(trial_no: int) -> None:
            if replay_seek is not None:
                replay_seek(trial_no)
                workspace.select_view("Canvas")

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
            nonlocal replay_loaded, replay_seek, last_snapshot
            try:
                item, trials, scores = await db_call(
                    runtime,
                    lambda session: _run_data(
                        session, flow, experiment_id, int(trial_page.value or 1)
                    ),
                )
                snapshot = (item, trials, scores)
                if snapshot == last_snapshot:
                    if item["status"] not in ACTIVE_STATUSES:
                        timer.deactivate()
                    return
                last_snapshot = snapshot
                status.set_text(item["status"].replace("_", " ").title())
                counters.set_text(
                    f"Trials {item['completed_trial_count']}/{item['requested_trial_count'] or '—'}"
                    f" · best candidate {item['best_candidate_score']}"
                    f" · floor {item['best_floor_plan_score']}"
                )
                progress.set_visibility(bool(item["requested_trial_count"]))
                if item["requested_trial_count"]:
                    progress.value = min(
                        1, item["completed_trial_count"] / item["requested_trial_count"]
                    )
                terminate_button.set_enabled(item["status"] in ACTIVE_STATUSES)
                if item["status"] not in ACTIVE_STATUSES and not replay_loaded:
                    replay_area.clear()
                    charts_area.clear()
                    replay_seek = await candidate_replay(
                        runtime,
                        item,
                        canvas_area=replay_area,
                        controls_area=replay_controls,
                        context_area=replay_context,
                        charts_area=charts_area,
                        on_seek=lambda: workspace.select_view("Canvas"),
                    )
                    replay_loaded = True
                    if replay_seek is None:
                        with charts_area:
                            if scores:
                                ui.plotly(figures.score_history(scores)).classes("w-full h-72")
                                ui.plotly(figures.score_distribution(scores)).classes("w-full h-72")
                            else:
                                ui.label("No saved scores are available.").classes("lab-muted")
                        workspace.select_view("Charts" if scores else "Trials")
                    elif scores:
                        with charts_area:
                            ui.plotly(figures.score_distribution(scores)).classes("w-full h-72")
                if not replay_loaded:
                    charts_area.clear()
                    with charts_area:
                        if scores:
                            ui.plotly(figures.score_history(scores)).classes("w-full h-72")
                            ui.plotly(figures.score_distribution(scores)).classes("w-full h-72")
                        else:
                            ui.label("Scores will appear as trials complete.").classes(
                                "lab-muted text-sm"
                            )
                trial_area.clear()
                with trial_area:
                    if not item["persist_trial_data"]:
                        ui.label(
                            "Debug data was disabled; only rejected and failed trials are saved."
                        ).classes("text-amber-300")
                    table(
                        trials,
                        ("id", "trial_no", "status", "final_score", "duration_ms"),
                        f"/experiments/{flow}/runs/{experiment_id}/trials/",
                        on_trial=seek_saved_trial if replay_seek else None,
                    )
                provenance_area.clear()
                with provenance_area:
                    ui.label(
                        f"Stop reason: {item['stop_reason'] or '—'}"
                        f" · Core {item['fpg_core_version']}"
                    ).classes("text-sm lab-muted")
                    json_panel(
                        "Request and configuration provenance",
                        {
                            key: item[key]
                            for key in (
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
                notify_error(exc)

        trial_page.on_value_change(refresh_run)
        terminate_button.on_click(terminate)
        timer = ui.timer(1, refresh_run, immediate=False)
        await refresh_run()

    @ui.page("/experiments/{flow}/runs/{experiment_id}/trials/{trial_id}")
    async def trial_page(flow: str, experiment_id: int, trial_id: int) -> None:
        if flow != "p01a":
            shell("This experiment has no candidate trials")
            return
        try:

            def read(session: Any) -> Any:
                trial = FLOW_SERVICES[flow](session).get_trial(trial_id)
                if trial.experiment_id != experiment_id:
                    raise ValueError("Trial does not belong to this run")
                return row_document(trial)

            item = await db_call(runtime, read)
            exported = None
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
                except (ValueError, KeyError, TypeError):
                    pass
            candidate = item["candidate_search_data"]
            workspace = ResultWorkspace(
                f"Candidate trial #{trial_id}",
                back_link=f"/experiments/{flow}/runs/{experiment_id}",
                back_label="Back to run",
                views=("Canvas", "Scores", "Diagnostics"),
                default="Canvas"
                if candidate
                else ("Scores" if item["candidate_scoring_data"] else "Diagnostics"),
            )
            with workspace.main("Canvas"):
                if candidate:
                    ui.plotly(figures.candidate_map(candidate)).classes("lab-primary-plot")
                else:
                    ui.label("Candidate geometry was not stored.").classes("text-amber-300")
            with workspace.main("Scores"):
                if item["candidate_scoring_data"]:
                    ui.plotly(figures.score_breakdown(item["candidate_scoring_data"])).classes(
                        "w-full h-[32rem]"
                    )
                else:
                    ui.label("No candidate scoring data was stored.").classes("lab-muted")
            with workspace.main("Diagnostics"):
                json_panel("Candidate, circulation, scoring and errors", item)
            with workspace.controls:
                ui.label(f"Trial {item['trial_no']} · {item['status']}").classes(
                    "font-semibold text-sm"
                )
                ui.label(
                    f"Score: {item['final_score'] if item['final_score'] is not None else '—'}"
                ).classes("text-sm")
                if exported is not None:
                    action_button(
                        "Copy cleaned hint map",
                        role="subtle",
                        icon="content_copy",
                        on_click=lambda: ui.run_javascript(
                            f"navigator.clipboard.writeText({json.dumps(json.dumps(exported))})"
                        ),
                    ).props("dense flat")
            with workspace.context("Canvas"):
                ui.label("Saved candidate hints and their prepared grid.").classes(
                    "text-sm lab-muted"
                )
            with workspace.context("Scores"):
                ui.label("Raw evaluator scores and contributions.").classes("text-sm lab-muted")
            with workspace.context("Diagnostics"):
                ui.label("Full saved trial data and errors.").classes("text-sm lab-muted")
        except Exception as exc:
            shell(
                "Candidate trial unavailable", back_link=f"/experiments/{flow}/runs/{experiment_id}"
            )
            ui.label(str(exc)).classes("text-rose-300")


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
            select(
                P01CandidateTrial.trial_no,
                P01CandidateTrial.final_score,
                P01CandidateTrial.status,
                P01CandidateTrial.error_data,
            )
            .where(P01CandidateTrial.experiment_id == experiment_id)
            .order_by(P01CandidateTrial.trial_no)
        ).mappings()
    ]
    return row_document(item), to_jsonable(trials), to_jsonable(scores)
