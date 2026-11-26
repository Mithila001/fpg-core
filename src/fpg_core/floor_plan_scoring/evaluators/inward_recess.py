from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge

from ...domain import ExecutionMode
from ..context import ScoringContext
from ..exceptions import ScoringConfigurationError
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    ScoreFinding,
    ScoreMetric,
)
from .base import FloorPlanEvaluator
from .common import require_non_negative, require_positive, typed_settings
from .recess_geometry import detect_recesses, lines, polygons

INWARD_RECESS_KEY = EvaluatorKey("inward_recess")
_Rings = tuple[tuple[tuple[float, float], ...], ...]


@dataclass(frozen=True, slots=True)
class RecessRoomBoundary:
    room_id: str
    segments: tuple[tuple[tuple[float, float], ...], ...]
    shared_length: float


@dataclass(frozen=True, slots=True)
class RecessSectionVisualization:
    polygons: tuple[_Rings, ...]
    width: float
    depth: float
    area: float
    depth_to_width_ratio: float
    level: int
    parent_indices: tuple[int, ...]
    direction: tuple[int, int]
    room_boundaries: tuple[RecessRoomBoundary, ...]
    violation_codes: tuple[str, ...]
    entrances: tuple[tuple[tuple[float, float], ...], ...] = ()


@dataclass(frozen=True, slots=True)
class RecessVisualization:
    region: RecessSectionVisualization
    entrance: tuple[tuple[float, float], ...]
    direction: tuple[int, int]
    branch_count: int
    sections: tuple[RecessSectionVisualization, ...]


@dataclass(frozen=True, slots=True)
class InwardRecessSettings:
    max_depth_to_width_ratio: float = 1.0
    max_recess_levels: int = 1
    tolerance: float = 1e-6

    def __post_init__(self) -> None:
        require_positive(
            self.max_depth_to_width_ratio, "Maximum inward-recess depth-to-width ratio"
        )
        if type(self.max_recess_levels) is not int or self.max_recess_levels < 1:
            raise ScoringConfigurationError(
                "Maximum inward-recess levels must be a positive integer."
            )
        require_non_negative(self.tolerance, "Inward-recess tolerance")


@dataclass(frozen=True, slots=True)
class InwardRecessVisualizationData:
    settings: InwardRecessSettings
    recesses: tuple[RecessVisualization, ...]


class InwardRecessEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return INWARD_RECESS_KEY

    @property
    def settings_type(self) -> type[object]:
        return InwardRecessSettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(settings, InwardRecessSettings, str(self.key))
        debug = context.mode is ExecutionMode.DEBUG
        union = context.room_union
        if union is None or union.is_empty or not union.is_valid:
            return EvaluatorResult(
                self.key,
                EvaluationStatus.COMPLETED,
                0.0,
                (
                    ScoreFinding(
                        code="ROOM_UNION_UNAVAILABLE",
                        message="Room geometry could not be combined for inward-recess analysis.",
                        severity=FindingSeverity.ERROR,
                    ),
                ),
                visualization_payload=InwardRecessVisualizationData(config, ())
                if debug
                else None,
            )

        recesses = detect_recesses(union, config.tolerance, debug=debug)
        findings: list[ScoreFinding] = []
        visuals: list[RecessVisualization] = []
        violating_count = 0
        max_ratio = 0.0
        for index, recess in enumerate(recesses):
            width = recess.entrance.length
            level = max(section.level for section in recess.sections)
            overall_codes = _violations(recess.depth, width, level, config)
            if recess.branch_count > config.max_recess_levels:
                overall_codes += ("INWARD_RECESS_TOO_MANY_BRANCHES",)
            max_ratio = max(max_ratio, recess.depth / width)
            section_visuals = []
            before = len(findings)
            if overall_codes:
                findings.extend(
                    _findings(
                        context,
                        recess.polygon,
                        recess.depth,
                        width,
                        level,
                        recess.branch_count,
                        index,
                        None,
                        overall_codes,
                        config,
                    )
                )
            for section_index, section in enumerate(recess.sections):
                max_ratio = max(max_ratio, section.depth / section.width)
                codes = _violations(section.depth, section.width, section.level, config)
                visual_codes = codes
                if (
                    len(recess.sections) == 1
                    and abs(section.width - width) <= config.tolerance
                ):
                    codes = tuple(code for code in codes if code not in overall_codes)
                if codes:
                    findings.extend(
                        _findings(
                            context,
                            section.polygon,
                            section.depth,
                            section.width,
                            section.level,
                            recess.branch_count,
                            index,
                            section_index,
                            codes,
                            config,
                        )
                    )
                if debug:
                    section_visuals.append(
                        _visual(
                            context,
                            section.polygon,
                            section.depth,
                            section.width,
                            section.level,
                            section.parents,
                            section.direction,
                            visual_codes,
                            section.entrance,
                        )
                    )
            if debug:
                visuals.append(
                    RecessVisualization(
                        _visual(
                            context,
                            recess.polygon,
                            recess.depth,
                            width,
                            level,
                            (),
                            recess.direction,
                            overall_codes,
                        ),
                        _coordinates(recess.entrance.coords),
                        recess.direction,
                        recess.branch_count,
                        tuple(section_visuals),
                    )
                )
            violating_count += int(len(findings) > before)

        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            0.0 if findings else 100.0,
            tuple(findings),
            (
                ScoreMetric("recess_count", len(recesses)),
                ScoreMetric("violating_recess_count", violating_count),
                ScoreMetric("maximum_depth_to_width_ratio", max_ratio),
            ),
            InwardRecessVisualizationData(config, tuple(visuals)) if debug else None,
        )


