"""P01A replay controls over cached, immutable saved trials."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from nicegui import events, ui

from fpg_lab.integrations.fpg_core.p01b_input import export_trial
from fpg_lab.runtime import LabRuntime, row_document
from fpg_lab.services.p01a import P01AService
from fpg_lab.ui.components import action_button, db_call, json_panel
from fpg_lab.visualization import circulation, figures, replay


async def candidate_replay(
    runtime: LabRuntime,
    item: dict[str, Any],
    *,
    canvas_area: ui.column,
    controls_area: ui.column,
    context_area: ui.column,
    charts_area: ui.column,
    on_seek: Callable[[], None],
) -> Callable[[int], None] | None:
    # ponytail: eager page-local cache targets 100–500 trials; use a sliding cache for larger replays.
    trials: list[dict[str, Any]] = []
    while True:
        page = await db_call(
            runtime,
            lambda session: [
                row_document(row)
                for row in P01AService(session).replay_trials(
                    item["id"], after=trials[-1]["trial_no"] if trials else 0
                )
            ],
        )
        trials.extend(page)
        if len(page) < 100:
            break
    if not any(t.get("candidate_search_data") for t in trials):
        with canvas_area:
            ui.label("No saved candidate geometry. Rerun P-01-A with Store debug data enabled.").classes(
                "text-amber-300"
            )
        return None
    prepared = (item.get("preprocessing_result") or {}).get("result") or {}
    rooms = list((prepared.get("generation_spec") or {}).get("rooms", []))
    known = {str(room["id"]) for room in rooms}
    # Include identities from partial/older snapshots without inventing geometry.
    for trial in trials:
        for cleaned in (False, True):
            for point in (replay.geometry(trial, cleaned) or {}).get("points", []):
                key = str(point["room_id"])
                if key not in known:
                    rooms.append({"id": key, "room_type": point.get("room_type", "room")})
                    known.add(key)
    styles = replay.room_styles(rooms)
    all_frames = replay.frames(trials)
    sequence = all_frames
    best = next((f for f in all_frames if f["trial_no"] == item["best_trial_no"]), None)

    room_ids = set(styles)
    all_path_keys = {
        circulation.path_key(path)
        for frame in all_frames
        for before in (False, True)
        for path in circulation.paths(frame, before=before) or []
    }
    selected_paths = set(all_path_keys)
    syncing_rooms = False
    with controls_area:
        ui.label("Replay").classes("font-semibold text-sm")
        with ui.row().classes("w-full items-center gap-1"):
            play = action_button("Play").props("dense")
            previous = action_button("Previous").props("dense outline")
            following = action_button("Next").props("dense outline")
            restart = action_button("Restart", role="subtle").props("dense flat")
            jump = action_button("Jump to best", role="subtle").props("dense flat")
            copy_hint = action_button(icon="content_copy", role="subtle").props(
                'dense flat aria-label="Copy cleaned hint map"'
            )
            copy_hint.tooltip("Copy selected trial's cleaned hint map")
        with ui.element("div").classes("w-full grid grid-cols-2 gap-2"):
            speed = ui.select([1, 2, 5, 10], value=2, label="Frames / second").props(
                "dense"
            ).classes("min-w-0")
            mode = ui.select(
                ["All trials", "Improvements only"], value="All trials", label="Frames"
            ).props("dense").classes("min-w-0")
            source = ui.switch("Cleaned hints", value=False).props("dense")
            onion = ui.number(
                "Previous frames", value=min(4, len(all_frames) - 1),
                min=0, max=len(all_frames) - 1, precision=0, step=1,
            ).props("dense").classes("min-w-0")
        slider = ui.slider(min=0, max=max(1, len(sequence) - 1), step=1, value=0).props(
            'label-always aria-label="Replay frame"'
        ).classes("w-full")
        summary = ui.label().classes("text-sm")
    with context_area:
        view = ui.toggle(["Hints", "Heatmap", "Circulation"], value="Hints").props("dense")
        with ui.expansion(f"Rooms · {len(room_ids)} selected").classes("w-full") as rooms_panel:
            with ui.row().classes("w-full items-center gap-2"):
                single = ui.switch("Select one", value=False).props("dense")
                all_rooms = action_button("Deselect all", role="subtle").props("dense flat")
            checks = {}
            with ui.element("div").classes("w-full grid grid-cols-2 gap-x-2 gap-y-1"):
                for key, style in styles.items():
                    checks[key] = ui.checkbox(
                        f"{style['label']} · {style['name']}", value=True
                    ).props("dense").classes("min-w-0")
                    checks[key].tooltip(key)
        heatmap = action_button("Show placement heatmap", role="subtle").props("dense flat")
        before_cleanup = ui.switch("Before cleanup", value=False).props("dense")
        route_panel = ui.column().classes("w-full gap-1")
        diagnostics = ui.column().classes("w-full min-w-0")
    with canvas_area:
        canvas = ui.plotly(figures.figure("Hint-map replay", geometry=True)).classes(
            "lab-primary-plot"
        )
    with charts_area:
        history = ui.plotly(
            figures.score_history(all_frames, trial_no=all_frames[0]["trial_no"])
        ).classes("w-full h-72")
        evaluator_plots = []
        with ui.element("div").classes("w-full grid grid-cols-2 gap-3"):
            for chart in figures.evaluator_histories(all_frames).values():
                evaluator_plots.append(ui.plotly(chart).classes("w-full min-w-0 h-72"))
    viewport: dict[str, list[float]] = {}
    heatmap_active = False
    observations: dict[tuple[str, bool], dict[tuple[float, float], list[int]]] = {}

    def remember_view(event: events.GenericEventArguments) -> None:
        if any(event.args.get(f"{axis}.autorange") for axis in ("xaxis", "yaxis")):
            viewport.clear()
        for axis in ("xaxis", "yaxis"):
            if f"{axis}.range[0]" in event.args:
                viewport[axis] = [event.args[f"{axis}.range[0]"], event.args[f"{axis}.range[1]"]]
            elif f"{axis}.range" in event.args:
                viewport[axis] = event.args[f"{axis}.range"]

    canvas.on("plotly_relayout", remember_view)

    def pause() -> None:
        timer.deactivate()
        play.set_text("Play")

    def render() -> None:
        if not sequence:
            summary.set_text("No scored improvements are available.")
            canvas.figure = figures.figure("Hint-map replay", geometry=True)
            canvas.update()
            diagnostics.clear()
            return
        index = min(int(slider.value), len(sequence) - 1)
        frame = sequence[index]
        try:
            export_trial(item, frame)
            copy_hint.enable()
        except Exception:
            copy_hint.disable()
        delta = frame["score_change"]

        def display(value: float | None) -> str:
            return f"{value:.2f}" if value is not None else "—"

        summary.set_text(
            f"Trial {frame['trial_no']} · {frame['status']} · Score {display(frame['final_score'])} · "
            f"Best so far {display(frame['best_score'])} · Change {display(delta)}"
            + (" · Selected best" if best and frame["trial_no"] == best["trial_no"] else "")
        )
        slider.props(
            f'label-value="Trial {frame["trial_no"]}" aria-valuetext="Trial {frame["trial_no"]}"'
        )
        is_circulation = view.value == "Circulation"
        rooms_panel.set_visibility(not is_circulation)
        rooms_panel.set_text(f"Rooms · {len(room_ids)} selected")
        heatmap.set_visibility(view.value == "Heatmap")
        before_cleanup.set_visibility(is_circulation)
        route_panel.set_visibility(is_circulation)
        source.set_visibility(not is_circulation)
        onion.set_enabled(not is_circulation and not heatmap_active)
        cleaned = not before_cleanup.value if is_circulation else bool(source.value)
        if is_circulation and not frame.get("circulation_data"):
            cleaned = False
        counts = None
        history_key = (next(iter(room_ids)), cleaned) if len(room_ids) == 1 else None
        if history_key is not None and history_key not in observations:
            observations[history_key] = replay.placement_history(
                all_frames, history_key[0], cleaned=cleaned
            )
        heatmap.set_enabled(history_key is not None and bool(observations.get(history_key)))
        if view.value == "Heatmap" and heatmap_active and history_key is not None:
            counts = replay.placement_counts(observations[history_key], frame["trial_no"])
        canvas.figure = replay.replay_map(
            sequence,
            index,
            prepared=prepared,
            styles=styles,
            cleaned=cleaned,
            previous_frames=0
            if is_circulation
            else max(0, min(int(onion.value or 0), len(all_frames) - 1)),
            selected_rooms=None if is_circulation else room_ids,
            heatmap_counts=counts,
        )
        route_panel.clear()
        available = circulation.paths(frame, before=bool(before_cleanup.value))
        if is_circulation:
            circulation.add_overlay(
                canvas.figure,
                frame,
                before=bool(before_cleanup.value),
                selected=selected_paths,
                styles=styles,
            )
            with route_panel:
                ui.label("Public: solid blue · Private: dashed amber").classes("text-xs lab-muted")
                ui.label("Source: circle · Destination: diamond · Removed hallway: cross").classes(
                    "text-xs lab-muted"
                )
                if available is None:
                    routing = (frame.get("circulation_data") or {}).get("lab_final_routing") or {}
                    ui.label(
                        routing.get("error")
                        or (
                            "No saved paths. Older runs can show Before cleanup; "
                            "new debug runs record the after-cleanup diagnostic reroute."
                        )
                    ).classes("text-sm text-amber-300")
                else:
                    visible_keys = {circulation.path_key(path) for path in available}
                    absent = len(selected_paths - visible_keys)
                    if absent:
                        ui.label(f"{absent} selected paths absent in this trial").classes(
                            "text-xs lab-muted"
                        )
                    with ui.row():
                        action_button("Select all", role="subtle", on_click=lambda: select_paths(True)).props(
                            "dense flat"
                        )
                        action_button("Deselect all", role="subtle", on_click=lambda: select_paths(False)).props(
                            "dense flat"
                        )
                    if not available:
                        ui.label("No paths in this trial.").classes("text-sm lab-muted")
                    for path in available:
                        key = circulation.path_key(path)
                        ui.checkbox(
                            circulation.path_label(path, styles),
                            value=key in selected_paths,
                        ).props("dense").on_value_change(
                            lambda event, key=key: choose_path(key, bool(event.value))
                        )
        for axis, bounds in viewport.items():
            canvas.figure.update_layout({axis: {"range": bounds, "autorange": False}})
        canvas.update()
        history.figure.update_shapes(x0=frame["trial_no"], x1=frame["trial_no"])
        history.update()
        for plot in evaluator_plots:
            plot.figure.update_shapes(x0=frame["trial_no"], x1=frame["trial_no"])
            plot.update()
        diagnostics.clear()
        with diagnostics:
            if is_circulation:
                if not before_cleanup.value and available is not None:
                    ui.label("After cleanup · Lab diagnostic reroute").classes("text-sm lab-muted")
                selected = [p for p in available or [] if circulation.path_key(p) in selected_paths]
                if selected:
                    with ui.expansion("Path scores and costs").classes("w-full"):
                        for path in selected:
                            ui.label(circulation.path_label(path, styles)).classes("font-medium")
                            costs = path["costs"]
                            ui.label(
                                f"Steps {path['step_count']} · Detour {path['detour_step_count']} · "
                                f"Turns {path['turn_count']} · Reference cost "
                                f"{path['manhattan_reference_cost']:.2f}"
                            ).classes("text-sm")
                            ui.label(
                                " · ".join(
                                    f"{name.replace('_', ' ')} {value:.2f}"
                                    for name, value in costs.items()
                                )
                            ).classes("text-sm")
                efficiency = (
                    (frame.get("circulation_data") or {}).get("lab_final_routing") or {}
                ).get("efficiency_score")
                if before_cleanup.value and available:
                    total_weight = sum(p["importance_weight"] for p in available)
                    efficiency = (
                        sum(p["path_efficiency_score"] * p["importance_weight"] for p in available)
                        / total_weight
                        if total_weight
                        else None
                    )
                if efficiency is not None:
                    ui.label(f"Circulation efficiency for this view: {efficiency:.2f}/100").classes(
                        "text-sm"
                    )
            if frame.get("error_data"):
                ui.label(
                    str(frame["error_data"].get("message", "Trial failed or was rejected"))
                ).classes("text-amber-300")
                json_panel("Trial error", frame["error_data"])
            if frame.get("candidate_scoring_data"):
                json_panel("Evaluator details", frame["candidate_scoring_data"])
        previous.set_enabled(index > 0)
        following.set_enabled(index < len(sequence) - 1)
        if index == len(sequence) - 1:
            pause()

    def seek(index: int) -> None:
        pause()
        target = max(0, min(index, len(sequence) - 1))
        if target == slider.value:
            render()
        else:
            slider.set_value(target)

    def tick() -> None:
        if int(slider.value) < len(sequence) - 1:
            slider.set_value(int(slider.value) + 1)
        else:
            pause()

    def toggle() -> None:
        if timer.active:
            pause()
        elif sequence:
            if int(slider.value) >= len(sequence) - 1:
                seek(0)
            play.set_text("Pause")
            timer.activate()

    def change_mode() -> None:
        nonlocal sequence
        pause()
        sequence = replay.frames(trials, improvements=mode.value == "Improvements only")
        slider._props["max"] = max(1, len(sequence) - 1)
        slider.update()
        for control in (play, previous, following, restart, slider):
            control.set_enabled(bool(sequence))
        seek(0)

    def filters_changed() -> None:
        nonlocal heatmap_active
        pause()
        if len(room_ids) != 1 or not replay.placement_history(
            all_frames, next(iter(room_ids)), cleaned=bool(source.value)
        ):
            heatmap_active = False
        heatmap.set_text("Show motion" if heatmap_active else "Show placement heatmap")
        onion.set_enabled(not heatmap_active)
        render()

    def sync_rooms() -> None:
        nonlocal syncing_rooms
        syncing_rooms = True
        try:
            for key, checkbox in checks.items():
                checkbox.set_value(key in room_ids)
        finally:
            syncing_rooms = False
        all_rooms.set_text("Deselect all" if len(room_ids) == len(styles) else "Select all")
        filters_changed()

    def choose_room(key: str, checked: bool) -> None:
        nonlocal room_ids
        if syncing_rooms:
            return
        room_ids = replay.select_rooms(room_ids, key, checked, single=single.value)
        sync_rooms()

    def change_single() -> None:
        if single.value and len(room_ids) > 1:
            keep = next(key for key in styles if key in room_ids)
            room_ids.intersection_update({keep})
        sync_rooms()

    def toggle_all() -> None:
        nonlocal room_ids
        choose_all = len(room_ids) != len(styles)
        if choose_all:
            single.set_value(False)
        room_ids = set(styles) if choose_all else set()
        sync_rooms()

    def toggle_heatmap() -> None:
        nonlocal heatmap_active
        pause()
        heatmap_active = not heatmap_active
        filters_changed()

    def choose_path(key: tuple[int, str, str], checked: bool) -> None:
        if checked:
            selected_paths.add(key)
        else:
            selected_paths.discard(key)
        pause()
        render()

    def select_paths(checked: bool) -> None:
        if checked:
            selected_paths.update(all_path_keys)
        else:
            selected_paths.clear()
        pause()
        render()

    def change_view() -> None:
        nonlocal heatmap_active
        heatmap_active = False
        filters_changed()

    def seek_trial(trial_no: int) -> None:
        pause()
        if not any(f["trial_no"] == trial_no for f in sequence):
            mode.set_value("All trials")
        seek(next(i for i, f in enumerate(sequence) if f["trial_no"] == trial_no))
        on_seek()

    timer = ui.timer(0.5, tick, active=False, immediate=False)
    ui.context.client.on_disconnect(pause)
    ui.context.client.on_delete(lambda: timer.cancel())
    play.on_click(toggle)
    previous.on_click(lambda: seek(int(slider.value) - 1))
    following.on_click(lambda: seek(int(slider.value) + 1))
    restart.on_click(lambda: seek(0))
    jump.set_enabled(best is not None)
    jump.on_click(
        lambda: seek(
            next(i for i, f in enumerate(sequence) if best and f["trial_no"] == best["trial_no"])
        )
    )

    def copy_selected() -> None:
        document = export_trial(item, sequence[int(slider.value)])
        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(json.dumps(document))})")
        ui.notify("Cleaned hint map copied")

    copy_hint.on_click(copy_selected)
    speed.on_value_change(lambda: setattr(timer, "interval", 1 / speed.value))
    slider.on_value_change(render)
    slider.on("pan", pause)
    mode.on_value_change(change_mode)
    source.on_value_change(filters_changed)
    view.on_value_change(change_view)
    before_cleanup.on_value_change(filters_changed)
    single.on_value_change(change_single)
    all_rooms.on_click(toggle_all)
    for key, checkbox in checks.items():
        checkbox.on_value_change(lambda event, key=key: choose_room(key, bool(event.value)))
    heatmap.on_click(toggle_heatmap)
    onion.on_value_change(render)
    render()
    return seek_trial
