"""E01A floor traffic setup and temporary, per-tab run results."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import plotly.graph_objects as go
from nicegui import app, run, ui

from fpg_lab.flows.e01a import simulate
from fpg_lab.flows.e01a_plans import plans
from fpg_lab.integrations.fpg_core.traffic_plan import import_traffic_plan
from fpg_lab.ui.components import notify_error, shell
from fpg_lab.ui.result_layout import ResultWorkspace
from fpg_lab.visualization import figures


def traffic_figure(plan: dict, result: dict | None, mode: str, selected: set[int] | None = None) -> go.Figure:
    chart = figures.floor_plan(plan, title="Floor traffic")
    chart.update_layout(uirevision=plan["name"], showlegend=False)
    if result and mode == "Heatmap":
        heat = result["heatmap"]
        chart.add_trace(go.Heatmap(x=heat["x"], y=heat["y"], z=heat["z"], zmin=0,
                                  colorscale="YlOrRd", opacity=0.75,
                                  colorbar={"title": "Trip coverage"},
                                  hovertemplate="Traffic: %{z:.2f}<extra></extra>"))
    if result and mode == "Paths":
        for i, route in enumerate(result["routes"]):
            if selected is not None and i not in selected:
                continue
            label = f"{route['source']} → {route['destination']}"
            polygon = route["footprint"]
            x, y = polygon.exterior.xy
            shade = figures.PALETTE[i % len(figures.PALETTE)]
            chart.add_trace(go.Scatter(x=list(x), y=list(y), mode="lines", fill="toself",
                                       name=label, line={"color": shade, "width": 1},
                                       opacity=0.45, hoverinfo="name"))
            points = route["points"]
            chart.add_trace(go.Scatter(x=[p[0] for p in points], y=[p[1] for p in points],
                                       mode="lines", line={"color": shade, "width": 2},
                                       showlegend=False, hoverinfo="skip"))
            chart.add_trace(go.Scatter(x=[points[0][0], points[-1][0]],
                                       y=[points[0][1], points[-1][1]], mode="markers",
                                       marker={"color": shade, "size": 9,
                                               "symbol": ["circle", "diamond"]},
                                       name=label, showlegend=False,
                                       text=["Start", "Destination"], hoverinfo="text+name"))
    if result and mode != "Floor plan":
        # Redraw walls and openings above the overlay; room fills remain beneath it.
        for room in plan["rooms"]:
            points = room["boundary"]["points"]
            closed = [*points, points[0]]
            chart.add_trace(go.Scatter(x=[p["x"] for p in closed], y=[p["y"] for p in closed],
                                       mode="lines", line={"color": "#d4d4d4", "width": 2},
                                       hoverinfo="skip", showlegend=False))
        for opening in plan["openings"]:
            chart.add_trace(go.Scatter(x=[opening["start"]["x"], opening["end"]["x"]],
                                       y=[opening["start"]["y"], opening["end"]["y"]],
                                       mode="lines", line={"width": 6, "color":
                                           "#75beff" if opening["opening_type"] == "window" else "#dcdcaa"},
                                       hoverinfo="skip", showlegend=False))
    return chart


async def main_page() -> None:
    """Choose a plan and start one tab-local traffic run."""
    shell("E01A · Floor Traffic", "Choose a plan to simulate its preset walking trips.", back_link="/")
    fixtures = plans()
    with ui.element("div").classes(
        "w-full grid grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)] gap-4 items-start"
    ):
        with ui.card().classes("w-full p-4 gap-3"):
            picker = ui.select(
                {key: plan["name"] for key, plan in fixtures.items()},
                value="compact", label="Floor plan",
            ).classes("w-full")
            with ui.expansion("Paste a floor plan").classes("w-full"):
                pasted = ui.textarea("Copied floor-plan JSON").classes("w-full")
                ui.button("Load pasted plan", on_click=lambda: load_pasted()).props("outline")
            button = ui.button("Simulate traffic").classes("w-full")
            status = ui.label("Results will be available in this browser tab only.").classes(
                "text-sm lab-muted"
            )
        with ui.card().classes("w-full min-w-0 p-3"):
            preview = ui.plotly(traffic_figure(fixtures["compact"], None, "Floor plan")).classes(
                "w-full h-[32rem]"
            )

    def update_preview() -> None:
        preview.figure = traffic_figure(fixtures[picker.value], None, "Floor plan")
        preview.update()

    def load_pasted() -> None:
        try:
            plan = import_traffic_plan(json.loads(pasted.value or ""))
            fixtures["pasted"] = plan
            picker.options = {key: value["name"] for key, value in fixtures.items()}
            picker.update()
            picker.set_value("pasted")
            update_preview()
            ui.notify("Plan loaded in this tab", type="positive")
        except Exception as exc:
            notify_error(exc)

    async def execute() -> None:
        button.disable()
        picker.disable()
        status.set_text("Calculating routes and floor coverage…")
        try:
            plan = fixtures[picker.value]
            result = await run.io_bound(simulate, plan)
            # A new run replaces any pending tab-local handoff; no database/history.
            run_id = uuid4().hex
            app.storage.tab["e01a_result"] = {
                "run_id": run_id, "plan": plan, "result": result,
            }
            ui.navigate.to(f"/experiments/e01a/runs/{run_id}")
        except Exception as exc:
            status.set_text(f"Simulation failed: {exc}")
            notify_error(exc)
        finally:
            button.enable()
            picker.enable()

    picker.on_value_change(lambda _: update_preview())
    button.on_click(execute)


async def result_page(run_id: str) -> None:
    """Inspect the latest run in this browser tab; no persisted E01A records."""
    await ui.context.client.connected()
    # Consume the one-time handoff: reloading or revisiting the result loses it,
    # exactly as the earlier single-page simulation did.
    saved = app.storage.tab.pop("e01a_result", None)
    if not saved or saved.get("run_id") != run_id:
        shell("E01A · Result unavailable", back_link="/experiments/e01a")
        ui.label("This temporary result is no longer available in this browser tab.")
        ui.link("Start another simulation", "/experiments/e01a")
        return

    plan: dict[str, Any] = saved["plan"]
    result: dict[str, Any] = saved["result"]
    selected: set[int] = set(range(len(result["routes"])))
    labels = {room["id"]: room["name"] for room in plan["rooms"]}
    workspace = ResultWorkspace(
        "E01A · Floor traffic result", back_link="/experiments/e01a",
        views=("Canvas", "Room statistics"),
    )
    with workspace.main("Canvas"):
        chart = ui.plotly(traffic_figure(plan, result, "Paths", selected)).classes(
            "lab-primary-plot"
        )
    with workspace.main("Room statistics"):
        ui.label("Room coverage · all preset trips").classes("text-base font-semibold")
        ui.table(
            columns=[
                {"name": key, "label": title, "field": key, "align": "left", "sortable": True}
                for key, title in (("room", "Room"), ("mean", "Mean"),
                                   ("peak", "Peak"), ("untouched", "Untouched"))
            ],
            rows=[
                {"room": labels[row["id"]], "mean": f"{row['mean']:.2f}",
                 "peak": f"{row['peak']:.2f}",
                 "untouched": f"{row['untouched_percent']:.1f}%"}
                for row in result["rooms"]
            ],
            row_key="room",
        ).classes("w-full")
    with workspace.controls:
        ui.label("Canvas mode").classes("font-semibold text-sm")
        mode = ui.toggle(("Floor plan", "Paths", "Heatmap"), value="Paths").props(
            "dense no-caps"
        ).classes("w-full")
        with ui.row().classes("w-full gap-1"):
            ui.button("Select all paths", on_click=lambda: select_paths(True)).props(
                "dense outline"
            )
            ui.button("Clear paths", on_click=lambda: select_paths(False)).props("dense flat")
        ui.label("10 project units / metre · 8-unit walking width").classes("lab-muted text-xs")
        ui.link("New simulation", "/experiments/e01a").classes("text-sm")
    with workspace.context("Canvas"):
        ui.label(f"{len(result['routes'])} routes · {len(result['failures'])} unreachable").classes(
            "font-medium text-sm"
        )
        routes_panel = ui.column().classes("w-full gap-1")
        failures_panel = ui.column().classes("w-full gap-1")
        if result["missing_room_types"]:
            ui.label("Missing trip room types: " + ", ".join(
                name.replace("_", " ") for name in result["missing_room_types"]
            )).classes("text-sm text-amber-300")
    with workspace.context("Room statistics"):
        ui.label("Coverage uses all preset trips, regardless of the displayed path filters.").classes(
            "text-sm lab-muted"
        )
        for room in result["rooms"]:
            ui.label(
                f"{labels[room['id']]}: {room['untouched_percent']:.1f}% untouched"
            ).classes("text-sm")

    def redraw() -> None:
        chart.figure = traffic_figure(plan, result, mode.value, selected)
        chart.update()
        routes_panel.set_visibility(mode.value == "Paths")

    def path_changed(index: int, checked: bool) -> None:
        if checked:
            selected.add(index)
        else:
            selected.discard(index)
        redraw()

    def show_routes() -> None:
        routes_panel.clear()
        with routes_panel:
            ui.label("Visible routes").classes("font-semibold text-sm")
            if not result["routes"]:
                ui.label("No matching routes. Handle failures below.").classes("lab-muted text-sm")
            for i, route in enumerate(result["routes"]):
                name = (
                    f"{labels[route['source']]} → {labels[route['destination']]}"
                    f" · {route['length']:.1f} units"
                )
                ui.checkbox(name, value=i in selected).props("dense").classes(
                    "w-full"
                ).on_value_change(
                    lambda event, index=i: path_changed(index, event.value)
                )

    def select_paths(choose_all: bool) -> None:
        selected.clear()
        if choose_all:
            selected.update(range(len(result["routes"])))
        show_routes()
        redraw()

    with failures_panel:
        for failure in result["failures"]:
            ui.label(
                f"{failure['source']} → {failure['destination']}: {failure['reason']}"
            ).classes("text-sm text-amber-300")
        if not result["routes"] and not result["failures"]:
            ui.label("No preset trips match the rooms in this plan.").classes("lab-muted")
    mode.on_value_change(lambda _: redraw())
    show_routes()
    redraw()
