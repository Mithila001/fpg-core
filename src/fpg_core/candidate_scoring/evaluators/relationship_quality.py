from __future__ import annotations

import heapq
import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ...domain import RoomType
from ..context import ScoringContext
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    ScoreFinding,
)
from .base import CandidateEvaluator
from .common import (
    EvaluationPoint,
    build_evaluation_data,
    clamp_score,
    distance,
    require_room_type,
    setting_float,
)

RELATIONSHIP_QUALITY_KEY = EvaluatorKey("relationship_quality")

DEFAULT_RELATION_RULES: tuple[tuple[RoomType, RoomType, float], ...] = (
    (RoomType.KITCHEN, RoomType.DINING_ROOM, 0.5),
    (RoomType.LIVING_ROOM, RoomType.KITCHEN, 1.0),
    (RoomType.LIVING_ROOM, RoomType.VERANDA, 0.5),
    (RoomType.LIVING_ROOM, RoomType.BEDROOM, 2.0),
    (RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM, 0.5),
    (RoomType.BATHROOM, RoomType.LIVING_ROOM, 0.5),
)
DEFAULT_PATH_QUERIES: tuple[tuple[RoomType, RoomType, str], ...] = (
    (RoomType.VERANDA, RoomType.LIVING_ROOM, "public"),
    (RoomType.LIVING_ROOM, RoomType.BEDROOM, "private"),
    (RoomType.LIVING_ROOM, RoomType.KITCHEN, "public"),
    (RoomType.LIVING_ROOM, RoomType.DINING_ROOM, "public"),
    (RoomType.LIVING_ROOM, RoomType.BATHROOM, "public"),
    (RoomType.BEDROOM, RoomType.BATHROOM, "private"),
    (RoomType.KITCHEN, RoomType.DINING_ROOM, "public"),
    (RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM, "private"),
)


@dataclass(frozen=True, slots=True)
class _PathCandidate:
    path: tuple[str, ...]
    cost: float
    turn_penalty: float


@dataclass(frozen=True, slots=True)
class RelationshipEdgeVisualization:
    source_id: str
    target_id: str
    distance: float
    relation_multiplier: float
    weighted_cost: float


@dataclass(frozen=True, slots=True)
class RelationshipQueryVisualization:
    start_type: str
    end_type: str
    route_type: str
    path: tuple[str, ...]
    cost: float | None
    turn_penalty: float | None
    score: float


@dataclass(frozen=True, slots=True)
class RelationshipQualityVisualizationData:
    floor_width: float
    floor_length: float
    points: tuple[EvaluationPoint, ...]
    edges: tuple[RelationshipEdgeVisualization, ...]
    queries: tuple[RelationshipQueryVisualization, ...]


