"""Saved P01A frames and room identities; independent of NiceGUI."""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

import plotly.graph_objects as go

from fpg_lab.visualization.figures import candidate_map


def frames(trials: Sequence[dict[str, Any]], *, improvements: bool = False) -> list[dict[str, Any]]:
    result = []
    best = previous = None
    for trial in sorted(trials, key=lambda t: t["trial_no"]):
        score = trial.get("final_score")
        improved = score is not None and (best is None or score > best)
        if improved:
            best = score
        frame = dict(
            trial,
            best_score=best,
            improved=improved,
            score_change=score - previous if score is not None and previous is not None else None,
        )
        if not improvements or improved:
            result.append(frame)
        if score is not None:
            previous = score
    return result


def room_styles(rooms: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    abbreviations = {
        "living_room": "LIV",
        "kitchen": "KIT",
        "dining_room": "DIN",
        "bedroom": "BED",
        "bathroom": "BTH",
        "hallway": "HAL",
        "garage": "GAR",
        "veranda": "VER",
    }
    counts: Counter[str] = Counter()
    result = {}
    for index, room in enumerate(rooms):
        kind = str(room.get("room_type", "room"))
        prefix = abbreviations.get(kind, kind[:3].upper())
        counts[prefix] += 1
        key = str(room["id"])
        result[key] = {
            "label": f"{prefix}{counts[prefix]}",
            "name": str(room.get("name") or key),
            "color": f"hsl({index * 137.508 % 360:.3f},70%,68%)",
        }
    return result


def geometry(frame: Mapping[str, Any], cleaned: bool) -> Any:
    if cleaned:
        return ((frame.get("circulation_data") or {}).get("result") or {}).get("candidate")
    return frame.get("candidate_search_data")


def select_rooms(selected: set[str], room_id: str, checked: bool, *, single: bool) -> set[str]:
    if checked:
        return {room_id} if single else selected | {room_id}
    return selected - {room_id}


def placement_history(
    trials: Sequence[dict[str, Any]], room_id: str, *, cleaned: bool = False
) -> dict[tuple[float, float], list[int]]:
    """Index observations once; binary search supports forward and backward seeks."""
    result: dict[tuple[float, float], list[int]] = {}
    for trial in sorted(trials, key=lambda t: t["trial_no"]):
        for point in (geometry(trial, cleaned) or {}).get("points", []):
            if str(point["room_id"]) == room_id:
                result.setdefault((point["x"], point["y"]), []).append(trial["trial_no"])
    return result


def placement_counts(
    history: Mapping[tuple[float, float], list[int]], trial_no: int
) -> Counter[tuple[float, float]]:
    return Counter(
        {
            point: count
            for point, numbers in history.items()
            if (count := bisect_right(numbers, trial_no))
        }
    )


def replay_map(
    sequence: Sequence[dict[str, Any]],
    index: int,
    *,
    prepared: Mapping[str, Any],
    styles: Mapping[str, Mapping[str, str]],
    cleaned: bool = False,
    previous_frames: int = 4,
    selected_rooms: set[str] | None = None,
    heatmap_counts: Mapping[tuple[float, float], int] | None = None,
) -> go.Figure:
    grid = prepared.get("candidate_grid") or {}
    result = candidate_map({"grid": grid, "points": []}, title="Hint-map replay")
    floor = (prepared.get("generation_spec") or {}).get("floor") or {}
    boundary = (
        [
            {"x": 0, "y": 0},
            {"x": floor["width"], "y": 0},
            {"x": floor["width"], "y": floor["length"]},
            {"x": 0, "y": floor["length"]},
        ]
        if floor
        else []
    )
    if boundary:
        closed = [*boundary, boundary[0]]
        result.add_trace(
            go.Scatter(
                x=[p["x"] for p in closed],
                y=[p["y"] for p in closed],
                mode="lines",
                name="Floor boundary",
                line=dict(color="#d4d4d4", width=2),
                hoverinfo="skip",
            )
        )
    xs = [p["x"] for p in boundary] or grid.get("x_positions", [])
    ys = [p["y"] for p in boundary] or grid.get("y_positions", [])
    if xs and ys:
        padding = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.05
        result.update_xaxes(
            range=[min(xs) - padding, max(xs) + padding], autorange=False, constrain="domain"
        )
        result.update_yaxes(
            range=[min(ys) - padding, max(ys) + padding], autorange=False, constrain="domain"
        )
    if heatmap_counts is not None:
        grid_xs, grid_ys = grid.get("x_positions", []), grid.get("y_positions", [])
        total = sum(heatmap_counts.values())
        if total and grid_xs and grid_ys:

            def edges(values: list[float], limit: float) -> list[float]:
                return [
                    max(0, values[0] - (values[1] - values[0]) / 2),
                    *[(a + b) / 2 for a, b in zip(values, values[1:], strict=False)],
                    min(limit, values[-1] + (values[-1] - values[-2]) / 2),
                ]

            counts = [[heatmap_counts.get((x, y), 0) for x in grid_xs] for y in grid_ys]
            details = [
                [[x, y, 100 * heatmap_counts.get((x, y), 0) / total] for x in grid_xs]
                for y in grid_ys
            ]
            result.add_trace(
                go.Heatmap(
                    x=edges(grid_xs, floor.get("width", grid_xs[-1])),
                    y=edges(grid_ys, floor.get("length", grid_ys[-1])),
                    z=counts,
                    customdata=details,
                    zmin=0,
                    zmax=max(heatmap_counts.values()),
                    zsmooth=False,
                    colorscale=[
                        [0, "#2453c7"],
                        [0.25, "#29a7d7"],
                        [0.5, "#8dd3a8"],
                        [0.75, "#ffd166"],
                        [1, "#d73027"],
                    ],
                    colorbar=dict(title="Placements"),
                    hovertemplate="X=%{customdata[0]}<br>Y=%{customdata[1]}<br>Placements %{z}"
                    "<br>Share %{customdata[2]:.1f}%<extra></extra>",
                )
            )
            result.data = (result.data[-1], *result.data[:-1])
        else:
            result.add_annotation(
                text="No placements through this trial",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
            )
        previous_frames = 0
    current = geometry(sequence[index], cleaned)
    if current is None:
        result.add_annotation(
            text="Cleaned geometry unavailable" if cleaned else "Candidate geometry unavailable",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
        return result
    for position in range(max(0, index - previous_frames), index + 1):
        candidate = geometry(sequence[position], cleaned)
        if candidate is None:
            continue
        age = index - position
        points = [
            p
            for p in candidate.get("points", [])
            if selected_rooms is None or str(p["room_id"]) in selected_rooms
        ]
        if points:
            identities = [styles[str(p["room_id"])] for p in points]
            result.add_trace(
                go.Scatter(
                    x=[p["x"] for p in points],
                    y=[p["y"] for p in points],
                    mode="markers" if age else "markers+text",
                    name="Current rooms" if not age else f"{age} frames ago",
                    showlegend=False,
                    text=[style["label"] for style in identities] if not age else None,
                    customdata=[
                        escape(f"{style['name']} ({p['room_id']})")
                        for p, style in zip(points, identities, strict=True)
                    ],
                    textposition="top center",
                    marker=dict(
                        size=12 if not age else 9, color=[style["color"] for style in identities]
                    ),
                    opacity=1 if not age else 0.08 + 0.42 * (1 - age / (previous_frames + 1)),
                    hovertemplate="%{customdata}<br>X=%{x}<br>Y=%{y}<extra></extra>"
                    if not age
                    else None,
                    hoverinfo="skip" if age else None,
                )
            )
    return result
