"""Tab-local setup and interactive result pages for E03A."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any
from uuid import uuid4

from fpg_core.domain import RoomType
from nicegui import app, run, ui
from pydantic import ValidationError

from fpg_lab.flows.e03a import Analysis, AreaRange, analyze
from fpg_lab.flows.e03a_config import (
    CONFIG_PATH,
    ROOM_TYPES,
    Configuration,
    export,
    import_e02a,
    maximum_counts,
    parse,
    room_label,
    save,
    width_axis,
)
from fpg_lab.ui.components import action_button, notify_error, shell
from fpg_lab.ui.result_layout import ResultWorkspace
from fpg_lab.visualization.figures import figure

TITLE = "E-03-A · Room Size Configuration Analyzer"
SETUP = "/experiments/e03a"
VIEWS = (
    "Overview",
    "Room configurations",
    "Relationship matrix",
    "Diagnostics",
)
ROOM_FIELDS = {
    "min_width": "Min width (units)",
    "max_width": "Max width (units)",
    "min_area": "Min area (units²)",
    "max_area": "Max area (units²)",
    "count": "Count",
}


def _table(headers: tuple[str, ...], values: list[tuple[Any, ...]]) -> ui.table:
    keys = [str(i) for i in range(len(headers))]
    return (
        ui.table(
            columns=[
                {"name": key, "label": label, "field": key, "align": "left"}
                for key, label in zip(keys, headers, strict=True)
            ],
            rows=[dict(zip(keys, row, strict=True), row_id=i) for i, row in enumerate(values)],
            row_key="row_id",
            pagination=0,
        )
        .props("dense flat hide-bottom")
        .classes("w-full")
    )


def _load() -> tuple[bytes | None, dict[str, Any], str]:
    try:
        contents = CONFIG_PATH.read_bytes()
    except FileNotFoundError:
        return None, {}, "Saved configuration is missing. Import from E02A to start."
    except OSError as exc:
        return None, {}, str(exc)
    try:
        return contents, parse(contents).model_dump(mode="json"), "Loaded saved configuration"
    except (ValueError, ArithmeticError) as exc:
        return contents, {}, f"Saved configuration is invalid. {exc}"


def _validation_message(exc: ValidationError) -> str:
    return " · ".join(
        f"{' / '.join(map(str, issue['loc'])) or 'Configuration'} — {issue['msg']}"
        for issue in exc.errors(include_url=False)
    )


async def _preview_import(
    draft: dict[str, Any],
    confirm: Callable[[dict[str, Any]], None],
) -> None:
    draft = deepcopy(draft)
    try:
        proposal = await run.io_bound(import_e02a, draft)
    except ValueError as exc:
        notify_error(exc)
        return
    if proposal is None:
        return
    updated = proposal.model_dump(mode="json")
    rows = []
    for key in (
        "project_units_per_meter",
        "aspect_precision",
        "default_aspect",
        "limit_attached_bathrooms",
    ):
        if draft.get(key) != updated[key] or key not in draft:
            rows.append((room_label(key), json.dumps(draft.get(key)), json.dumps(updated[key])))
    for room, settings in updated["rooms"].items():
        previous = draft.get("rooms", {}).get(room, {})
        for key, value in settings.items():
            if previous.get(key) != value or key not in previous:
                rows.append(
                    (
                        f"{room_label(room)} · {room_label(key)}",
                        json.dumps(previous.get(key)),
                        json.dumps(value),
                    )
                )
    with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-full"):
        ui.label("Import from E02A").classes("text-lg font-semibold")
        if rows:
            _table(("Setting", "Current draft", "Proposed"), rows).classes(
                "max-h-[55vh] overflow-auto"
            )
        else:
            ui.label("The relevant E02A settings already match this draft.")
        with ui.row():

            def apply() -> None:
                dialog.close()
                confirm(updated)

            action_button("Apply import", role="main", on_click=apply)
            action_button("Cancel", role="subtle", on_click=dialog.close)
    dialog.open()


def _whole_number(value: str) -> int | str:
    try:
        return int(value) if value.isascii() and value.isdecimal() else value
    except ValueError:
        return value


async def setup_page() -> None:
    shell(TITLE, back_link="/")
    expected, draft, message = _load()
    revision = 0
    status = ui.label(message).classes("lab-muted")
    summary = ui.element("div").classes("grid grid-cols-[auto_8rem_6rem] gap-x-5 items-center")
    with ui.row():
        action_button("Reload saved", on_click=lambda: reload())
        action_button("Validate fields", on_click=lambda: validate())
        maximum = action_button("Use maximum counts", on_click=lambda: maximize())
        action_button("Import from E02A", on_click=lambda: preview())
        start = action_button("Start analysis", role="main", on_click=lambda: launch())

    def render() -> None:
        summary.clear()
        maximum.set_enabled(bool(draft))
        with summary:
            if draft:
                for heading in ("Room type", "Selected", "Allowed"):
                    ui.label(heading).classes("font-semibold")
                for room, spec in draft["rooms"].items():
                    label = room_label(room)
                    ui.label(label)
                    count = ui.input(
                        f"{label} count",
                        value=str(spec["count"]),
                        on_change=lambda e, target=spec: set_count(target, e.value),
                    )
                    count.props("dense inputmode=numeric")
                    count.set_enabled(spec["minimum_count"] != spec["maximum_count"])
                    ui.label(f"{spec['minimum_count']}–{spec['maximum_count']}")
        start.set_enabled(validate(show_valid=False) is not None if draft else False)

    def set_count(spec: dict[str, Any], value: str) -> None:
        nonlocal revision
        revision += 1
        spec["count"] = _whole_number(value)
        start.set_enabled(validate() is not None)

    def maximize() -> None:
        nonlocal draft, revision
        draft = {
            **draft,
            "rooms": maximum_counts(draft["rooms"], draft["limit_attached_bathrooms"]),
        }
        revision += 1
        validate()
        render()

    def reload() -> None:
        nonlocal expected, draft, revision
        revision += 1
        expected, draft, message = _load()
        status.set_text(message)
        render()

    def validate(*, show_valid: bool = True) -> Configuration | None:
        try:
            config = Configuration.model_validate(draft)
        except ValidationError as exc:
            status.set_text(_validation_message(exc))
            return None
        if show_valid:
            status.set_text("Configuration fields are valid. Start analysis to check feasibility.")
        return config

    async def preview() -> None:
        original_revision = revision

        def apply(updated: dict[str, Any]) -> None:
            nonlocal draft, revision
            if revision != original_revision:
                ui.notify("The draft changed. Preview the import again.", type="warning")
                return
            draft = updated
            revision += 1
            status.set_text("Import applied to the unsaved draft")
            render()

        await _preview_import(draft, apply)

    async def launch() -> None:
        if (config := validate()) is None:
            return
        await ui.context.client.connected()
        run_id = uuid4().hex
        app.storage.tab["e03a_run"] = {
            "id": run_id,
            "draft": config.model_dump(mode="json"),
            "expected": expected.hex() if expected is not None else None,
        }
        ui.navigate.to(f"{SETUP}/runs/{run_id}")

    render()


async def result_page(run_id: str) -> None:
    client = ui.context.client
    await client.connected()
    handoff = app.storage.tab.get("e03a_run")
    if not handoff or handoff["id"] != run_id:
        shell("E-03-A · Run unavailable", back_link=SETUP)
        ui.link("Start another analysis", SETUP)
        return
    app.storage.tab.pop("e03a_run")
    expected = handoff["expected"]
    workspace = Workspace(
        handoff["draft"],
        bytes.fromhex(expected) if expected is not None else None,
        run_id,
    )
    client.on_delete(workspace.close)


def _compute(
    config: Configuration, locks: dict[RoomType, AreaRange], baseline: Analysis | None
) -> tuple[Analysis, Analysis]:
    base = baseline if baseline is not None else analyze(config)
    return base, analyze(config, locks, base) if locks else base


class Workspace:
    def __init__(self, draft: dict[str, Any], expected: bytes | None, run_id: str) -> None:
        self.draft = draft
        self.expected = expected
        self.locks: dict[RoomType, AreaRange] = {}
        self.revision = 0
        self.task: asyncio.Task[None] | None = None
        self.closed = False
        self.saving = False
        self.baseline_config: Configuration | None = None
        self.baseline: Analysis | None = None
        self.result: Analysis | None = None
        self.selected: RoomType | None = None
        self.workspace = ResultWorkspace(TITLE, back_link=SETUP, views=VIEWS)
        with self.workspace.controls:
            self.status = ui.label().classes("font-semibold")
            self.file_status = ui.label(f"Run {run_id[:8]}").classes("lab-muted text-sm")
            self.save_button = action_button(
                "Save configuration", role="main", on_click=self.save_draft
            )
            self.export_button = action_button("Export JSON", on_click=self.export_draft)
            action_button("Import from E02A", on_click=self.preview)
            self.reset_button = action_button(
                "Reset unsaved edits", role="danger", on_click=self.reset
            )
            self.lock_panel = ui.column().classes("w-full")
        self.draw_editor()
        self.draw_matrix()
        self.changed()

    def close(self) -> None:
        self.closed = True

    def changed(self) -> None:
        self.revision += 1
        self.result = None
        config = self.validate()
        self.save_button.disable()
        self.export_button.set_enabled(config is not None)
        if config is not None:
            self.status.set_text("Calculating…")
        self.draw_results()
        if config is not None and (self.task is None or self.task.done()):
            self.task = asyncio.create_task(self.calculate())

    def validate(self, *, show_error: bool = True) -> Configuration | None:
        try:
            return Configuration.model_validate(self.draft)
        except ValidationError as exc:
            if show_error:
                self.status.set_text(f"Invalid input · {_validation_message(exc)}")
            return None

    async def calculate(self) -> None:
        while not self.closed:
            revision = self.revision
            await asyncio.sleep(0.25)
            if self.closed:
                return
            if revision != self.revision:
                continue
            config = self.validate()
            if config is None:
                return
            reusable = (
                self.baseline
                if config == self.baseline_config
                and self.baseline
                and self.baseline.status != "incomplete"
                else None
            )
            try:
                output = await run.io_bound(_compute, config, dict(self.locks), reusable)
            except Exception as exc:
                if revision == self.revision and not self.closed:
                    self.status.set_text(f"Analysis error · {exc}")
                if revision != self.revision:
                    continue
                return
            if self.closed:
                return
            if revision != self.revision:
                continue
            if output is None:
                return
            self.baseline_config = config
            self.baseline, self.result = output
            suffix = (
                f" · unlocked {self.baseline.status}"
                if any(config.rooms[room].count for room in self.locks)
                else ""
            )
            self.status.set_text(f"{self.result.status.capitalize()}{suffix}")
            self.save_button.set_enabled(not self.saving)
            self.draw_results()
            return

    async def save_draft(self) -> None:
        config = self.validate()
        if config is None or self.saving or self.result is None:
            return
        self.saving = True
        self.save_button.disable()
        self.reset_button.disable()
        try:
            contents = await run.io_bound(save, config, self.expected)
            if contents is not None:
                self.expected = contents
                self.file_status.set_text(
                    "Saved configuration"
                    if config == self.validate(show_error=False)
                    else "Saved previous draft · newer edits are unsaved"
                )
        except (OSError, ValueError) as exc:
            notify_error(exc)
        finally:
            self.saving = False
            self.reset_button.enable()
            self.save_button.set_enabled(self.result is not None)

    def export_draft(self) -> None:
        if (config := self.validate()) is not None:
            ui.download.content(
                export(config), filename="e03a-config.json", media_type="application/json"
            )

    def reset(self) -> None:
        if self.saving:
            return
        expected, draft, message = _load()
        self.file_status.set_text(message)
        if draft:
            self.expected, self.draft = expected, draft
            self.redraw_configuration()

    async def preview(self) -> None:
        revision = self.revision

        def apply(updated: dict[str, Any]) -> None:
            if revision != self.revision:
                ui.notify("The draft changed. Preview the import again.", type="warning")
                return
            self.draft = updated
            self.file_status.set_text("Import applied to the unsaved draft")
            self.redraw_configuration()

        await _preview_import(self.draft, apply)

    def redraw_configuration(self) -> None:
        self.draw_editor()
        self.draw_matrix()
        self.changed()

    def draw_editor(self) -> None:
        pane = self.workspace.main("Room configurations")
        pane.clear()

        def edit_ratio(target: dict[str, Any], key: str, label: str) -> None:
            ui.input(
                label,
                value=str(target.get(key, "")),
                on_change=lambda e: update(target, key, e.value),
            ).props("dense").classes("w-24")

        def update(target: dict[str, Any], field: str, value: Any) -> None:
            target[field] = _whole_number(value) if field == "count" else value
            self.file_status.set_text("Unsaved configuration edits")
            self.changed()

        with pane:
            ui.label("Default room aspect ratio · X ÷ Y").classes("font-semibold")
            with ui.row().classes("items-center"):
                default = self.draft.get("default_aspect")

                def set_default(event: Any) -> None:
                    update(
                        self.draft,
                        "default_aspect",
                        {"min_ratio": "0.60", "max_ratio": "1.80"} if event.value else None,
                    )
                    self.draw_editor()

                ui.switch("Enabled", value=default is not None, on_change=set_default)
                if default is not None:
                    edit_ratio(default, "min_ratio", "Minimum")
                    edit_ratio(default, "max_ratio", "Maximum")
            ui.label("10 units = 1 m · 100 units² = 1 m²").classes("text-sm lab-muted")
            for room_type in ROOM_TYPES:
                spec = self.draft["rooms"][room_type.value]
                override = spec["aspect"]
                with ui.expansion(room_label(room_type.value), value=True).classes("w-full"):
                    axis = "X span" if width_axis(room_type).value == "x" else "shorter span"
                    ui.label(
                        f"Maximum width applies to the {axis} · Count {spec['minimum_count']}–{spec['maximum_count']}"
                    ).classes("text-sm lab-muted")
                    with ui.row().classes("items-center gap-2"):
                        for field, label in ROOM_FIELDS.items():
                            ui.input(
                                label,
                                value=str(spec[field]),
                                on_change=lambda e, s=spec, k=field: update(s, k, e.value),
                            ).props("dense").classes("w-24")
                        modes = {
                            "inherit": "Use default",
                            "custom": "Override",
                            "none": "Unrestricted",
                        }
                        mode = (
                            "inherit"
                            if override == "inherit"
                            else ("none" if override is None else "custom")
                        )

                        def set_mode(event: Any, settings: dict = spec) -> None:
                            default_bounds = self.draft.get("default_aspect") or {
                                "min_ratio": "0.60",
                                "max_ratio": "1.80",
                            }
                            update(
                                settings,
                                "aspect",
                                dict(default_bounds)
                                if event.value == "custom"
                                else (None if event.value == "none" else "inherit"),
                            )
                            self.draw_editor()

                        ui.select(modes, value=mode, label="Room aspect", on_change=set_mode).props(
                            "dense"
                        ).classes("w-28")
                        if isinstance(override, dict):
                            edit_ratio(override, "min_ratio", "Min aspect")
                            edit_ratio(override, "max_ratio", "Max aspect")

    def draw_matrix(self) -> None:
        pane = self.workspace.main("Relationship matrix")
        pane.clear()
        cross = {
            (rule["compared_type"], rule["reference_type"]): rule
            for rule in self.draft["cross_type_rules"]
        }
        same = {rule["room_type"]: rule for rule in self.draft["same_type_rules"]}
        rooms = [room.value for room in ROOM_TYPES]
        with pane:
            ui.label("Compared rooms ↓  ·  Reference rooms →").classes("lab-muted")
            with (
                ui.element("div").classes("w-full overflow-x-auto"),
                ui.element("table").classes("w-full text-sm"),
            ):
                with ui.element("thead"), ui.element("tr"):
                    ui.element("th")
                    for room in rooms:
                        with ui.element("th").classes("p-1 text-left"):
                            ui.label(room_label(room))
                with ui.element("tbody"):
                    for a in rooms:
                        with ui.element("tr"):
                            with ui.element("th").classes("text-left pr-2"):
                                ui.label(room_label(a))
                            for b in rooms:
                                rule = same.get(a) if a == b else cross.get((a, b))
                                label = "+"
                                if rule is not None:
                                    label = (
                                        format(float(rule["maximum_spread_ratio"]), ".3g")
                                        if a == b
                                        else f"{rule['min_ratio'] or '–'} / {rule['max_ratio'] or '–'}"
                                    )
                                with ui.element("td").classes("p-1"):
                                    action_button(
                                        label,
                                        role="subtle" if rule is None else "general",
                                        on_click=lambda first=a, second=b, old=rule: self.edit_rule(
                                            first, second, old
                                        ),
                                    ).props(
                                        f'dense outline no-caps aria-label="Edit {room_label(a)} to {room_label(b)} rule"'
                                    ).tooltip(f"{room_label(a)} / {room_label(b)}")

    def edit_rule(self, a: str, b: str, old: dict[str, Any] | None) -> None:
        diagonal = a == b
        group = "same_type_rules" if diagonal else "cross_type_rules"
        fields = (
            {"maximum_spread_ratio": "Maximum spread ratio"}
            if diagonal
            else {
                "min_ratio": "Minimum area ratio",
                "max_ratio": "Maximum area ratio",
            }
        )
        with ui.dialog() as dialog, ui.card():
            ui.label(
                f"{room_label(a)} spread" if diagonal else f"{room_label(a)} to {room_label(b)}"
            ).classes("font-semibold")
            inputs = {
                key: ui.input(label, value=str((old or {}).get(key) or ""))
                for key, label in fields.items()
            }
            issue = ui.label().classes("text-negative")

            def apply(remove: bool = False) -> None:
                from fpg_lab.flows.e03a_config import CrossRule, SameRule

                rules = [rule for rule in self.draft[group] if rule != old]
                if not remove:
                    values = {key: item.value.strip() or None for key, item in inputs.items()}
                    try:
                        rule = (
                            SameRule.model_validate({"room_type": a, **values})
                            if diagonal
                            else CrossRule.model_validate(
                                {"compared_type": a, "reference_type": b, **values}
                            )
                        )
                    except ValidationError as exc:
                        issue.set_text(_validation_message(exc))
                        return
                    rules.append(rule.model_dump(mode="json"))
                self.draft[group] = rules
                self.file_status.set_text("Unsaved configuration edits")
                dialog.close()
                self.draw_matrix()
                self.changed()

            with ui.row():
                action_button("Apply rule", role="main", on_click=lambda: apply())
                if old is not None:
                    action_button("Remove rule", role="danger", on_click=lambda: apply(True))
                action_button("Cancel", role="subtle", on_click=dialog.close)
        dialog.open()

    def draw_results(self) -> None:
        overview = self.workspace.main("Overview")
        diagnostics = self.workspace.main("Diagnostics")
        overview.clear()
        diagnostics.clear()
        self.draw_locks()
        result, baseline, config = self.result, self.baseline, self.baseline_config
        if result is None or baseline is None or config is None:
            return
        active = [kind for kind in ROOM_TYPES if config.rooms[kind].count]
        compare = any(kind in self.locks for kind in active)

        with overview:
            rows = []
            for kind in ROOM_TYPES:
                room = f"{kind.value}_1"
                spec = config.rooms[kind]
                supported = result.supported.get(room)
                flex = result.flexibility(room)
                span = result.ranges(room)
                original = baseline.ranges(room)
                current: tuple[Any, ...] = (
                    room_label(kind.value),
                    spec.count,
                    f"{spec.min_area / 100:g}–{spec.max_area / 100:g}",
                    _span(span, 0, 100) if spec.count else "Inactive",
                    f"{len(supported)} / {len(result.dimensions[room])}"
                    if supported is not None
                    else "—",
                    f"{flex:.1f}%" if flex is not None else "—",
                )
                if compare:
                    affected = result.supported.get(room) != baseline.supported.get(room)
                    current += (_span(original, 0, 100), "Changed" if affected else "—")
                rows.append(current)

            headers: tuple[str, ...] = (
                "Room type",
                "Count",
                "Configured (m²)",
                "Feasible (m²)",
                "Area options",
                "Flexibility",
            )
            if compare:
                headers += ("Unlocked (m²)", "Lock effect")
            _table(headers, rows)
            if any(result.flexibility(f"{kind.value}_1") is not None for kind in active):
                chart = figure("Retained area options by room type")
                labels = [room_label(kind.value) for kind in active]
                if compare:
                    chart.add_bar(
                        name="Unlocked",
                        x=labels,
                        y=[baseline.flexibility(f"{kind.value}_1") for kind in active],
                    )
                chart.add_bar(
                    name="Current",
                    x=labels,
                    y=[result.flexibility(f"{kind.value}_1") for kind in active],
                )
                chart.update_yaxes(range=[0, 100], ticksuffix="%")
                ui.plotly(chart).classes("w-full h-[270px]")

        with diagnostics:
            if result.category:
                ui.label(f"{result.category} conflict").classes("font-semibold")
            for line in result.diagnostics:
                ui.label(line)
            if result.inactive:
                ui.label("Inapplicable rules").classes("font-semibold")
                for a, b in result.inactive:
                    ui.label(
                        f"{room_label(a.value)} spread"
                        if a == b
                        else f"{room_label(a.value)} to {room_label(b.value)}"
                    )
            if result.status == "compatible":
                ui.label(
                    "Compatible sizes can come from different arrangements. Check the combination you intend to use."
                ).classes("lab-muted")
            if result.witness:
                with ui.expansion("Compatible sizing example").classes("w-full"):
                    _table(
                        ("Room", "Width (m)", "Length (m)", "Area (m²)", "Area (units²)"),
                        [
                            (room_label(room), width / 10, length / 10, area / 100, area)
                            for room, (width, length, area) in result.witness.items()
                        ],
                    )

    def draw_locks(self) -> None:
        self.lock_panel.clear()
        result, config = self.result, self.baseline_config
        with self.lock_panel:
            ui.label("Area-range locks").classes("font-semibold")
            for kind, area in self.locks.items():
                inactive = (
                    " · inactive" if config is not None and not config.rooms[kind].count else ""
                )
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label(
                        f"{room_label(kind.value)} · {area.minimum}–{area.maximum} units²{inactive}"
                    )
                    action_button(
                        f"Remove {room_label(kind.value)} lock",
                        role="subtle",
                        on_click=lambda target=kind: self.set_lock(target, None),
                    ).props("dense")
            if self.locks:
                action_button("Clear all locks", role="subtle", on_click=self.clear_locks)
            if result is None or config is None:
                return
            choices = {
                kind.value: room_label(kind.value)
                for kind in ROOM_TYPES
                if config.rooms[kind].count or kind in self.locks
            }
            if not choices:
                return
            if self.selected is None or self.selected.value not in choices:
                self.selected = RoomType(next(iter(choices)))

            def select(event: Any) -> None:
                self.selected = RoomType(event.value)
                self.draw_locks()

            ui.select(
                choices, value=self.selected.value, label="Room type", on_change=select
            ).classes("w-full")
            kind = self.selected
            room = f"{kind.value}_1"
            lock = self.locks.get(kind)
            if not config.rooms[kind].count:
                return
            minimum = (
                ui.input("Minimum area (units²)", value=str(lock.minimum) if lock else "")
                .props("dense inputmode=numeric")
                .classes("w-full")
            )
            maximum = (
                ui.input("Maximum area (units²)", value=str(lock.maximum) if lock else "")
                .props("dense inputmode=numeric")
                .classes("w-full")
            )
            issue = ui.label().classes("text-negative text-sm")

            def apply() -> None:
                lo, hi = _whole_number(minimum.value.strip()), _whole_number(maximum.value.strip())
                if not isinstance(lo, int) or not isinstance(hi, int):
                    issue.set_text("Enter whole areas in project units².")
                    return
                try:
                    area = AreaRange(lo, hi)
                except ValueError as exc:
                    issue.set_text(str(exc))
                    return
                self.set_lock(kind, area)

            action_button("Apply range lock", on_click=apply)

            current = result.ranges(room)
            original = self.baseline.ranges(room) if self.baseline else ()
            with ui.expansion("Feasible dimensions", value=lock is not None).classes("w-full"):
                _table(
                    ("Range", "Unlocked", "Current"),
                    [
                        (label, _span(original, i, scale), _span(current, i, scale))
                        for i, (label, scale) in enumerate(
                            (("Area (m²)", 100), ("Width (m)", 10), ("Length (m)", 10))
                        )
                    ],
                )
            supported = result.supported.get(room)
            if lock is not None and supported is not None:
                requested = lock.maximum - lock.minimum + 1
                if not supported:
                    ui.label("No area in the requested range has global support.").classes(
                        "lab-muted text-sm"
                    )
                elif len(supported) < requested:
                    ui.label(
                        f"Partial range support · {len(supported)} of {requested} whole areas"
                    ).classes("lab-muted text-sm")
                    ui.label(f"Feasible area · {supported[0]}–{supported[-1]} units²").classes(
                        "lab-muted text-sm"
                    )

            with ui.expansion("Same-type variation", value=True).classes("w-full"):
                if config.rooms[kind].count < 2:
                    ui.label("Not applicable · fewer than two rooms").classes("lab-muted text-sm")
                    return
                rule = next(
                    (rule for rule in config.same_type_rules if rule.room_type == kind), None
                )
                ui.label(
                    f"Configured tolerance · {rule.maximum_spread_ratio * 100:g}%"
                    if rule
                    else "Configured tolerance · none"
                )
                variation = result.variation.get(kind)
                if variation is None:
                    ui.label("Variation unavailable for this result").classes("lab-muted text-sm")
                    return
                ui.label(f"Maximum area difference · {variation.difference / 100:g} m²")
                ui.label(f"Maximum relative spread · {float(variation.spread) * 100:.2f}%")
                ui.label(
                    "Other relationships narrow the achievable variation."
                    if variation.restricted_by_other_rules
                    else "The same variation is achievable with all relationships applied."
                ).classes("lab-muted text-sm")

    def set_lock(self, room: RoomType, area: AreaRange | None) -> None:
        if area is None:
            self.locks.pop(room, None)
        else:
            self.locks[room] = area
        self.changed()

    def clear_locks(self) -> None:
        self.locks.clear()
        self.changed()


def _span(ranges: tuple[tuple[int, int], ...], index: int, scale: int) -> str:
    if not ranges:
        return "—"
    low, high = ranges[index]
    return f"{low / scale:g}–{high / scale:g}"