class RelationshipQualityEvaluator(CandidateEvaluator):
    """Scores desired room proximity, route efficiency, and hallway separation."""

    @property
    def key(self) -> EvaluatorKey:
        return RELATIONSHIP_QUALITY_KEY

    def evaluate(
        self,
        context: ScoringContext,
        settings: Mapping[str, Any],
    ) -> EvaluatorResult:
        data = build_evaluation_data(context)
        points_by_id = {point.room_id: point for point in data.points}
        points_by_type: dict[RoomType, list[EvaluationPoint]] = defaultdict(list)
        for point in data.points:
            points_by_type[point.room_type].append(point)

        relation_rules = _read_relation_rules(settings)
        path_queries = _read_path_queries(settings)
        graph = _build_graph(data.points, points_by_type, relation_rules)
        edge_visualizations = _graph_visualizations(graph, points_by_id)
        active_queries = [
            query
            for query in path_queries
            if points_by_type.get(query[0]) and points_by_type.get(query[1])
        ]

        if not active_queries:
            return EvaluatorResult(
                evaluator_key=self.key,
                status=EvaluationStatus.NOT_APPLICABLE,
                score=None,
                findings=(
                    ScoreFinding(
                        code="NO_ACTIVE_RELATION_QUERIES",
                        message="No configured room relationship query applies to this candidate.",
                    ),
                ),
                visualization_payload=RelationshipQualityVisualizationData(
                    floor_width=data.floor_width,
                    floor_length=data.floor_length,
                    points=data.points,
                    edges=edge_visualizations,
                    queries=(),
                ),
            )

        pathing_weight = setting_float(settings, "pathing_weight", 0.75)
        hallway_privacy_weight = setting_float(settings, "hallway_privacy_weight", 0.25)
        weight_total = pathing_weight + hallway_privacy_weight
        if weight_total <= 0:
            raise ValueError("Relationship sub-score weights must have a positive total.")
        pathing_weight /= weight_total
        hallway_privacy_weight /= weight_total
        max_cost_multiplier = setting_float(settings, "max_cost_multiplier", 3.0)
        max_cost = max(1.0, math.hypot(data.floor_width, data.floor_length) * max_cost_multiplier)

        query_scores: list[float] = []
        hallway_usage: dict[str, dict[str, int]] = {
            point.room_id: {"public": 0, "private": 0}
            for point in data.points
            if point.room_type is RoomType.HALLWAY
        }
        findings: list[ScoreFinding] = []
        metrics: dict[str, float] = {}
        query_visualizations: list[RelationshipQueryVisualization] = []

        for index, (start_type, end_type, route_type) in enumerate(active_queries):
            candidates: list[_PathCandidate] = []
            for start in points_by_type[start_type]:
                for end in points_by_type[end_type]:
                    if start.room_id == end.room_id:
                        continue
                    candidate = _shortest_path(graph, points_by_id, start.room_id, end.room_id)
                    if candidate is not None:
                        candidates.append(candidate)

            if not candidates:
                query_scores.append(0.0)
                query_visualizations.append(
                    RelationshipQueryVisualization(
                        start_type=start_type.value,
                        end_type=end_type.value,
                        route_type=route_type,
                        path=(),
                        cost=None,
                        turn_penalty=None,
                        score=0.0,
                    )
                )
                findings.append(
                    ScoreFinding(
                        code="RELATION_PATH_MISSING",
                        message=(
                            f"No route was found for {start_type.value} "
                            f"to {end_type.value}."
                        ),
                        severity=FindingSeverity.WARNING,
                    )
                )
                continue

            best = min(candidates, key=lambda candidate: candidate.cost)
            base_score = clamp_score(100.0 * (1.0 - best.cost / max_cost))
            query_score = clamp_score(base_score * (1.0 - best.turn_penalty))
            query_scores.append(query_score)
            query_visualizations.append(
                RelationshipQueryVisualization(
                    start_type=start_type.value,
                    end_type=end_type.value,
                    route_type=route_type,
                    path=best.path,
                    cost=best.cost,
                    turn_penalty=best.turn_penalty,
                    score=query_score,
                )
            )
            metrics[f"query.{index}.score"] = query_score
            metrics[f"query.{index}.cost"] = best.cost
            metrics[f"query.{index}.turn_penalty"] = best.turn_penalty
            for room_id in best.path:
                if room_id in hallway_usage:
                    hallway_usage[room_id][route_type] += 1

        pathing_score = sum(query_scores) / len(query_scores)
        hallway_score = _hallway_separation_score(hallway_usage)
        total_score = clamp_score(
            pathing_score * pathing_weight + hallway_score * hallway_privacy_weight
        )
        if hallway_score < 100.0:
            findings.append(
                ScoreFinding(
                    code="HALLWAY_MIXES_PUBLIC_PRIVATE_FLOW",
                    message="One or more hallways carry a mixed public/private route pattern.",
                    severity=FindingSeverity.WARNING,
                )
            )

        metrics.update(
            {
                "active_query_count": float(len(active_queries)),
                "pathing_score": pathing_score,
                "hallway_separation_score": hallway_score,
                "graph_node_count": float(len(graph)),
                "graph_edge_count": float(sum(len(edges) for edges in graph.values()) / 2.0),
            }
        )
        return EvaluatorResult(
            evaluator_key=self.key,
            status=EvaluationStatus.COMPLETED,
            score=total_score,
            findings=tuple(findings),
            metrics=metrics,
            visualization_payload=RelationshipQualityVisualizationData(
                floor_width=data.floor_width,
                floor_length=data.floor_length,
                points=data.points,
                edges=edge_visualizations,
                queries=tuple(query_visualizations),
            ),
        )


def _read_relation_rules(
    settings: Mapping[str, Any],
) -> tuple[tuple[RoomType, RoomType, float], ...]:
    raw = settings.get("relation_rules", DEFAULT_RELATION_RULES)
    return tuple(
        (
            require_room_type(item[0], "relation_rules source room type"),
            require_room_type(item[1], "relation_rules target room type"),
            float(item[2]),
        )
        for item in raw
    )


def _read_path_queries(
    settings: Mapping[str, Any],
) -> tuple[tuple[RoomType, RoomType, str], ...]:
    raw = settings.get("path_queries", DEFAULT_PATH_QUERIES)
    return tuple(
        (
            require_room_type(item[0], "path_queries source room type"),
            require_room_type(item[1], "path_queries target room type"),
            str(item[2]),
        )
        for item in raw
    )


