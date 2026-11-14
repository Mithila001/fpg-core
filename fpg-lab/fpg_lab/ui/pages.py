from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from nicegui import run, ui

from fpg_lab.core.settings import ROOT
from fpg_lab.inputs import FloorPlanTemplateCreate, SystemConfigurationCreate
from fpg_lab.runtime import LabRuntime, row_document
from fpg_lab.services.common import FloorPlanTemplateService, SystemConfigurationService
from fpg_lab.ui.components import (
    action_button,
    db_call,
    editor_value,
    format_experiment_code,
    notify_error,
    set_editor,
    shell,
)
from fpg_lab.ui.experiments import register_experiments

EXPERIMENTS = {
    "e01a": ("Floor Traffic", "Preset floor plans → walking paths → traffic heatmap"),
    "p01a": ("Candidate search", "Preprocess → search → circulation → candidate score"),
    "p01b": (
        "Manual hint floor plan",
        "Manual hints → solve → refine → post-process → score",
    ),
    "p01c": ("Floor plan with openings", "Repeated floor-plan generation → openings → scoring"),
}


def register_pages(runtime: LabRuntime) -> None:
    @ui.page("/")
    async def home() -> None:
        shell(
            "Experiment workspace",
            "Run and inspect floor-plan prototypes and experiments directly in Python.",
        )
        # Family grouping is display-only; experiment keys and route paths stay unchanged.
        categories = {flow[0].lower() for flow in EXPERIMENTS}
        order = [code for code in ("e", "p") if code in categories]
        order.extend(sorted(categories - {"e", "p"}))
        for index, prefix in enumerate(order):
            group = [
                (flow, entry) for flow, entry in EXPERIMENTS.items() if flow.startswith(prefix)
            ]
            if index:
                ui.separator().classes("w-full my-4")
            with (
                ui.element("div")
                .classes("w-full grid gap-3 items-stretch")
                .style("grid-template-columns: repeat(auto-fill, minmax(285px, 1fr))")
            ):
                for flow, (title, description) in group:
                    with ui.card().classes("w-full h-full p-4 gap-2"):
                        ui.label(format_experiment_code(flow)).classes(
                            "text-base font-bold font-mono tracking-wide lab-accent"
                        )
                        ui.label(title).classes("text-lg font-semibold")
                        ui.label(description).classes("lab-muted text-sm flex-1")
                        action_button(
                            "Open setup",
                            on_click=lambda f=flow: ui.navigate.to(f"/experiments/{f}"),
                        ).props("dense outline")
        ui.label(
            f"FPG Core {runtime.codec.fpg_core_version} · P-01 runs are saved; E-01-A runs are temporary"
        ).classes("text-xs lab-muted mt-3")

    @ui.page("/configurations")
    async def configurations() -> None:
        await records_page(runtime, "configuration")

    @ui.page("/templates")
    async def templates() -> None:
        await records_page(runtime, "template")

    register_experiments(runtime)


