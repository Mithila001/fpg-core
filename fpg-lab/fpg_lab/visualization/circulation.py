"""Render saved circulation diagnostics without rerunning Core in the UI."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

import plotly.graph_objects as go


def details(frame: Mapping[str, Any]) -> dict[str, Any]:
    return (frame.get("circulation_data") or {}).get("details") or {}


def paths(frame: Mapping[str, Any], *, before: bool) -> list[dict[str, Any]] | None:
    document = frame.get("circulation_data") or {}
    if before:
        passes = details(frame).get("passes") or []
        return passes[-1].get("paths", []) if passes else None
    return (document.get("lab_final_routing") or {}).get("paths")


def path_key(path: Mapping[str, Any]) -> tuple[int, str, str]:
    return path["rule_id"], path["source_point_key"], path["destination_point_key"]


def path_label(path: Mapping[str, Any], styles: Mapping[str, Mapping[str, str]]) -> str:
    def label(room_id: str) -> str:
        return styles.get(room_id, {}).get("label", room_id)

    return (
        f"{path['rule_name']} · {label(path['source_room_id'])} → "
        f"{label(path['destination_room_id'])} · {path['traffic_class']} · "
        f"{path['path_efficiency_score']:.2f}/100"
    )


def add_overlay(
    figure: go.Figure,
    frame: Mapping[str, Any],
    *,
    before: bool,
    selected: set[tuple[int, str, str]],
    styles: Mapping[str, Mapping[str, str]],
) -> None:
    available = paths(frame, before=before)
    if available is None:
        figure.add_annotation(
            text="Before-cleanup paths unavailable" if before else "After-cleanup paths unavailable",
            x=0.5, y=1, xref="paper", yref="paper", showarrow=False,
        )
    for path in available or []:
        if path_key(path) not in selected:
            continue
        public = path["traffic_class"] == "public"
        nodes = path["nodes"]
        costs = path["costs"]
        text = escape(path_label(path, styles))
        figure.add_trace(go.Scatter(
            x=[node["x"] for node in nodes], y=[node["y"] for node in nodes],
            mode="lines+markers", name=path_label(path, styles), showlegend=False,
            line=dict(color="#38bdf8" if public else "#f59e0b", width=3,
                      dash="solid" if public else "dash"),
            marker=dict(
                size=[9 if i in (0, len(nodes) - 1) else 4 for i in range(len(nodes))],
                symbol=["diamond" if i == len(nodes) - 1 else "circle" for i in range(len(nodes))],
            ),
            hovertemplate=(f"{text}<br>Steps {path['step_count']} · Turns {path['turn_count']}"
                           f"<br>Total cost {costs['total_cost']:.2f}<extra></extra>"),
        ))
    diagnostic = details(frame)
    passes = diagnostic.get("passes") or []
    traffic = (
        (passes[-1].get("hallway_traffic") or []) if before and passes
        else diagnostic.get("final_hallway_traffic") or []
    )
    final_routing = (frame.get("circulation_data") or {}).get("lab_final_routing") or {}
    if not before and "hallway_traffic" in final_routing:
        traffic = [h for h in traffic if h.get("removed")] + [
            dict(h, removed=False, removal_reason=None) for h in final_routing["hallway_traffic"]
        ]
    hallway_labels = {
        styles.get(h["room_id"], {}).get("label", h["room_id"]) for h in traffic
    }
    for trace in figure.data:
        if trace.name == "Current rooms" and trace.text:
            trace.text = ["" if label in hallway_labels else label for label in trace.text]
    for hallway in traffic:
        removed = hallway.get("removed", False)
        role = hallway["traffic_class"]
        label = styles.get(hallway["room_id"], {}).get("label", hallway["room_id"])
        reason = hallway.get("removal_reason")
        figure.add_trace(go.Scatter(
            x=[hallway["x"]], y=[hallway["y"]], mode="markers+text",
            text=[f"{label} · removed" if removed else f"{label} · {role}"],
            textposition="bottom center", showlegend=False,
            marker=dict(symbol="x" if removed else "circle-open", size=17,
                        color="#fb7185" if removed else "#e2e8f0", line=dict(width=2)),
            hovertemplate=(f"{escape(label)} · {escape(role)}"
                           f"<br>Public routes {hallway.get('public_route_count', 0)}"
                           f" · Private routes {hallway.get('private_route_count', 0)}"
                           + (f"<br>Removed: {escape(str(reason))}" if removed else "")
                           + "<extra></extra>"),
        ))
