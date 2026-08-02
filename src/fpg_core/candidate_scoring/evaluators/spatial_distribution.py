from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from ...domain import ExecutionMode
from ..context import ScoringContext
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    ScoreFinding,
    SpatialDistributionDetails,
    SpatialDistributionPointDetails,
)
from .base import CandidateEvaluator
from .common import (
    EvaluationPoint,
    build_evaluation_data,
    clamp_score,
    setting_float,
    setting_int,
)

SPATIAL_DISTRIBUTION_KEY = EvaluatorKey("spatial_distribution")


class SpatialDistributionEvaluator(CandidateEvaluator):
    """Scores anti-clumping and whole-floor point coverage."""

    @property
    def key(self) -> EvaluatorKey:
        return SPATIAL_DISTRIBUTION_KEY

    def evaluate(
        self,
        context: ScoringContext,
        settings: Mapping[str, Any],
    ) -> EvaluatorResult:
        data = build_evaluation_data(context)
        debug_enabled = context.mode is ExecutionMode.DEBUG

        nnd_weight = setting_float(settings, "nnd_weight", 0.40)
        coverage_weight = setting_float(settings, "coverage_weight", 0.60)
        total_weight = nnd_weight + coverage_weight
        if total_weight <= 0:
            raise ValueError("nnd_weight and coverage_weight must have a positive total.")
        nnd_weight /= total_weight
        coverage_weight /= total_weight

        sensitivity = setting_float(settings, "nnd_cv_sensitivity", 8.0)
        grid_size = setting_int(settings, "grid_size", 20)
        if grid_size < 2:
            raise ValueError("grid_size must be at least 2.")
        gap_zero_score_ratio = setting_float(settings, "gap_zero_score_ratio", 1.5)
        if gap_zero_score_ratio <= 1.0:
            raise ValueError("gap_zero_score_ratio must be greater than 1.0.")

        if not data.points:
            details = (
                SpatialDistributionDetails(
                    floor_width=data.floor_width,
                    floor_length=data.floor_length,
                    points=(),
                    grid_size=grid_size,
                    nearest_distances=(),
                    ideal_point_distance=0.0,
                    theoretical_coverage_gap=0.0,
                    gap_zero_score_ratio=gap_zero_score_ratio,
                )
                if debug_enabled
                else None
            )
            return EvaluatorResult(
                evaluator_key=self.key,
                status=EvaluationStatus.COMPLETED,
                score=0.0,
                findings=(
                    ScoreFinding(
                        code="NO_CANDIDATE_POINTS",
                        message="No candidate points were available for spatial scoring.",
                        severity=FindingSeverity.ERROR,
                    ),
                ),
                metrics={"point_count": 0.0} if debug_enabled else {},
                details=details,
            )

        nnd_score, nnd_metrics = _nnd_score(
            data.points,
            data.floor_width,
            data.floor_length,
            sensitivity,
        )
        coverage_score, coverage_metrics, nearest_distances = _coverage_score(
            data.points,
            data.floor_width,
            data.floor_length,
            grid_size,
            gap_zero_score_ratio,
            collect_nearest_distances=debug_enabled,
        )
        final_score = clamp_score(
            nnd_score * nnd_weight + coverage_score * coverage_weight
        )

        findings: list[ScoreFinding] = []
        if nnd_metrics["coefficient_of_variation"] > 0.8:
            findings.append(
                ScoreFinding(
                    code="IRREGULAR_POINT_SPACING",
                    message="Candidate points show strong spacing variation or clustering.",
                    severity=FindingSeverity.WARNING,
                )
            )
        if coverage_metrics["gap_ratio"] > 1.3:
            findings.append(
                ScoreFinding(
                    code="LARGE_UNCOVERED_REGION",
                    message=(
                        "Candidate points leave a comparatively large uncovered "
                        "floor region."
                    ),
                    severity=FindingSeverity.WARNING,
                )
            )

        if debug_enabled:
            metrics = {
                "nnd_score": nnd_score,
                "coverage_score": coverage_score,
                "nnd_weight": nnd_weight,
                "coverage_weight": coverage_weight,
                "point_count": float(len(data.points)),
                **nnd_metrics,
                **coverage_metrics,
            }
            details: SpatialDistributionDetails | None = SpatialDistributionDetails(
                floor_width=data.floor_width,
                floor_length=data.floor_length,
                points=tuple(_point_details(point) for point in data.points),
                grid_size=grid_size,
                nearest_distances=nearest_distances,
                ideal_point_distance=nnd_metrics["ideal_point_distance"],
                theoretical_coverage_gap=coverage_metrics[
                    "theoretical_coverage_gap"
                ],
                gap_zero_score_ratio=gap_zero_score_ratio,
            )
        else:
            metrics = {}
            details = None

        return EvaluatorResult(
            evaluator_key=self.key,
            status=EvaluationStatus.COMPLETED,
            score=final_score,
            findings=tuple(findings),
            metrics=metrics,
            details=details,
        )


