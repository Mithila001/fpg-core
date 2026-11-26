"""Tab-local setup and interactive result pages for E03A."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from copy import deepcopy
from decimal import Decimal
from typing import Any

from fpg_core.domain import RoomType
from nicegui import run, ui
from pydantic import ValidationError

from fpg_lab.e03a_config import (
    ROOM_TYPES,
    Configuration,
    export,
    refresh_profile_inputs,
    room_label,
    width_axis,
)
from fpg_lab.flows.e03a import Analysis, AreaRange, analyze
from fpg_lab.services.common import SystemConfigurationService
from fpg_lab.ui.components import action_button, db_call, notify_error, profile_picker, shell
from fpg_lab.ui.result_layout import ResultWorkspace

TITLE = "E-03-A · Room Size Configuration Analyzer"
SETUP = "/experiments/e03a"
VIEWS = ("Rooms", "Relationships")
ROOM_FIELDS = {
    "min_width": "Min width (units)",
    "max_width": "Max width (units)",
    "min_area": "Min area (units²)",
    "max_area": "Max area (units²)",
    "count": "Count",
}


def _hint(message: str) -> None:
    with (
        ui.element("span")
        .classes("inline-flex items-center lab-muted cursor-help text-base")
        .props(f'role="img" aria-label="{message}"')
    ):
        ui.icon("help_outline")
        ui.tooltip(message).props('delay="300" max-width="320px"').classes("text-sm")


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


async def _load(runtime, profile_id):
    def read(session):
        record, validated = SystemConfigurationService(session, runtime.codec).for_flow(
            profile_id, "e03a"
        )
        return record.id, record.name, record.config_hash, validated.payload["experiments"]["e03a"]

    return await db_call(runtime, read)


def _validation_message(exc: ValidationError) -> str:
    return " · ".join(
        f"{' / '.join(map(str, issue['loc'])) or 'Configuration'} — {issue['msg']}"
        for issue in exc.errors(include_url=False)
    )


async def _preview_import(
    draft: dict[str, Any],
    source: dict[str, Any],
    confirm: Callable[[dict[str, Any]], None],
) -> None:
    draft = deepcopy(draft)
    try:
        proposal = await run.io_bound(refresh_profile_inputs, draft, source)
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
        with ui.row().classes("items-center gap-1"):
            ui.label("Refresh profile inputs").classes("text-lg font-semibold")
            _hint(
                "Current draft shows what you have now. Proposed shows what applying the import "
                "would change. Your relationship rules stay in the draft, and saving is separate."
            )
        if rows:
            _table(("Setting", "Current draft", "Proposed"), rows).classes(
                "max-h-[55vh] overflow-auto"
            )
        else:
            ui.label("The profile inputs already match this draft.")
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


async def setup_page(runtime) -> None:
    with ui.row().classes("items-center"):
        profile = await profile_picker(runtime)
        load_button = action_button("Load profile")
    area = ui.column().classes("w-full")
    workspace = None

    async def load():
        nonlocal workspace
        load_button.disable()
        try:
            profile_id, name, expected, draft = await _load(runtime, profile.value)
            if workspace is not None:
                workspace.close()
            area.clear()
            with area:
                workspace = Workspace(runtime, profile_id, name, draft, expected)
        except Exception as exc:
            notify_error(exc)
        finally:
            load_button.enable()

    load_button.on_click(load)
    await load()


async def result_page(run_id: str) -> None:
    shell("E-03-A · Session ended", back_link=SETUP)
    ui.link("Open room sizing workspace", SETUP)


def _compute(
    config: Configuration, locks: dict[RoomType, AreaRange], baseline: Analysis | None
) -> tuple[Analysis, Analysis]:
    base = baseline if baseline is not None else analyze(config)
    return base, analyze(config, locks, base) if locks else base


class Workspace:
    def __init__(self, runtime, profile_id, profile_name, draft, expected) -> None:
        self.runtime = runtime
        self.profile_id = profile_id
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
        self.before_rule: Analysis | None = None
        ui.context.client.on_delete(self.close)
        self.workspace = ResultWorkspace(
            TITLE, back_link="/", back_label="Experiments", views=VIEWS
        )
        with self.workspace.controls:
            with ui.column().classes("w-full rounded border border-white/10 bg-white/5 p-3 gap-2"):
                with ui.row().classes("items-center gap-1"):
                    ui.label("Analysis").classes("font-semibold")
                    _hint(
                        "Results update after every edit. A compatible result means the room sizes "
                        "can coexist under these rules. The analysis checks sizes only."
                    )
                self.status = ui.label().classes("text-sm").props('role="status"')
                self.analysis_panel = ui.column().classes("w-full gap-1")
            self.lock_panel = ui.column().classes("w-full rounded border border-white/10 p-3 gap-2")
            with ui.column().classes("w-full border-t border-white/10 pt-3 gap-2"):
                ui.label("Configuration").classes("font-semibold")
                self.file_status = ui.label(f"Editing {profile_name}").classes(
                    "lab-muted text-sm"
                )
                self.save_button = (
                    action_button("Save configuration", role="main", on_click=self.save_draft)
                    .props("dense no-caps")
                    .classes("w-full")
                )
                with ui.row().classes("w-full gap-1"):
                    action_button("Refresh profile inputs", role="subtle", on_click=self.preview).props(
                        "dense no-caps"
                    )
                    self.export_button = action_button(
                        "Export JSON", role="subtle", on_click=self.export_draft
                    ).props("dense no-caps")
                    self.reset_button = action_button(
                        "Reset unsaved edits", role="danger", on_click=self.reset
                    ).props("flat dense no-caps")
        self.draw_matrix()
        self.changed()

    def close(self) -> None:
        self.closed = True

    def changed(self, *, rule_edit: bool = False) -> None:
        self.before_rule = (
            self.result
            if rule_edit and self.result and self.result.status != "incomplete"
            else None
        )
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
            messages = {
                "compatible": "Room sizes can work together",
                "incompatible": "The current sizes cannot work together",
                "incomplete": "Analysis could not finish",
            }
            self.status.set_text(messages[self.result.status])
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
            contents = await db_call(self.runtime, lambda session: (
                SystemConfigurationService(session, self.runtime.codec).save_section(
                    self.profile_id, "experiments.e03a", config.model_dump(mode="json"),
                    expected_hash=self.expected,
                ).config_hash
            ))
            if contents is not None:
                self.expected = contents
                self.file_status.set_text(
                    "Saved configuration"
                    if config == self.validate(show_error=False)
                    else "Saved previous draft · newer edits are unsaved"
                )
        except Exception as exc:
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

    async def reset(self) -> None:
        if self.saving:
            return
        try:
            _, name, expected, draft = await _load(self.runtime, self.profile_id)
            self.expected, self.draft = expected, draft
            self.file_status.set_text(f"Editing {name}")
            self.redraw_configuration()
        except Exception as exc:
            notify_error(exc)

    async def preview(self) -> None:
        revision = self.revision

        def apply(updated: dict[str, Any]) -> None:
            if revision != self.revision:
                ui.notify("The draft changed. Preview the import again.", type="warning")
                return
            self.draft = updated
            self.file_status.set_text("Import applied to the unsaved draft")
            self.redraw_configuration()

        try:
            source = await db_call(self.runtime, lambda session: (
                SystemConfigurationService(session, self.runtime.codec)
                .for_flow(self.profile_id, "e03a_refresh")[1].payload
            ))
            await _preview_import(self.draft, source, apply)
        except Exception as exc:
            notify_error(exc)

    def redraw_configuration(self) -> None:
        self.draw_matrix()
        self.changed()

    def draw_rooms(self) -> None:
        pane = self.workspace.main("Rooms")
        pane.clear()
        with pane:
            action_button("Default room shape", role="subtle", on_click=lambda: self.edit_room())
            with (
                ui.element("div").classes("w-full overflow-x-auto"),
                ui.element("table").classes("w-full text-sm"),
            ):
                with ui.element("thead"), ui.element("tr"):
                    for heading in (
                        "Room type",
                        "Count",
                        "Allowed (m²)",
                        "Possible (m²)",
                        "Actions",
                    ):
                        with ui.element("th").classes("p-2 text-left"):
                            with ui.row().classes("items-center gap-1 flex-nowrap"):
                                ui.label(heading)
                                if heading == "Possible (m²)":
                                    _hint(
                                        "Smallest and largest areas that fit the current rules and "
                                        "area tests. Open Details to see how many distinct areas fit."
                                    )
                with ui.element("tbody"):
                    for kind in ROOM_TYPES:
                        name = room_label(kind.value)
                        spec = self.draft["rooms"][kind.value]
                        room = f"{kind.value}_1"
                        possible = _possible(self.result, room) if spec["count"] else "Inactive"
                        with ui.element("tr").classes("border-t border-white/10"):
                            for value in (
                                name,
                                str(spec["count"]),
                                f"{Decimal(spec['min_area']) / 100:g}–{Decimal(spec['max_area']) / 100:g}",
                                possible,
                            ):
                                with ui.element("td").classes("p-2"):
                                    ui.label(value)
                            with ui.element("td").classes("p-2"), ui.row().classes("gap-1"):
                                action_button(
                                    "Edit",
                                    role="general",
                                    on_click=lambda k=kind: self.edit_room(k),
                                ).props(f'dense outline no-caps aria-label="Edit {name}"')
                                if spec["count"]:
                                    action_button(
                                        "Details",
                                        role="subtle",
                                        on_click=lambda k=kind: self.room_details(k),
                                    ).props(
                                        f'dense no-caps aria-label="{name} details"'
                                    ).set_enabled(self.result is not None)
                                    action_button(
                                        "Test area",
                                        role="subtle",
                                        on_click=lambda k=kind: self.test_area(k),
                                    ).props(f'dense no-caps aria-label="Test {name} area"')

    def edit_room(self, kind: RoomType | None = None) -> None:
        candidate = deepcopy(self.draft)
        spec = candidate["rooms"][kind.value] if kind is not None else None
        with ui.dialog() as dialog, ui.card().classes("w-[34rem] max-w-full"):
            ui.label(f"Edit {room_label(kind.value)}" if kind else "Default room shape").classes(
                "text-lg font-semibold"
            )
            fields = {}
            if kind and spec is not None:
                ui.label(
                    f"Count {spec['minimum_count']}–{spec['maximum_count']} · "
                    f"Maximum width applies to the {('X span' if width_axis(kind).value == 'x' else 'shorter span')}."
                ).classes("lab-muted text-sm")
                with ui.row().classes("gap-2"):
                    for field, label in ROOM_FIELDS.items():
                        fields[field] = (
                            ui.input(label, value=str(spec[field])).props("dense").classes("w-28")
                        )
            with ui.row().classes("items-center gap-1"):
                ui.label("Room shape · X ÷ Y").classes("font-semibold")
                _hint(
                    "A ratio of 1 is square. A ratio of 1.5 means X is 50% longer than Y. "
                    "Use default inherits the shared room shape. Set bounds overrides it for this room type."
                )
            shape = spec["aspect"] if spec is not None else candidate["default_aspect"]
            options = {"none": "Unrestricted", "custom": "Set bounds"}
            if spec is not None:
                options = {"inherit": "Use default", **options}
            mode = ui.radio(
                options, value="custom" if isinstance(shape, dict) else shape or "none"
            ).props("inline")
            bounds = shape if isinstance(shape, dict) else candidate["default_aspect"]
            bounds = bounds or {"min_ratio": "0.60", "max_ratio": "1.80"}
            with ui.row().bind_visibility_from(mode, "value", lambda value: value == "custom"):
                minimum = ui.input("Minimum X ÷ Y", value=str(bounds["min_ratio"]))
                maximum = ui.input("Maximum X ÷ Y", value=str(bounds["max_ratio"]))
            issue = ui.label().classes("text-negative")

            def apply() -> None:
                aspect: str | dict[str, Any] | None = None
                if mode.value == "inherit":
                    aspect = "inherit"
                elif mode.value == "custom":
                    aspect = {"min_ratio": minimum.value, "max_ratio": maximum.value}
                if spec is not None:
                    spec.update({key: value.value for key, value in fields.items()}, aspect=aspect)
                    spec["count"] = _whole_number(spec["count"].strip())
                else:
                    candidate["default_aspect"] = aspect
                try:
                    config = Configuration.model_validate(candidate)
                except ValidationError as exc:
                    issue.set_text(_validation_message(exc))
                    return
                self.draft = config.model_dump(mode="json")
                self.file_status.set_text("Unsaved configuration edits")
                dialog.close()
                self.changed()

            with ui.row():
                action_button("Apply room settings", role="main", on_click=apply)
                action_button("Cancel", role="subtle", on_click=dialog.close)
        dialog.open()

    def draw_matrix(self) -> None:
        pane = self.workspace.main("Relationships")
        pane.clear()
        cross = {
            (rule["compared_type"], rule["reference_type"]): rule
            for rule in self.draft["cross_type_rules"]
        }
        same = {rule["room_type"]: rule for rule in self.draft["same_type_rules"]}
        rooms = [room.value for room in ROOM_TYPES]
        with pane:
            with ui.row().classes("items-center gap-2"):
                ui.label(
                    "Pick the room to size on the left, then the room to compare it with across the top."
                ).classes("lab-muted")
                _hint(
                    "Select + to add a rule or a value to edit it. A diagonal cell limits how "
                    "much two rooms of the same type can differ in area."
                )
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
            with ui.row().classes("items-center gap-1"):
                ui.label(
                    f"{room_label(a)} spread" if diagonal else f"{room_label(a)} to {room_label(b)}"
                ).classes("font-semibold")
                _hint(
                    "Enter 0 to require equal areas. Enter 0.2 to allow the larger room "
                    "to be up to 20% bigger than the smaller room."
                    if diagonal
                    else "Divide the first room’s area by the second room’s area. Fill either bound "
                    "or both. The rule applies to every pair of those room types."
                )
            if not diagonal:
                ui.label(
                    f"A minimum of 0.5 means each {room_label(a)} must be at least half the area of each {room_label(b)}."
                ).classes("lab-muted")
            inputs = {
                key: ui.input(label, value=str((old or {}).get(key) or ""))
                for key, label in fields.items()
            }
            issue = ui.label().classes("text-negative")

            def apply(remove: bool = False) -> None:
                from fpg_lab.e03a_config import CrossRule, SameRule

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
                self.changed(rule_edit=True)

            with ui.row():
                action_button("Apply rule", role="main", on_click=lambda: apply())
                if old is not None:
                    action_button("Remove rule", role="danger", on_click=lambda: apply(True))
                action_button("Cancel", role="subtle", on_click=dialog.close)
        dialog.open()

    def draw_results(self) -> None:
        self.draw_rooms()
        self.analysis_panel.clear()
        self.lock_panel.clear()
        self.lock_panel.set_visibility(bool(self.locks))
        context = self.workspace.context("Relationships")
        context.clear()
        result, baseline, config = self.result, self.baseline, self.baseline_config
        with self.lock_panel:
            if self.locks:
                with ui.row().classes("items-center gap-1"):
                    ui.label("Temporary area tests").classes("font-semibold")
                    _hint(
                        "A test restricts every room of that type. Remove it to see which areas "
                        "fit without the test. Saving keeps only your configuration."
                    )
                for kind, area in self.locks.items():
                    name = room_label(kind.value)
                    inactive = " · inactive" if not self.draft["rooms"][kind.value]["count"] else ""
                    with ui.row().classes("items-center"):
                        ui.label(
                            f"{name} · {area.minimum / 100:g}–{area.maximum / 100:g} m²{inactive}"
                        )
                        action_button(
                            "Remove", role="subtle", on_click=lambda k=kind: self.set_lock(k, None)
                        ).props(f'dense no-caps aria-label="Remove {name} test"')
            if (
                self.locks
                and result
                and baseline
                and "incomplete" not in (result.status, baseline.status)
            ):
                self.show_effect("Effect of temporary tests", baseline, result)
        if result is None or baseline is None or config is None:
            return
        with self.analysis_panel:
            if result.status == "incompatible":
                if result.category == "Area-range lock":
                    ui.label("Widen or remove a temporary area test.")
                elif result.category == "Dimension":
                    ui.label("Review the size and shape limits of the affected rooms.")
                    action_button(
                        "Review rooms",
                        role="subtle",
                        on_click=lambda: self.workspace.select_view("Rooms"),
                    )
                else:
                    ui.label("Review the relationships between the affected rooms.")
                    action_button(
                        "Review relationships",
                        role="subtle",
                        on_click=lambda: self.workspace.select_view("Relationships"),
                    )
            with ui.row().classes("gap-1"):
                if result.diagnostics or result.inactive:
                    action_button(
                        "Analysis details", role="subtle", on_click=self.analysis_details
                    ).props("dense no-caps")
                if result.status == "compatible" and result.witness:
                    action_button(
                        "Example sizes", role="subtle", on_click=self.example_sizes
                    ).props("dense no-caps")
        with context:
            ui.label("Possible room areas (m²)").classes("font-semibold")
            _table(
                ("Room", "Possible"),
                [
                    (room_label(kind.value), _possible(result, f"{kind.value}_1"))
                    for kind in ROOM_TYPES
                    if config.rooms[kind].count
                ],
            )
            if self.before_rule is not None and result.status != "incomplete":
                self.show_effect("Effect of last rule edit", self.before_rule, result)

    def show_effect(self, title: str, before: Analysis, after: Analysis) -> None:
        with ui.row().classes("items-center gap-1"):
            ui.label(title).classes("font-semibold text-sm")
            _hint(
                "Read each arrow from before to after. Options counts distinct areas that fit. "
                "That set can change even when its smallest and largest values stay the same."
            )
        rows = []
        for kind in ROOM_TYPES:
            room = f"{kind.value}_1"
            previous, current = before.supported.get(room), after.supported.get(room)
            if previous != current:
                old_area, new_area = _possible(before, room), _possible(after, room)
                change = (
                    f"{old_area} → {new_area} m²"
                    if old_area != new_area and previous and current
                    else (
                        f"{old_area} → {new_area}"
                        if old_area != new_area
                        else "Area options changed"
                    )
                )
                counts = f"{len(previous or ())} → {len(current or ())}"
                rows.append((room_label(kind.value), change, counts))
        if rows:
            _table(("Room", "Range", "Options"), rows)
        else:
            ui.label("Possible areas stayed the same.").classes("lab-muted text-sm")

    def analysis_details(self) -> None:
        result = self.result
        if result is None:
            return
        with ui.dialog() as dialog, ui.card().classes("w-[42rem] max-w-full"):
            ui.label("Analysis details").classes("text-lg font-semibold")
            for line in result.diagnostics:
                ui.label(line)
            if result.inactive:
                ui.label("Inactive rules").classes("font-semibold")
                for a, b in result.inactive:
                    ui.label(
                        room_label(a.value) + (" spread" if a == b else f" / {room_label(b.value)}")
                    )
            action_button("Close", role="subtle", on_click=dialog.close)
        dialog.open()

    def example_sizes(self) -> None:
        if self.result is None:
            return
        with ui.dialog() as dialog, ui.card().classes("w-[42rem] max-w-full"):
            ui.label("One compatible set of room sizes").classes("text-lg font-semibold")
            _table(
                ("Room", "Width (m)", "Length (m)", "Area (m²)"),
                [
                    (room_label(room), x / 10, y / 10, area / 100)
                    for room, (x, y, area) in self.result.witness.items()
                ],
            )
            action_button("Close", role="subtle", on_click=dialog.close)
        dialog.open()

    def room_details(self, kind: RoomType) -> None:
        result = self.result
        if result is None:
            return
        room = f"{kind.value}_1"
        ranges = result.ranges(room)
        supported = result.supported.get(room)
        total = len(result.dimensions.get(room, {}))
        with ui.dialog() as dialog, ui.card().classes("w-[32rem] max-w-full"):
            with ui.row().classes("items-center gap-1"):
                ui.label(f"{room_label(kind.value)} details").classes("text-lg font-semibold")
                _hint(
                    "Area options count each distinct area once, even if several widths and "
                    "lengths produce it. Width, length, and area ranges show separate extremes. "
                    "Use Example sizes for a set of dimensions that works together."
                )
            if supported is not None and total and result.status != "incomplete":
                ui.label(
                    f"{len(supported)} of {total} possible areas fit the current rules ({100 * len(supported) / total:.1f}%)."
                )
                ui.label(
                    "The total counts distinct areas that fit this room²s own size and shape limits."
                ).classes("lab-muted text-sm")
            if ranges and result.status == "compatible":
                ui.label(f"Possible width · {_span(ranges, 1, 10)} m")
                ui.label(f"Possible length · {_span(ranges, 2, 10)} m")
                ui.label("Each range shows its smallest and largest possible value.").classes(
                    "lab-muted text-sm"
                )
            elif result.status == "incomplete":
                ui.label("Analysis could not finish.")
            else:
                ui.label("No compatible dimensions.")
            variation = result.variation.get(kind)
            if result.status == "compatible" and variation is not None:
                ui.label(
                    f"Two rooms can differ by up to {variation.difference / 100:g} m² in one compatible arrangement."
                )
                ui.label(
                    f"Largest relative difference · {float(variation.spread):.2%} of the smaller room"
                )
            action_button("Close", role="subtle", on_click=dialog.close)
        dialog.open()

    def test_area(self, kind: RoomType) -> None:
        lock = self.locks.get(kind)
        with ui.dialog() as dialog, ui.card():
            with ui.row().classes("items-center gap-1"):
                ui.label(f"Test {room_label(kind.value)} area").classes("font-semibold")
                _hint(
                    "Enter both bounds in square metres, with up to two decimal places. "
                    "You can enter the same number twice to test one exact area. After applying, "
                    "check the sidebar for changes to this room and others."
                )
            ui.label("This temporary range applies to every room of this type.")
            minimum = ui.input(
                "Minimum area (m²)", value=str(Decimal(lock.minimum) / 100) if lock else ""
            )
            maximum = ui.input(
                "Maximum area (m²)", value=str(Decimal(lock.maximum) / 100) if lock else ""
            )
            issue = ui.label().classes("text-negative")

            def apply() -> None:
                try:
                    values = [field.value.strip() for field in (minimum, maximum)]
                    if any(
                        not re.fullmatch(r"(?:[0-9]{1,12}(?:\.[0-9]{1,2})?|\.[0-9]{1,2})", value)
                        for value in values
                    ):
                        raise ValueError
                    area = AreaRange(*(int(Decimal(value) * 100) for value in values))
                except ValueError:
                    issue.set_text(
                        "Enter positive areas with up to two decimal places, with minimum at most maximum."
                    )
                    return
                dialog.close()
                self.set_lock(kind, area)

            action_button("Apply test", role="main", on_click=apply)
            action_button("Cancel", role="subtle", on_click=dialog.close)
        dialog.open()

    def set_lock(self, room: RoomType, area: AreaRange | None) -> None:
        if area is None:
            self.locks.pop(room, None)
        else:
            self.locks[room] = area
        self.changed()


def _possible(result: Analysis | None, room: str) -> str:
    if result is None:
        return "Checking…"
    if result.status == "incomplete":
        return "Unavailable"
    return _span(result.ranges(room), 0, 100) if result.status == "compatible" else "None"


def _span(ranges: tuple[tuple[int, int], ...], index: int, scale: int) -> str:
    if not ranges:
        return "—"
    low, high = ranges[index]
    return f"{low / scale:g}–{high / scale:g}"
