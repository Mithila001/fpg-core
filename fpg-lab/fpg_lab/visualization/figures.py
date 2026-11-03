from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

import plotly.graph_objects as go

PALETTE = ("#4ec9b0", "#75beff", "#c586c0", "#dcdcaa", "#ce9178", "#9cdcfe")


def color(key: str) -> str:
    return PALETTE[int.from_bytes(sha256(key.encode()).digest()[:2]) % len(PALETTE)]


def figure(title: str, *, geometry: bool = False) -> go.Figure:
    result = go.Figure()
    result.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor="#252526",
        plot_bgcolor="#1e1e1e",
        margin=dict(l=40, r=20, t=50, b=40),
        font=dict(family="sans-serif", color="#d4d4d4"),
        uirevision=title,
        legend=dict(orientation="h"),
    )
    result.update_xaxes(gridcolor="#3c3c3c", zerolinecolor="#6b6b6b")
    result.update_yaxes(gridcolor="#3c3c3c", zerolinecolor="#6b6b6b")
    if geometry:
        result.update_xaxes(title="X · project units", zeroline=False)
        result.update_yaxes(
            title="Y · project units", scaleanchor="x", scaleratio=1, zeroline=False
        )
    return result


def candidate_map(
    candidate: Mapping[str, Any] | None, *, title: str = "Candidate map"
) -> go.Figure:
    result = figure(title, geometry=True)
    result.update_xaxes(showgrid=False)
    result.update_yaxes(showgrid=False)
    if not candidate:
        return result
    grid = candidate.get("grid") or {}
    xs, ys = grid.get("x_positions", []), grid.get("y_positions", [])
    if xs and ys:
        # Draw grid lines rather than the Cartesian product of potentially 250,000 nodes.
        x_lines, y_lines = [], []
        for x in xs:
            x_lines.extend([x, x, None])
            y_lines.extend([min(ys), max(ys), None])
        for y in ys:
            x_lines.extend([min(xs), max(xs), None])
            y_lines.extend([y, y, None])
        result.add_trace(
            go.Scatter(
                x=x_lines,
                y=y_lines,
                mode="lines",
                line=dict(color="#3c3c3c", width=1),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    for point in candidate.get("points", []):
        key = str(point.get("room_id", "hint"))
        result.add_trace(
            go.Scatter(
                x=[point["x"]],
                y=[point["y"]],
                mode="markers+text",
                name=key,
                text=[key],
                textposition="top center",
                marker=dict(size=12, color=color(key)),
                hovertemplate=f"{key}<br>X=%{{x}}<br>Y=%{{y}}<extra></extra>",
            )
        )
    return result


def floor_plan(plan: Mapping[str, Any] | None, *, title: str = "Floor plan") -> go.Figure:
    result = figure(title, geometry=True)
    if not plan:
        return result
    polygons = [("Floor boundary", plan.get("boundary"), "#d4d4d4", False)]
    polygons.extend(
        (
            room.get("name") or room["id"],
            room.get("boundary"),
            color(str(room.get("room_type", room["id"]))),
            True,
        )
        for room in plan.get("rooms", [])
    )
    for label, polygon, shade, fill in polygons:
        points = (polygon or {}).get("points", [])
        if not points:
            continue
        closed = [*points, points[0]]
        result.add_trace(
            go.Scatter(
                x=[p["x"] for p in closed],
                y=[p["y"] for p in closed],
                mode="lines",
                fill="toself" if fill else None,
                name=label,
                line=dict(color=shade, width=2),
                opacity=0.75,
                hoveron="fills+points",
                text=label,
                hoverinfo="text",
            )
        )
        if fill:
            result.add_annotation(
                x=sum(p["x"] for p in points) / len(points),
                y=sum(p["y"] for p in points) / len(points),
                text=label,
                showarrow=False,
            )
    for opening in plan.get("openings", []):
        start, end = opening["start"], opening["end"]
        result.add_trace(
            go.Scatter(
                x=[start["x"], end["x"]],
                y=[start["y"], end["y"]],
                mode="lines",
                name=f"{opening['opening_type']} · {opening['id']}",
                line=dict(
                    width=6, color="#75beff" if opening["opening_type"] == "window" else "#dcdcaa"
                ),
            )
        )
    return result


def score_history(trials: Sequence[Mapping[str, Any]], *, trial_no: int | None = None) -> go.Figure:
    result = figure("Candidate score progression")
    scored = [trial for trial in trials if trial.get("final_score") is not None]
    result.add_trace(
        go.Scatter(
            x=[t["trial_no"] for t in scored],
            y=[t["final_score"] for t in scored],
            mode="lines+markers",
            name="Score",
            line=dict(color=PALETTE[0]),
        )
    )
    result.update_xaxes(title="Trial")
    result.update_yaxes(title="Score", range=[0, 100])
    best = None
    best_scores = []
    for trial in trials:
        score = trial.get("final_score")
        if score is not None:
            best = score if best is None else max(best, score)
        best_scores.append(best)
    result.add_trace(
        go.Scatter(
            x=[t["trial_no"] for t in trials],
            y=best_scores,
            mode="lines",
            name="Best so far",
            line=dict(shape="hv"),
        )
    )
    if trial_no is not None:
        result.add_vline(x=trial_no, line_color=PALETTE[1])
    return result


def score_distribution(trials: Sequence[Mapping[str, Any]]) -> go.Figure:
    result = figure("Candidate score distribution")
    result.add_trace(
        go.Histogram(
            x=[t["final_score"] for t in trials if t.get("final_score") is not None],
            marker_color=PALETTE[0],
        )
    )
    return result


def score_breakdown(scoring: Mapping[str, Any] | None) -> go.Figure:
    result = figure("Score breakdown")
    if not scoring:
        return result
    evaluators = scoring.get("evaluator_results", [])
    result.add_trace(
        go.Bar(
            x=[e.get("evaluator_key", e.get("key", "")) for e in evaluators],
            y=[e.get("raw_score", e.get("score")) for e in evaluators],
            marker_color=PALETTE[1],
        )
    )
    result.add_trace(
        go.Bar(
            x=[e.get("evaluator_key", "") for e in evaluators],
            y=[e.get("contribution") for e in evaluators],
            name="Contribution",
            marker_color=PALETTE[0],
        )
    )
    result.data[0].name = "Raw score"
    return result


def evaluator_histories(trials: Sequence[Mapping[str, Any]]) -> dict[str, go.Figure]:
    """Keep missing/unevaluated scores as gaps; maxima belong to each evaluator."""
    ordered = sorted(trials, key=lambda trial: trial["trial_no"])
    evaluations = [
        {
            e["evaluator_key"]: e
            for e in (t.get("candidate_scoring_data") or {}).get("evaluator_results", [])
        }
        for t in ordered
    ]
    keys = dict.fromkeys(key for values in evaluations for key in values)
    results = {}
    for key in keys:
        result = figure(key.replace("_", " ").title())
        scores, maxima, details = [], [], []
        best = None
        for values in evaluations:
            evaluation = values.get(key, {})
            status = evaluation.get("status", "unavailable")
            score = evaluation.get("raw_score") if status == "completed" else None
            if score is not None:
                best = score if best is None else max(best, score)
            scores.append(score)
            maxima.append(best)
            details.append([status, evaluation.get("contribution")])
        xs = [trial["trial_no"] for trial in ordered]
        result.add_trace(
            go.Scatter(
                x=xs,
                y=scores,
                mode="lines+markers",
                name="Raw score",
                connectgaps=False,
                customdata=details,
                hovertemplate="Trial %{x}<br>Score %{y:.2f}<br>Status %{customdata[0]}"
                "<br>Contribution %{customdata[1]}<extra></extra>",
            )
        )
        result.add_trace(
            go.Scatter(
                x=xs, y=maxima, mode="lines", name="Evaluator best so far", line=dict(shape="hv")
            )
        )
        result.update_xaxes(title="Trial")
        result.update_yaxes(title="Score", range=[0, 100])
        if xs:
            result.add_vline(x=xs[0], line_color=PALETTE[1])
        results[key] = result
    return results
