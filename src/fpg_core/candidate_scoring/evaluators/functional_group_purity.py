from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from ...domain import ExecutionMode, RoomType
from ..context import ScoringContext
from ..types import EvaluationStatus, EvaluatorKey, EvaluatorResult
from .base import CandidateEvaluator
from .common import build_evaluation_data, clamp_score, setting_float

FUNCTIONAL_GROUP_PURITY_KEY = EvaluatorKey("functional_group_purity")


def _cross(a, b, c) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _hull(points):
    points = sorted(points, key=lambda p: (p.x, p.y, p.room_id))
    lower, upper = [], []
    for point in points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    return hull if len(hull) >= 3 else []


def _interrupts(point, a, b, tolerance) -> bool:
    dx, dy = b.x - a.x, b.y - a.y
    length2 = dx * dx + dy * dy
    if not length2:
        return False
    t = ((point.x - a.x) * dx + (point.y - a.y) * dy) / length2
    return (
        0 <= t <= 1
        and math.hypot(point.x - (a.x + t * dx), point.y - (a.y + t * dy)) <= tolerance
    )


class FunctionalGroupPurityEvaluator(CandidateEvaluator):
    """Score unrelated points interrupting group connections or regions."""

    @property
    def key(self) -> EvaluatorKey:
        return FUNCTIONAL_GROUP_PURITY_KEY

    def evaluate(
        self, context: ScoringContext, settings: Mapping[str, Any]
    ) -> EvaluatorResult:
        for key in (
            "direct_interruption_penalty",
            "regional_intrusion_penalty",
            "connection_tolerance_grid_steps",
        ):
            if key in settings and (
                isinstance(settings[key], bool)
                or not isinstance(settings[key], (int, float))
            ):
                raise ValueError(f"Setting '{key}' must be numeric.")
        direct = setting_float(settings, "direct_interruption_penalty", 1.0)
        regional = setting_float(settings, "regional_intrusion_penalty", 0.5)
        tolerance_steps = setting_float(
            settings, "connection_tolerance_grid_steps", 0.5
        )
        if min(direct, regional, tolerance_steps) < 0:
            raise ValueError(
                "Group purity penalties and tolerance must be nonnegative."
            )
        groups = settings.get(
            "groups", ({"name": "bedrooms", "room_types": ("bedroom",)},)
        )
        if not isinstance(groups, (list, tuple)):
            raise ValueError("groups must be a sequence.")
        points = [
            p
            for p in build_evaluation_data(context).points
            if p.room_type is not RoomType.HALLWAY
        ]
        tolerance = context.scoring_input.candidate.grid.grid_spacing * tolerance_steps
        diagnostics = []
        for group in groups:
            if (
                not isinstance(group, Mapping)
                or not isinstance(group.get("name"), str)
                or not group["name"]
                or not isinstance(group.get("room_types"), (list, tuple))
                or not group["room_types"]
            ):
                raise ValueError("Each group needs a name and room types.")
            types = {RoomType(value) for value in group["room_types"]} - {
                RoomType.HALLWAY
            }
            members = sorted(
                (p for p in points if p.room_type in types),
                key=lambda p: (p.x, p.y, p.room_id),
            )
            if len(members) < 2:
                continue
            connected, remaining, edges = [members[0]], members[1:], []
            while remaining:
                _, _, _, a, b = min(
                    (math.hypot(a.x - b.x, a.y - b.y), a.room_id, b.room_id, a, b)
                    for a in connected
                    for b in remaining
                )
                connected.append(b)
                remaining.remove(b)
                edges.append((a, b))
            hull = _hull(members)
            intrusions: list[dict[str, Any]] = []
            for point in points:
                if point in members:
                    continue
                is_direct = any(_interrupts(point, a, b, tolerance) for a, b in edges)
                is_region = bool(hull) and all(
                    _cross(hull[i], hull[(i + 1) % len(hull)], point) >= 0
                    for i in range(len(hull))
                )
                penalty = max(direct if is_direct else 0, regional if is_region else 0)
                if is_direct or is_region:
                    intrusions.append(
                        {
                            "room_id": point.room_id,
                            "x": point.x,
                            "y": point.y,
                            "kind": "direct"
                            if is_direct and direct >= regional
                            else "regional",
                            "penalty": penalty,
                        }
                    )
            score = clamp_score(
                100 * (1 - sum(i["penalty"] for i in intrusions) / len(members))
            )
            diagnostics.append(
                {
                    "name": group["name"],
                    "members": [
                        {"room_id": p.room_id, "x": p.x, "y": p.y} for p in members
                    ],
                    "edges": [
                        [{"x": a.x, "y": a.y}, {"x": b.x, "y": b.y}] for a, b in edges
                    ],
                    "hull": [{"x": p.x, "y": p.y} for p in hull],
                    "intrusions": intrusions,
                    "score": score,
                }
            )
        if not diagnostics:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            sum(d["score"] for d in diagnostics) / len(diagnostics),
            details={"groups": diagnostics}
            if context.mode is ExecutionMode.DEBUG
            else None,
        )