def _build_graph(
    points: tuple[EvaluationPoint, ...],
    points_by_type: Mapping[RoomType, list[EvaluationPoint]],
    relation_rules: tuple[tuple[RoomType, RoomType, float], ...],
) -> dict[str, dict[str, float]]:
    graph: dict[str, dict[str, float]] = {point.room_id: {} for point in points}

    for room_type_a, room_type_b, relation_cost in relation_rules:
        nodes_a = points_by_type.get(room_type_a, [])
        nodes_b = points_by_type.get(room_type_b, [])
        if (
            room_type_a is RoomType.BEDROOM
            and room_type_b is RoomType.ATTACHED_BATHROOM
        ):
            available = list(nodes_a)
            for bathroom in nodes_b:
                if not available:
                    break
                bedroom = min(available, key=lambda point: distance(point, bathroom))
                _add_edge(graph, bedroom, bathroom, relation_cost)
                available.remove(bedroom)
            continue
        for node_a in nodes_a:
            for node_b in nodes_b:
                if node_a.room_id != node_b.room_id:
                    _add_edge(graph, node_a, node_b, relation_cost)

    connectable = {
        RoomType.LIVING_ROOM,
        RoomType.BATHROOM,
        RoomType.DINING_ROOM,
        RoomType.KITCHEN,
        RoomType.BEDROOM,
        RoomType.HALLWAY,
        RoomType.GARAGE,
    }
    for hallway in points_by_type.get(RoomType.HALLWAY, []):
        for other in points:
            if other.room_id != hallway.room_id and other.room_type in connectable:
                _add_edge(graph, hallway, other, 1.0)
    return graph


def _add_edge(
    graph: dict[str, dict[str, float]],
    a: EvaluationPoint,
    b: EvaluationPoint,
    relation_cost: float,
) -> None:
    weighted_cost = distance(a, b) * (1.0 + relation_cost)
    previous = graph[a.room_id].get(b.room_id)
    if previous is None or weighted_cost < previous:
        graph[a.room_id][b.room_id] = weighted_cost
        graph[b.room_id][a.room_id] = weighted_cost


def _graph_visualizations(
    graph: Mapping[str, Mapping[str, float]],
    points_by_id: Mapping[str, EvaluationPoint],
) -> tuple[RelationshipEdgeVisualization, ...]:
    edges: list[RelationshipEdgeVisualization] = []
    seen: set[tuple[str, str]] = set()
    for source_id, neighbors in graph.items():
        for target_id, weighted_cost in neighbors.items():
            pair: tuple[str, str] = (
                (source_id, target_id)
                if source_id <= target_id
                else (target_id, source_id)
            )
            if pair in seen:
                continue
            seen.add(pair)
            direct_distance = distance(points_by_id[source_id], points_by_id[target_id])
            multiplier = (
                weighted_cost / direct_distance - 1.0
                if direct_distance > 1e-9
                else 0.0
            )
            edges.append(
                RelationshipEdgeVisualization(
                    source_id=source_id,
                    target_id=target_id,
                    distance=direct_distance,
                    relation_multiplier=multiplier,
                    weighted_cost=weighted_cost,
                )
            )
    return tuple(edges)


def _shortest_path(
    graph: Mapping[str, Mapping[str, float]],
    points_by_id: Mapping[str, EvaluationPoint],
    start: str,
    end: str,
) -> _PathCandidate | None:
    queue: list[tuple[float, str, tuple[str, ...]]] = [(0.0, start, (start,))]
    best_cost: dict[str, float] = {start: 0.0}
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node == end:
            return _PathCandidate(path, cost, _turn_penalty(path, points_by_id))
        if cost > best_cost.get(node, math.inf):
            continue
        for neighbor, edge_cost in graph.get(node, {}).items():
            new_cost = cost + edge_cost
            if new_cost < best_cost.get(neighbor, math.inf):
                best_cost[neighbor] = new_cost
                heapq.heappush(queue, (new_cost, neighbor, (*path, neighbor)))
    return None


def _turn_penalty(
    path: tuple[str, ...],
    points_by_id: Mapping[str, EvaluationPoint],
) -> float:
    if len(path) < 3:
        return 0.0
    penalties: list[float] = []
    for first_id, middle_id, last_id in zip(
        path,
        path[1:],
        path[2:],
        strict=False,
    ):
        first = points_by_id[first_id]
        middle = points_by_id[middle_id]
        last = points_by_id[last_id]
        angle1 = math.degrees(math.atan2(middle.y - first.y, middle.x - first.x))
        angle2 = math.degrees(math.atan2(last.y - middle.y, last.x - middle.x))
        turn = abs(angle2 - angle1)
        if turn > 180.0:
            turn = 360.0 - turn
        penalties.append(clamp_score((turn - 120.0) / 60.0 * 100.0) / 100.0 if turn > 120.0 else 0.0)
    return sum(penalties) / len(penalties)


def _hallway_separation_score(usage: Mapping[str, Mapping[str, int]]) -> float:
    crossed = [counts for counts in usage.values() if counts["public"] + counts["private"] > 0]
    if not crossed:
        return 100.0
    scores = []
    for counts in crossed:
        public = counts["public"]
        private = counts["private"]
        total = public + private
        scores.append(1.0 if total == 1 else abs(public - private) / total)
    return clamp_score(100.0 * sum(scores) / len(scores))