async def records_page(runtime: LabRuntime, kind: str) -> None:
    is_config = kind == "configuration"
    shell(
        "System configurations" if is_config else "Floor-plan templates",
        "Edit a JSON draft, validate it, then save. Existing experiment snapshots stay unchanged.",
    )
    state: dict[str, Any] = {"id": None, "baseline": {}, "records": {}}

    def service(session: Any) -> Any:
        return (
            SystemConfigurationService(session, runtime.codec)
            if is_config
            else FloorPlanTemplateService(session)
        )

    async def refresh() -> None:
        records = await db_call(
            runtime,
            lambda session: [
                row_document(r) for r in service(session).list(limit=500, offset=0)[0]
            ],
        )
        state["records"] = {r["id"]: r for r in records}
        picker.options = {
            r["id"]: r["name"] + (" · active" if r.get("is_active") else "") for r in records
        }
        picker.update()

    def load_record() -> None:
        record = state["records"].get(picker.value)
        if record is None:
            return
        state["id"] = record["id"]
        name.value, description.value = record["name"], record.get("description") or ""
        state["baseline"] = deepcopy(record["configuration_data" if is_config else "template_data"])
        set_editor(editor, state["baseline"])
        feedback.set_text(
            f"Loaded {record['name']}"
            + (
                f" · core {record['fpg_core_version']} · hash {record['config_hash'][:12]}"
                if is_config
                else ""
            )
        )

    async def new_record() -> None:
        try:
            if is_config:
                configuration = await run.io_bound(runtime.codec.default_configuration)
                if configuration is None:
                    raise ValueError("Default configuration could not be loaded")
                value = configuration.payload
            else:
                value = json.loads(
                    (ROOT / "seed/floor_plan_template.example.json").read_text(encoding="utf-8")
                )["template_data"]
            state["id"], state["baseline"] = None, deepcopy(value)
            picker.value = None
            name.value, description.value = (
                "research-profile" if is_config else "research-template",
                "",
            )
            set_editor(editor, value)
            feedback.set_text("New unsaved draft")
        except Exception as exc:
            notify_error(exc)

    async def payload() -> Any:
        data = await editor_value(editor)
        model = SystemConfigurationCreate if is_config else FloorPlanTemplateCreate
        values = {
            "name": name.value,
            "description": (description.value or "").strip() or None,
            "configuration_data" if is_config else "template_data": data,
            "schema_version": str(data.get("schema_version", 6)) if is_config else "1",
        }
        return model.model_validate(values)

    async def validate() -> None:
        try:
            draft = await payload()
            if is_config:
                await run.io_bound(
                    runtime.codec.validate_payload, draft.configuration_data.model_dump(mode="json")
                )
            else:
                # Core preprocessing validation happens against a selected experiment profile.
                draft.template_data.model_dump(mode="json")
            feedback.set_text(
                "Draft is valid"
                if is_config
                else "Request structure is valid; experiment preprocessing checks the selected profile."
            )
            ui.notify("Validation passed", type="positive")
        except Exception as exc:
            feedback.set_text(str(exc))
            notify_error(exc)

    async def save() -> None:
        try:
            draft = await payload()
            record_id = state["id"]
            saved = await db_call(
                runtime,
                lambda session: row_document(
                    service(session).create(draft)
                    if record_id is None
                    else service(session).update(record_id, draft)
                ),
            )
            state["id"] = saved["id"]
            await refresh()
            picker.value = saved["id"]
            load_record()
            ui.notify("Saved", type="positive")
        except Exception as exc:
            feedback.set_text(str(exc))
            notify_error(exc)

    def duplicate() -> None:
        state["id"] = None
        picker.value = None
        name.value = ((name.value or "")[:120] or "research") + "-copy"
        feedback.set_text("Unsaved copy; choose a unique name and save")

    async def activate() -> None:
        try:
            if state["id"] is None:
                raise ValueError("Save the profile before activating it")
            await db_call(runtime, lambda session: service(session).activate(state["id"]))
            await refresh()
            feedback.set_text("Saved profile activated. Unsaved draft changes were not applied.")
        except Exception as exc:
            notify_error(exc)

    async def delete() -> None:
        if state["id"] is None:
            return
        with ui.dialog() as dialog, ui.card():
            ui.label("Delete this saved record?")
            with ui.row():
                action_button("Cancel", role="subtle", on_click=lambda: dialog.submit(False))
                action_button("Delete", role="danger", on_click=lambda: dialog.submit(True))
        if not await dialog:
            return
        try:
            await db_call(runtime, lambda session: service(session).delete(state["id"]))
            await refresh()
            await new_record()
        except Exception as exc:
            notify_error(exc)

    with ui.card().classes("w-full p-5 gap-4"):
        with ui.row().classes("w-full items-center gap-3"):
            picker = ui.select(
                {},
                label="Saved profiles" if is_config else "Saved templates",
                on_change=load_record,
            ).classes("min-w-80")
            action_button("New from default", on_click=new_record)
            action_button("Duplicate draft", role="subtle", on_click=duplicate)
            action_button("Refresh list", role="subtle", on_click=refresh).props("flat")
        with ui.row().classes("w-full"):
            name = ui.input("Name").classes("flex-1")
            description = ui.input("Description").classes("flex-[2]")
        # NiceGUI's browser validator rejects Pydantic's discriminated-union schemas.
        # Validate configuration drafts with the Python codec instead.
        editor = ui.json_editor({"content": {"json": {}}}).classes(
            "nicegui-json-editor w-full min-h-96"
        )
        feedback = ui.label().classes("text-sm lab-text whitespace-pre-wrap")
        with ui.row():
            action_button("Validate", on_click=validate).props("outline")
            action_button("Save", role="main", on_click=save)
            action_button(
                "Reset draft", role="danger", on_click=lambda: set_editor(editor, state["baseline"])
            ).props("flat")
            if is_config:
                action_button("Activate saved profile", role="main", on_click=activate).props(
                    "outline"
                )
            action_button("Delete saved record", role="danger", on_click=delete).props("flat")
    await refresh()
    if state["records"]:
        picker.value = next(iter(state["records"]))
        load_record()
    else:
        await new_record()
