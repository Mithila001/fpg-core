"""Floor-traffic page; all results belong to the current browser session."""
from __future__ import annotations

import json
from typing import Any

import plotly.graph_objects as go
from nicegui import run, ui

from fpg_lab.flows.e01a import simulate
from fpg_lab.flows.e01a_plans import plans
from fpg_lab.integrations.fpg_core.traffic_plan import import_traffic_plan
from fpg_lab.ui.components import notify_error, shell
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
    shell("E01A · Floor Traffic", "Explore preset walking routes and their accumulated floor coverage.",
          back_link="/")
    fixtures = plans()
    state: dict[str, Any] = {"result": None, "mode": "Floor plan", "selected": set(), "syncing": False}
    with ui.element("div").classes(
        "w-full grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)] gap-5 items-start"
    ):
        with ui.card().classes("w-full min-w-0 p-3"):
            chart = ui.plotly(traffic_figure(fixtures["compact"], None, "Floor plan")).classes(
                "w-full h-[42rem] min-w-0")
        with ui.card().classes("w-full min-w-0 p-5 gap-4"):
            ui.label("Floor traffic").classes("text-lg font-semibold")
            picker = ui.select({k: p["name"] for k, p in fixtures.items()}, value="compact",
                               label="Floor plan").classes("w-full")
            with ui.expansion("Paste floor plan").classes("w-full"):
                pasted = ui.textarea("Paste copied floor-plan JSON").classes("w-full")
                ui.button("Load pasted plan", on_click=lambda: load_pasted()).props("outline")
            button = ui.button("Simulate traffic").classes("w-full")
            status = ui.label("Select a plan and simulate to see paths and traffic.").classes("lab-muted text-sm")
            ui.label("View mode").classes("font-semibold")
            with ui.row().classes("w-full gap-x-2 gap-y-0"):
                mode_checks = {name: ui.checkbox(name, value=name == "Floor plan").props("dense")
                               for name in ("Floor plan", "Paths", "Heatmap")}
            routes_panel = ui.column().classes("w-full gap-1")
            details = ui.column().classes("w-full gap-2")

    def redraw() -> None:
        chart.figure = traffic_figure(fixtures[picker.value], state["result"], state["mode"], state["selected"])
        chart.update()
        routes_panel.set_visibility(state["mode"] == "Paths")

    def set_mode(name: str) -> None:
        state["syncing"] = True
        state["mode"] = name
        for key, checkbox in mode_checks.items():
            checkbox.value = key == name
        state["syncing"] = False
        redraw()

    def mode_changed(name: str, value: bool) -> None:
        if state["syncing"]:
            return
        if value:
            set_mode(name)
        elif state["mode"] == name:
            state["syncing"] = True
            mode_checks[name].value = True
            state["syncing"] = False

    def show_routes() -> None:
        routes_panel.clear()
        result = state["result"]
        with routes_panel:
            ui.label("Paths").classes("font-semibold")
            if result is None:
                ui.label("Run the simulation to choose paths.").classes("lab-muted text-sm")
                return
            labels = {r["id"]: r["name"] for r in fixtures[picker.value]["rooms"]}
            with ui.row().classes("gap-2"):
                ui.button("Select all", on_click=lambda: select_paths(True)).props("dense flat")
                ui.button("Clear all", on_click=lambda: select_paths(False)).props("dense flat")
            for i, route in enumerate(result["routes"]):
                label = f"{labels[route['source']]} → {labels[route['destination']]} · {route['length']:.1f} units"
                check = ui.checkbox(label, value=i in state["selected"]).props("dense").classes("w-full")
                check.on_value_change(lambda event, index=i: path_changed(index, event.value))
            for failure in result["failures"]:
                ui.label(f"{failure['source']} → {failure['destination']}: {failure['reason']}").classes("text-orange-300")

    def path_changed(index: int, checked: bool) -> None:
        if checked:
            state["selected"].add(index)
        else:
            state["selected"].discard(index)
        redraw()

    def select_paths(all_paths: bool) -> None:
        result = state["result"]
        state["selected"] = set(range(len(result["routes"]))) if all_paths and result else set()
        show_routes()
        redraw()

    def load_pasted() -> None:
        try:
            plan = import_traffic_plan(json.loads(pasted.value or ""))
            fixtures["pasted"] = plan
            picker.options = {key: value["name"] for key, value in fixtures.items()}
            picker.update()
            if picker.value == "pasted":
                changed_plan()
            else:
                picker.value = "pasted"
            ui.notify("Floor plan loaded for this session", type="positive")
        except Exception as exc:
            notify_error(exc)

    def changed_plan() -> None:
        state["result"] = None
        state["selected"] = set()
        details.clear()
        status.set_text("Select a plan and simulate to see paths and traffic.")
        show_routes()
        set_mode("Floor plan")

    async def execute() -> None:
        button.disable()
        picker.disable()
        status.set_text("Calculating routes and traffic…")
        try:
            result = await run.io_bound(simulate, fixtures[picker.value])
            state["result"] = result
            state["selected"] = set(range(len(result["routes"])))
            status.set_text(f"{len(result['routes'])} routes calculated · {len(result['failures'])} unreachable · "
                            "10 units per metre · 8-unit walking width")
            details.clear()
            with details:
                if result["missing_room_types"]:
                    names = ", ".join(name.replace("_", " ") for name in result["missing_room_types"])
                    ui.label(f"Trips requiring these missing room types were skipped: {names}.").classes("lab-muted text-sm")
                if not result["routes"] and not result["failures"]:
                    ui.label("No preset trip pairs match the rooms in this plan.").classes("lab-muted")
                ui.label("Room coverage · all preset trips").classes("font-semibold")
                labels = {r["id"]: r["name"] for r in fixtures[picker.value]["rooms"]}
                ui.table(columns=[{"name": k, "label": title, "field": k, "align": "left"}
                                  for k, title in (("room", "Room"), ("mean", "Mean"),
                                                   ("peak", "Peak"), ("untouched", "Untouched"))],
                         rows=[{"room": labels[r["id"]], "mean": f"{r['mean']:.2f}",
                                "peak": f"{r['peak']:.2f}", "untouched": f"{r['untouched_percent']:.1f}%"}
                               for r in result["rooms"]], row_key="room").classes("w-full")
            show_routes()
            set_mode("Paths")
        except Exception as exc:
            state["result"] = None
            state["selected"] = set()
            details.clear()
            show_routes()
            status.set_text(f"Simulation failed: {exc}")
            redraw()
            notify_error(exc)
        finally:
            button.enable()
            picker.enable()

    for name, checkbox in mode_checks.items():
        checkbox.on_value_change(lambda event, view=name: mode_changed(view, event.value))
    picker.on_value_change(lambda _: changed_plan())
    button.on_click(execute)
    show_routes()
    routes_panel.set_visibility(False)
