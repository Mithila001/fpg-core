from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from ...domain import ExecutionMode, RoomType
from ..context import ScoringContext
from ..footprints import boundary_distance, proximity_score
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
        if "connection_tolerance_grid_steps" in settings:
            raise ValueError(
                "Replace connection_tolerance_grid_steps with connection_tolerance in project units."
            )
        for key in (
            "direct_interruption_penalty",
            "regional_intrusion_penalty",
            "connection_tolerance",
            "compactness_preferred_distance",
            "compactness_zero_score_distance",
            "purity_weight",
            "compactness_weight",
        ):
            if key in settings and (
                isinstance(settings[key], bool)
                or not isinstance(settings[key], (int, float))
            ):
                raise ValueError(f"Setting '{key}' must be numeric.")
        direct = setting_float(settings, "direct_interruption_penalty", 1.0)
        regional = setting_float(settings, "regional_intrusion_penalty", 0.5)
        tolerance = setting_float(settings, "connection_tolerance", 5.0)
        preferred = setting_float(settings, "compactness_preferred_distance", 5.0)
        zero = setting_float(settings, "compactness_zero_score_distance", 30.0)
        purity_weight = setting_float(settings, "purity_weight", 0.5)
        compactness_weight = setting_float(settings, "compactness_weight", 0.5)
        if (
            min(direct, regional, tolerance, purity_weight, compactness_weight) < 0
            or purity_weight + compactness_weight <= 0
        ):
            raise ValueError(
                "Group purity penalties and tolerance must be nonnegative."
            )
        proximity_score(0, preferred, zero)
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
        footprints = context.derived["footprints"]
        relations = context.scoring_input.specification.room_relations
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
            member_ids = {p.source_room_id for p in members}
            for point in points:
                if point in members:
                    continue
                if point.room_type is RoomType.ATTACHED_BATHROOM and any(
                    (
                        str(relation.source_room_id) == point.source_room_id
                        and any(
                            str(target) in member_ids
                            for target in relation.target_room_ids
                        )
                    )
                    or (
                        str(relation.source_room_id) in member_ids
                        and point.source_room_id
                        in {str(target) for target in relation.target_room_ids}
                    )
                    for relation in relations
                ):
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
            purity = clamp_score(
                100 * (1 - sum(i["penalty"] for i in intrusions) / len(members))
            )
            compactness = sum(
                proximity_score(
                    boundary_distance(footprints[a.room_id], footprints[b.room_id]),
                    preferred,
                    zero,
                )
                for a, b in edges
            ) / len(edges)
            score = (purity * purity_weight + compactness * compactness_weight) / (
                purity_weight + compactness_weight
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
                    "purity_score": purity,
                    "compactness_score": compactness,
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