def _point_details(point: EvaluationPoint) -> SpatialDistributionPointDetails:
    return SpatialDistributionPointDetails(
        point_id=point.room_id,
        source_room_id=point.source_room_id,
        room_name=point.name,
        room_type=point.room_type,
        hint_index=point.hint_index,
        x=point.x,
        y=point.y,
    )


def _nnd_score(
    points: tuple[EvaluationPoint, ...],
    floor_width: float,
    floor_length: float,
    sensitivity: float,
) -> tuple[float, dict[str, float]]:
    anchors = (
        (0.0, 0.0),
        (floor_width, 0.0),
        (floor_width, floor_length),
        (0.0, floor_length),
        (floor_width / 2.0, 0.0),
        (floor_width / 2.0, floor_length),
        (0.0, floor_length / 2.0),
        (floor_width, floor_length / 2.0),
        (floor_width / 4.0, 0.0),
        (3.0 * floor_width / 4.0, 0.0),
        (floor_width / 4.0, floor_length),
        (3.0 * floor_width / 4.0, floor_length),
    )

    nearest: list[float] = []
    for point in points:
        room_distances = [
            math.hypot(point.x - other.x, point.y - other.y)
            for other in points
            if other.room_id != point.room_id
        ]
        boundary_distances = [math.hypot(point.x - x, point.y - y) for x, y in anchors]
        nearest.append(min((*room_distances, *boundary_distances)))

    mean_nnd = sum(nearest) / len(nearest)
    variance = sum((value - mean_nnd) ** 2 for value in nearest) / len(nearest)
    std_nnd = math.sqrt(variance)
    cv = std_nnd / max(mean_nnd, 1e-9)
    score = clamp_score(100.0 * math.exp(max(-cv * sensitivity, -10.0)))
    ideal_distance = math.sqrt((floor_width * floor_length) / len(points))
    return score, {
        "mean_nearest_distance": mean_nnd,
        "nearest_distance_std": std_nnd,
        "coefficient_of_variation": cv,
        "ideal_point_distance": ideal_distance,
    }


def _coverage_score(
    points: tuple[EvaluationPoint, ...],
    floor_width: float,
    floor_length: float,
    grid_size: int,
    gap_zero_score_ratio: float,
    *,
    collect_nearest_distances: bool,
) -> tuple[float, dict[str, float], tuple[tuple[float, ...], ...]]:
    distances: list[float] = []
    rows: list[tuple[float, ...]] = []
    for x_index in range(grid_size):
        x = floor_width * x_index / (grid_size - 1)
        column: list[float] | None = [] if collect_nearest_distances else None
        for y_index in range(grid_size):
            y = floor_length * y_index / (grid_size - 1)
            nearest = min(
                math.hypot(x - point.x, y - point.y) for point in points
            )
            distances.append(nearest)
            if column is not None:
                column.append(nearest)
        if column is not None:
            rows.append(tuple(column))

    ordered = sorted(distances)
    percentile_index = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    gap_95 = ordered[percentile_index]
    mean_gap = sum(distances) / len(distances)
    ideal_distance = math.sqrt((floor_width * floor_length) / len(points))
    theoretical_gap = ideal_distance / math.sqrt(2.0)
    gap_ratio = gap_95 / max(theoretical_gap, 1e-9)
    score = clamp_score(
        100.0 * (1.0 - (gap_ratio - 1.0) / (gap_zero_score_ratio - 1.0))
    )
    return (
        score,
        {
            "coverage_gap_95": gap_95,
            "coverage_mean_gap": mean_gap,
            "theoretical_coverage_gap": theoretical_gap,
            "gap_ratio": gap_ratio,
            "coverage_grid_size": float(grid_size),
        },
        tuple(rows),
    )
