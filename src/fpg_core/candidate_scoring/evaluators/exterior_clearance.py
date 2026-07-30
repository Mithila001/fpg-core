from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ...types import RoomType
from ..context import ScoringContext
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    ScoreFinding,
)
from .base import CandidateEvaluator
from .common import EvaluationPoint, build_evaluation_data, clamp_score, setting_float

EXTERIOR_CLEARANCE_KEY = EvaluatorKey("exterior_clearance")


@dataclass(frozen=True, slots=True)
class ClearanceCorridorVisualization:
    room_id: str
    room_name: str
    side: str
    bounds: tuple[float, float, float, float]
    blocker_ids: tuple[str, ...]
    selected_for_score: bool


@dataclass(frozen=True, slots=True)
class ExteriorClearanceVisualizationData:
    floor_width: float
    floor_length: float
    points: tuple[EvaluationPoint, ...]
    corridors: tuple[ClearanceCorridorVisualization, ...]


class ExteriorClearanceEvaluator(CandidateEvaluator):
    """Scores likely unobstructed front and back exterior access corridors."""

    @property
    def key(self) -> EvaluatorKey:
        return EXTERIOR_CLEARANCE_KEY

    def evaluate(
        self,
        context: ScoringContext,
        settings: Mapping[str, Any],
    ) -> EvaluatorResult:
        data = build_evaluation_data(context)
        corridor_half_width = setting_float(settings, "corridor_half_width", 10.0)
        corridor_depth = setting_float(settings, "corridor_depth", 20.0)
        penalty_per_blocker = setting_float(settings, "penalty_per_blocker", 10.0)
        hallway_back_base_score = setting_float(settings, "hallway_back_base_score", 70.0)

        components: list[tuple[str, float]] = []
        findings: list[ScoreFinding] = []
        metrics: dict[str, float] = {}
        corridors: list[ClearanceCorridorVisualization] = []

        for room_type, label in (
            (RoomType.VERANDA, "veranda_front"),
            (RoomType.GARAGE, "garage_front"),
        ):
            rooms = [point for point in data.points if point.room_type == room_type]
            if not rooms:
                continue
            room_scores = []
            for room in rooms:
                blockers = _blockers(
                    room,
                    "front",
                    data.points,
                    corridor_half_width,
                    corridor_depth,
                )
                score = clamp_score(100.0 - len(blockers) * penalty_per_blocker)
                room_scores.append(score)
                _record_blockers(findings, room, blockers, "front")
                corridors.append(
                    _clearance_visualization(
                        room,
                        "front",
                        blockers,
                        corridor_half_width,
                        corridor_depth,
                        selected_for_score=True,
                    )
                )
            component_score = sum(room_scores) / len(room_scores)
            components.append((label, component_score))
            metrics[f"component.{label}"] = component_score

        kitchens = [
            point for point in data.points if point.room_type is RoomType.KITCHEN
        ]
        hallways = [
            point for point in data.points if point.room_type is RoomType.HALLWAY
        ]
        back_candidates: list[tuple[float, EvaluationPoint, tuple[EvaluationPoint, ...]]] = []
        for room in kitchens:
            blockers = _blockers(room, "back", data.points, corridor_half_width, corridor_depth)
            back_candidates.append(
                (clamp_score(100.0 - len(blockers) * penalty_per_blocker), room, blockers)
            )
        for room in hallways:
            blockers = _blockers(room, "back", data.points, corridor_half_width, corridor_depth)
            back_candidates.append(
                (
                    clamp_score(hallway_back_base_score - len(blockers) * penalty_per_blocker),
                    room,
                    blockers,
                )
            )
        if back_candidates:
            best_score, best_room, blockers = max(back_candidates, key=lambda item: item[0])
            components.append(("back_access", best_score))
            metrics["component.back_access"] = best_score
            _record_blockers(findings, best_room, blockers, "back")
            for _, room, room_blockers in back_candidates:
                corridors.append(
                    _clearance_visualization(
                        room,
                        "back",
                        room_blockers,
                        corridor_half_width,
                        corridor_depth,
                        selected_for_score=room.room_id == best_room.room_id,
                    )
                )

        visualization = ExteriorClearanceVisualizationData(
            floor_width=data.floor_width,
            floor_length=data.floor_length,
            points=data.points,
            corridors=tuple(corridors),
        )

        if not components:
            return EvaluatorResult(
                evaluator_key=self.key,
                status=EvaluationStatus.NOT_APPLICABLE,
                score=None,
                findings=(
                    ScoreFinding(
                        code="NO_EXTERIOR_ACCESS_ROOMS",
                        message="No veranda, garage, kitchen, or hallway requires clearance scoring.",
                    ),
                ),
                visualization_payload=visualization,
            )

        metrics["evaluated_component_count"] = float(len(components))
        return EvaluatorResult(
            evaluator_key=self.key,
            status=EvaluationStatus.COMPLETED,
            score=clamp_score(sum(score for _, score in components) / len(components)),
            findings=tuple(findings),
            metrics=metrics,
            visualization_payload=visualization,
        )


def _blockers(
    room: EvaluationPoint,
    side: str,
    points: tuple[EvaluationPoint, ...],
    half_width: float,
    depth: float,
) -> tuple[EvaluationPoint, ...]:
    if side == "front":
        min_x, max_x = room.x - half_width, room.x + half_width
        min_y, max_y = room.y - depth, room.y
    elif side == "back":
        min_x, max_x = room.x - half_width, room.x + half_width
        min_y, max_y = room.y, room.y + depth
    else:
        raise ValueError(f"Unsupported clearance side: {side}")

    return tuple(
        other
        for other in points
        if other.room_id != room.room_id
        and min_x <= other.x <= max_x
        and min_y <= other.y <= max_y
    )


def _record_blockers(
    findings: list[ScoreFinding],
    room: EvaluationPoint,
    blockers: tuple[EvaluationPoint, ...],
    side: str,
) -> None:
    if not blockers:
        return
    findings.append(
        ScoreFinding(
            code="EXTERIOR_CLEARANCE_BLOCKED",
            message=(
                f"{side.title()} clearance for '{room.name}' is blocked by "
                f"{len(blockers)} candidate room point(s)."
            ),
            severity=FindingSeverity.WARNING,
            subject_ids=(room.room_id, *(blocker.room_id for blocker in blockers)),
        )
    )


def _clearance_visualization(
    room: EvaluationPoint,
    side: str,
    blockers: tuple[EvaluationPoint, ...],
    half_width: float,
    depth: float,
    *,
    selected_for_score: bool,
) -> ClearanceCorridorVisualization:
    if side == "front":
        bounds = (
            room.x - half_width,
            room.x + half_width,
            room.y - depth,
            room.y,
        )
    else:
        bounds = (
            room.x - half_width,
            room.x + half_width,
            room.y,
            room.y + depth,
        )
    return ClearanceCorridorVisualization(
        room_id=room.room_id,
        room_name=room.name,
        side=side,
        bounds=bounds,
        blocker_ids=tuple(blocker.room_id for blocker in blockers),
        selected_for_score=selected_for_score,
    )