def _violations(
    depth: float,
    width: float,
    level: int,
    config: InwardRecessSettings,
) -> tuple[str, ...]:
    codes = []
    if depth - config.max_depth_to_width_ratio * width > config.tolerance:
        codes.append("INWARD_RECESS_DEPTH_TO_WIDTH_EXCEEDED")
    if level > config.max_recess_levels:
        codes.append("INWARD_RECESS_TOO_MANY_LEVELS")
    return tuple(codes)


def _boundaries(
    context: ScoringContext,
    shape: BaseGeometry,
) -> tuple[RecessRoomBoundary, ...]:
    result = []
    boundary = shape.boundary
    for room in sorted(context.rooms, key=lambda room: room.room_id):
        shared = boundary.intersection(room.polygon.boundary)
        parts = lines(shared)
        if not parts:
            continue
        if len(parts) > 1:
            parts = lines(linemerge(parts))
        result.append(
            RecessRoomBoundary(
                room.room_id,
                tuple(sorted(_coordinates(part.normalize().coords) for part in parts)),
                shared.length,
            )
        )
    return tuple(result)


def _coordinates(
    coords: Iterable[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    return tuple((float(x), float(y)) for x, y in coords)


def _visual(
    context: ScoringContext,
    shape: BaseGeometry,
    depth: float,
    width: float,
    level: int,
    parents: tuple[int, ...],
    direction: tuple[int, int],
    codes: tuple[str, ...],
    entrance: BaseGeometry | None = None,
) -> RecessSectionVisualization:
    rings = tuple(
        tuple(_coordinates(ring.coords) for ring in (poly.exterior, *poly.interiors))
        for poly in polygons(shape.normalize())
    )
    return RecessSectionVisualization(
        rings,
        width,
        depth,
        shape.area,
        depth / width,
        level,
        parents,
        direction,
        _boundaries(context, shape),
        codes,
        tuple(_coordinates(part.coords) for part in lines(entrance)) if entrance is not None else (),
    )


def _findings(
    context: ScoringContext,
    shape: BaseGeometry,
    depth: float,
    width: float,
    level: int,
    branch_count: int,
    recess_index: int,
    section_index: int | None,
    codes: tuple[str, ...],
    config: InwardRecessSettings,
) -> tuple[ScoreFinding, ...]:
    boundaries = _boundaries(context, shape)
    ratio = depth / width
    messages = {
        "INWARD_RECESS_DEPTH_TO_WIDTH_EXCEEDED": (
            f"depth-to-width ratio {ratio:.6g} exceeds {config.max_depth_to_width_ratio:.6g}"
        ),
        "INWARD_RECESS_TOO_MANY_LEVELS": (
            f"nesting level {level} exceeds {config.max_recess_levels}"
        ),
        "INWARD_RECESS_TOO_MANY_BRANCHES": (
            f"branch count {branch_count} exceeds {config.max_recess_levels}"
        ),
    }
    subject = f"Inward recess {recess_index}"
    metrics: tuple[ScoreMetric, ...] = (
        ScoreMetric("recess_index", recess_index),
        ScoreMetric("width", width, "units"),
        ScoreMetric("depth", depth, "units"),
        ScoreMetric("area", shape.area, "square_units"),
        ScoreMetric("depth_to_width_ratio", ratio),
        ScoreMetric("level", level),
        ScoreMetric("branch_count", branch_count),
        ScoreMetric(
            "shared_boundary_length",
            sum(item.shared_length for item in boundaries),
            "units",
        ),
    )
    if section_index is not None:
        subject += f", section {section_index}"
        metrics += (ScoreMetric("section_index", section_index),)
    return tuple(
        ScoreFinding(
            code,
            f"{subject}: {messages[code]}.",
            FindingSeverity.ERROR,
            tuple(item.room_id for item in boundaries),
            metrics,
        )
        for code in codes
    )
