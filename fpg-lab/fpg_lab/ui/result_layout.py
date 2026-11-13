"""Desktop-first result workspace shared by Lab experiments.

Only the page geometry is shared: each experiment owns its controls and views.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from nicegui import ui

from fpg_lab.ui.components import shell


class ResultWorkspace:
    """Separate scrollable primary views and a persistent, contextual sidebar."""

    def __init__(
        self,
        title: str,
        *,
        back_link: str,
        back_label: str = "Back to setup",
        views: Sequence[str] = ("Canvas",),
        default: str | None = None,
        on_view_change: Callable[[str], None] | None = None,
    ) -> None:
        if not views or len(set(views)) != len(views):
            raise ValueError("Result views must be a non-empty set of unique labels")
        self.active_view = default or views[0]
        if self.active_view not in views:
            raise ValueError("Default view must be present in views")
        self.on_view_change = on_view_change
        shell(None)
        ui.query(".nicegui-content").classes("lab-result-root")
        with ui.column().classes("lab-result-frame"):
            with ui.row().classes("lab-result-toolbar"):
                with ui.row().classes("items-center gap-3 min-w-0 flex-wrap"):
                    ui.link(back_label, back_link).classes("text-sm lab-muted no-underline")
                    ui.label(title).classes("text-lg font-semibold lab-text")
                if len(views) > 1:
                    self.selector = ui.toggle(list(views), value=self.active_view).props(
                        "dense no-caps"
                    ).classes("lab-result-view-switch")
                    self.selector.on_value_change(lambda event: self.select_view(event.value))
                else:
                    self.selector = None
            with ui.element("div").classes("lab-result-grid"):
                with ui.element("div").classes("lab-result-main"):
                    self._main = {}
                    for name in views:
                        pane = ui.column().classes("lab-result-pane")
                        pane.set_visibility(name == self.active_view)
                        self._main[name] = pane
                with ui.column().classes("lab-result-sidebar"):
                    self.controls = ui.column().classes("lab-result-controls")
                    ui.separator().classes("lab-result-divider")
                    self._contexts = {}
                    for name in views:
                        context = ui.column().classes("lab-result-context")
                        context.set_visibility(name == self.active_view)
                        self._contexts[name] = context

    def main(self, name: str) -> ui.column:
        return self._main[name]

    def context(self, name: str) -> ui.column:
        return self._contexts[name]

    def select_view(self, name: str) -> None:
        if name not in self._main or name == self.active_view:
            return
        self.active_view = name
        for key, pane in self._main.items():
            pane.set_visibility(key == name)
        for key, context in self._contexts.items():
            context.set_visibility(key == name)
        if self.selector is not None and self.selector.value != name:
            self.selector.set_value(name)
        # Plotly needs a resize notification when a previously hidden plot becomes visible.
        if ui.context.client.has_socket_connection:
            ui.run_javascript("window.dispatchEvent(new Event('resize'))")
        if self.on_view_change:
            self.on_view_change(name)
