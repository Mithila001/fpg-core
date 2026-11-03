from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from nicegui import run, ui
from sqlalchemy.orm import Session

from fpg_lab.runtime import LabRuntime


def shell(
    title: str, subtitle: str = "", *, compact: bool = False, back_link: str | None = None
) -> None:
    ui.colors(
        primary="#75beff",
        secondary="#b0b0b0",
        accent="#75beff",
        positive="#276749",
        negative="#b32632",
        warning="#cca700",
        info="#005fb8",
        dark="#252526",
        dark_page="#1e1e1e",
    )
    ui.add_css("""
        :root { color-scheme: dark; }
        .q-card, .q-table__container { border: 1px solid #3c3c3c; box-shadow: none; }
        .lab-workspace { background: #1e1e1e; color: #d4d4d4; }
        .lab-header { background: #181818; color: #d4d4d4; border-color: #3c3c3c; }
        .lab-panel { background: #252526; border-color: #3c3c3c; }
        .lab-text { color: #d4d4d4; }
        .lab-muted, .q-field--dark .q-field__label { color: #b0b0b0; }
        .lab-accent { color: #75beff; }
        .bg-primary { --q-primary: #005fb8; }
        .q-btn.text-negative { --q-negative: #f48771; }
        .q-btn.text-positive { --q-positive: #89d185; }
        .q-btn.bg-primary, .q-btn.bg-negative, .q-btn.bg-positive { color: #ffffff !important; }
        .q-field--outlined .q-field__control:before { border-color: #6b6b6b; }
        a:focus-visible, .q-btn:focus-visible { outline: 2px solid #75beff; outline-offset: 3px; }
        .nicegui-json-editor {
            --jse-background-color: #1e1e1e;
            --jse-text-color: #d4d4d4;
            --jse-panel-background: #252526;
            --jse-panel-border: 1px solid #3c3c3c;
            --jse-panel-color: #d4d4d4;
            --jse-panel-button-color: #d4d4d4;
            --jse-main-border: 1px solid #3c3c3c;
            --jse-menu-color: #ffffff;
            --jse-theme-color: #005fb8;
            --jse-theme-color-highlight: #0078d4;
            --jse-selection-background-color: #3c3c3c;
            --jse-selection-background-inactive-color: #252526;
            --jse-hover-background-color: #252526;
            --jse-context-menu-background: #252526;
            --jse-context-menu-color: #d4d4d4;
            --jse-modal-background: #252526;
            --jse-modal-code-background: #1e1e1e;
            --jse-overlay-background: #00000080;
            --jse-table-header-background: #252526;
            --jse-table-header-background-highlight: #3c3c3c;
            --jse-table-row-odd-background: #252526;
            --jse-navigation-bar-background: #252526;
            --jse-navigation-bar-dropdown-color: #d4d4d4;
            --jse-active-line-background-color: #2a2d2e;
            --jse-contents-background-color: #1e1e1e;
            --jse-a-color: #75beff;
            --jse-input-background: #1e1e1e;
            --jse-input-color: #d4d4d4;
            --jse-input-border: 1px solid #6b6b6b;
            --jse-value-color-string: #ce9178;
            --jse-key-color: #9cdcfe;
            --jse-value-color-number: #b5cea8;
            --jse-value-color-boolean: #569cd6;
            --jse-value-color-null: #b0b0b0;
            --jse-value-color-url: #75beff;
            --jse-delimiter-color: #b0b0b0;
        }
    """)
    with ui.header().classes("lab-header border-b shadow-none items-center gap-6"):
        ui.link("FPG Lab", "/").classes("text-xl font-bold no-underline lab-accent")
        for name, path in (
            ("Experiments", "/"),
            ("Configurations", "/configurations"),
            ("Templates", "/templates"),
        ):
            ui.link(name, path).classes("lab-text no-underline hover:underline")
        ui.label("Local research workspace").classes("ml-auto text-xs lab-muted")
    ui.query("body").classes("lab-workspace")
    with ui.row().classes("w-full items-center justify-between"):
        ui.label(title).classes(
            "text-2xl font-semibold" if compact else "text-3xl font-semibold mt-5"
        )
        if back_link:
            ui.link("Back to experiments", back_link).classes("text-sm")
    if subtitle:
        ui.label(subtitle).classes("lab-muted mb-4")


async def db_call(runtime: LabRuntime, operation: Callable[[Session], Any]) -> Any:
    def call() -> Any:
        with runtime.database.session_factory() as session:
            return operation(session)

    return await run.io_bound(call)


def json_panel(title: str, value: Any) -> None:
    with ui.expansion(title).classes("w-full lab-panel border rounded-lg"):
        ui.code(json.dumps(value, indent=2, ensure_ascii=False), language="json").classes(
            "w-full max-h-96 overflow-auto"
        )


def set_editor(editor: ui.json_editor, value: Any) -> None:
    editor.properties["content"] = {"json": deepcopy(value)}
    editor.update()


async def editor_value(editor: ui.json_editor) -> dict[str, Any]:
    content = await editor.run_editor_method("get", timeout=5)
    if not isinstance(content, dict):
        raise ValueError("The JSON editor is still loading; try again")
    value = content["json"] if "json" in content else json.loads(content.get("text", ""))
    if not isinstance(value, dict):
        raise ValueError("Enter a JSON object")
    return value


def notify_error(exc: Exception) -> None:
    ui.notify(str(exc), type="negative", timeout=10000, multi_line=True)
