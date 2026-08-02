from __future__ import annotations

import heapq
import itertools
import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

from ...domain import (
    CirculationGridNode,
    CirculationRouteRule,
    CirculationTrafficClass,
    DestinationSelection,
    ExecutionMode,
    HallwayTrafficClass,
    RoomType,
    RouteCostBreakdown,
)
from ..config import RelationshipQualityConfig
from ..context import ScoringContext
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    RelationshipPathDetails,
    RelationshipQualityDetails,
    RelationshipRouteFailureDetails,
    ScoreFinding,
)
from .base import CandidateEvaluator
from .common import EvaluationData, EvaluationPoint, build_evaluation_data

RELATIONSHIP_QUALITY_KEY = EvaluatorKey("relationship_quality")

_MAX_GRID_NODE_COUNT = 250_000
_NONE_DIRECTION = -1
_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (1, 0),
    (0, 1),
    (-1, 0),
    (0, -1),
)

_Node: TypeAlias = tuple[int, int]
_State: TypeAlias = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class _IndexedPoint:
    point: EvaluationPoint
    x_index: int
    y_index: int


@dataclass(frozen=True, slots=True)
class _ValidatedRouting:
    data: EvaluationData
    config: RelationshipQualityConfig
    x_node_count: int
    y_node_count: int
    indexed_points: tuple[_IndexedPoint, ...]
    occupied_nodes: dict[_Node, _IndexedPoint]

    @property
    def grid_node_count(self) -> int:
        return self.x_node_count * self.y_node_count


@dataclass(frozen=True, slots=True)
class _ResolvedRoute:
    rule: CirculationRouteRule
    source: _IndexedPoint
    destination: _IndexedPoint
    nodes: tuple[_Node, ...]
    movement_cost: float
    perimeter_bias_cost: float
    turn_cost: float
    total_cost: float
    turn_count: int
    manhattan_reference_cost: float

    @property
    def step_count(self) -> int:
        return max(0, len(self.nodes) - 1)

    @property
    def manhattan_step_count(self) -> int:
        return abs(self.source.x_index - self.destination.x_index) + abs(
            self.source.y_index - self.destination.y_index
        )

    @property
    def path_efficiency_score(self) -> float:
        if self.total_cost <= 0:
            return 100.0
        return _clamp_score(
            100.0 * self.manhattan_reference_cost / self.total_cost
        )


@dataclass(frozen=True, slots=True)
class _RouteFailure:
    rule: CirculationRouteRule
    source: _IndexedPoint
    destination: _IndexedPoint | None
    message: str


class RelationshipQualityEvaluator(CandidateEvaluator):
    """Scores one-pass grid-route efficiency between configured room types."""

    @property
    def key(self) -> EvaluatorKey:
        return RELATIONSHIP_QUALITY_KEY

    def evaluate(
        self,
        context: ScoringContext,
        settings: Mapping[str, Any],
    ) -> EvaluatorResult:
        routing_config = _read_routing_config(settings)
        data = build_evaluation_data(context)
        validated = _validate_routing(data, routing_config)
        active_rules = _active_rules(validated)

        if not active_rules:
            return EvaluatorResult(
                evaluator_key=self.key,
                status=EvaluationStatus.NOT_APPLICABLE,
                score=None,
                findings=(
                    ScoreFinding(
                        code="NO_ACTIVE_RELATION_ROUTES",
                        message=(
                            "No configured relationship route has both endpoint "
                            "room types in this candidate."
                        ),
                    ),
                ),
            )

        hallway_classes = {
            (str(item.room_id), item.hint_index): item.traffic_class
            for item in context.scoring_input.hallway_classifications
        }
        routes, failures, total_expected_weight = _resolve_rules(
            validated,
            active_rules,
            hallway_classes,
        )
        score = _weighted_efficiency_score(routes, total_expected_weight)
        findings = tuple(_failure_finding(failure) for failure in failures)

        if context.mode is ExecutionMode.DEBUG:
            metrics = _debug_metrics(
                active_rules=active_rules,
                routes=routes,
                failures=failures,
                score=score,
            )
            details: RelationshipQualityDetails | None = _debug_details(
                validated,
                routes,
                failures,
                score,
            )
        else:
            metrics = {}
            details = None

        return EvaluatorResult(
            evaluator_key=self.key,
            status=EvaluationStatus.COMPLETED,
            score=score,
            findings=findings,
            metrics=metrics,
            details=details,
        )


def _read_routing_config(
    settings: Mapping[str, Any],
) -> RelationshipQualityConfig:
    config = settings.get("routing_config")
    if not isinstance(config, RelationshipQualityConfig):
        raise ValueError(
            "Relationship quality requires settings['routing_config'] as a "
            "RelationshipQualityConfig instance."
        )
    return config


def _validate_routing(
    data: EvaluationData,
    config: RelationshipQualityConfig,
) -> _ValidatedRouting:
    grid = config.grid
    if not math.isclose(
        grid.width,
        data.floor_width,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "Relationship routing grid width must match the specification floor width."
        )
    if not math.isclose(
        grid.length,
        data.floor_length,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "Relationship routing grid length must match the specification floor length."
        )

    x_node_count = _axis_node_count(grid.width, grid.scale, "width")
    y_node_count = _axis_node_count(grid.length, grid.scale, "length")
    grid_node_count = x_node_count * y_node_count
    if grid_node_count > _MAX_GRID_NODE_COUNT:
        raise ValueError(
            "Relationship routing grid exceeds the 250,000-node safety limit."
        )

    indexed_points: list[_IndexedPoint] = []
    occupied_nodes: dict[_Node, _IndexedPoint] = {}
    for point in data.points:
        x_index = _coordinate_index(
            coordinate=point.x,
            origin=grid.origin_x,
            scale=grid.scale,
            node_count=x_node_count,
            axis_name="x",
            point_id=point.room_id,
        )
        y_index = _coordinate_index(
            coordinate=point.y,
            origin=grid.origin_y,
            scale=grid.scale,
            node_count=y_node_count,
            axis_name="y",
            point_id=point.room_id,
        )
        indexed = _IndexedPoint(
            point=point,
            x_index=x_index,
            y_index=y_index,
        )
        node = (x_index, y_index)
        existing = occupied_nodes.get(node)
        if existing is not None:
            raise ValueError(
                "Candidate hint points cannot overlap on the relationship grid: "
                f"'{existing.point.room_id}' and '{point.room_id}'."
            )
        occupied_nodes[node] = indexed
        indexed_points.append(indexed)

    return _ValidatedRouting(
        data=data,
        config=config,
        x_node_count=x_node_count,
        y_node_count=y_node_count,
        indexed_points=tuple(indexed_points),
        occupied_nodes=occupied_nodes,
    )


def _axis_node_count(extent: float, scale: float, axis_name: str) -> int:
    raw_steps = extent / scale
    steps = round(raw_steps)
    tolerance = max(1e-9, abs(raw_steps) * 1e-9)
    if not math.isclose(raw_steps, steps, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(
            f"Relationship grid {axis_name} extent must be an exact multiple "
            "of grid scale."
        )
    return int(steps) + 1


def _coordinate_index(
    *,
    coordinate: float,
    origin: float,
    scale: float,
    node_count: int,
    axis_name: str,
    point_id: str,
) -> int:
    raw_index = (coordinate - origin) / scale
    index = round(raw_index)
    tolerance = max(1e-8, abs(raw_index) * 1e-9)
    if not math.isclose(raw_index, index, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(
            f"Candidate point '{point_id}' {axis_name} coordinate does not "
            "align with the relationship grid."
        )
    if index < 0 or index >= node_count:
        raise ValueError(
            f"Candidate point '{point_id}' is outside the relationship grid "
            f"on the {axis_name} axis."
        )
    return int(index)


def _active_rules(
    validated: _ValidatedRouting,
) -> tuple[CirculationRouteRule, ...]:
    present_types = {point.point.room_type for point in validated.indexed_points}
    return tuple(
        rule
        for rule in validated.config.route_rules
        if rule.source_room_type in present_types
        and rule.destination_room_type in present_types
    )


def _resolve_rules(
    validated: _ValidatedRouting,
    rules: tuple[CirculationRouteRule, ...],
    hallway_classes: Mapping[tuple[str, int], HallwayTrafficClass],
) -> tuple[tuple[_ResolvedRoute, ...], tuple[_RouteFailure, ...], float]:
    points_by_type: dict[RoomType, list[_IndexedPoint]] = defaultdict(list)
    for point in validated.indexed_points:
        points_by_type[point.point.room_type].append(point)

    routes: list[_ResolvedRoute] = []
    failures: list[_RouteFailure] = []
    total_expected_weight = 0.0

    for rule in rules:
        sources = points_by_type[rule.source_room_type]
        destinations = points_by_type[rule.destination_room_type]

        for source in sources:
            candidates: list[_ResolvedRoute] = []
            for destination in destinations:
                route = _route_between(
                    validated=validated,
                    rule=rule,
                    source=source,
                    destination=destination,
                    hallway_classes=hallway_classes,
                )
                if rule.destination_selection is DestinationSelection.ALL_MATCHING:
                    total_expected_weight += rule.importance_weight
                    if route is None:
                        failures.append(
                            _RouteFailure(
                                rule=rule,
                                source=source,
                                destination=destination,
                                message=_missing_path_message(
                                    rule,
                                    source,
                                    destination,
                                ),
                            )
                        )
                    else:
                        routes.append(route)
                elif route is not None:
                    candidates.append(route)

            if rule.destination_selection is DestinationSelection.ALL_MATCHING:
                continue

            total_expected_weight += rule.importance_weight
            if not candidates:
                failures.append(
                    _RouteFailure(
                        rule=rule,
                        source=source,
                        destination=None,
                        message=(
                            f"Route rule {rule.id} ('{rule.name}') could not reach "
                            f"any {rule.destination_room_type.value} point from "
                            f"'{source.point.room_id}'."
                        ),
                    )
                )
                continue

            routes.append(
                min(
                    candidates,
                    key=lambda route: (
                        route.total_cost,
                        route.turn_count,
                        route.step_count,
                        route.destination.point.room_id,
                    ),
                )
            )

    return tuple(routes), tuple(failures), total_expected_weight


def _route_between(
    *,
    validated: _ValidatedRouting,
    rule: CirculationRouteRule,
    source: _IndexedPoint,
    destination: _IndexedPoint,
    hallway_classes: Mapping[tuple[str, int], HallwayTrafficClass],
) -> _ResolvedRoute | None:
    start = (source.x_index, source.y_index)
    target = (destination.x_index, destination.y_index)
    start_state: _State = (start[0], start[1], _NONE_DIRECTION)

    distances: dict[_State, float] = {start_state: 0.0}
    tie_values: dict[_State, tuple[int, int]] = {start_state: (0, 0)}
    predecessors: dict[_State, _State] = {}
    serial = itertools.count()
    queue: list[tuple[float, int, int, int, _State]] = [
        (0.0, 0, 0, next(serial), start_state)
    ]
    final_state: _State | None = None

    while queue:
        cost, turns, steps, _, state = heapq.heappop(queue)
        known_cost = distances.get(state)
        if known_cost is None or not math.isclose(
            cost,
            known_cost,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            continue
        if tie_values[state] != (turns, steps):
            continue

        node = (state[0], state[1])
        if node == target:
            final_state = state
            break

        previous_direction = state[2]
        for direction, (dx, dy) in enumerate(_DIRECTIONS):
            next_node = (node[0] + dx, node[1] + dy)
            if not _inside_grid(validated, next_node):
                continue
            if not _can_enter(
                validated=validated,
                node=next_node,
                target=target,
                rule=rule,
                hallway_classes=hallway_classes,
            ):
                continue

            movement_cost, perimeter_cost, turn_cost = _transition_costs(
                validated=validated,
                node=next_node,
                previous_node=node,
                direction=direction,
                previous_direction=previous_direction,
            )
            new_cost = cost + movement_cost + perimeter_cost + turn_cost
            new_turns = turns + int(
                previous_direction != _NONE_DIRECTION
                and previous_direction != direction
            )
            new_steps = steps + 1
            next_state = (next_node[0], next_node[1], direction)
            existing_cost = distances.get(next_state)
            existing_tie = tie_values.get(next_state)
            candidate_tie = (new_turns, new_steps)

            if existing_cost is not None:
                if new_cost > existing_cost + 1e-12:
                    continue
                if (
                    math.isclose(
                        new_cost,
                        existing_cost,
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    )
                    and existing_tie is not None
                    and candidate_tie >= existing_tie
                ):
                    continue

            distances[next_state] = new_cost
            tie_values[next_state] = candidate_tie
            predecessors[next_state] = state
            heapq.heappush(
                queue,
                (
                    new_cost,
                    new_turns,
                    new_steps,
                    next(serial),
                    next_state,
                ),
            )

    if final_state is None:
        return None

    states = _reconstruct_states(start_state, final_state, predecessors)
    nodes = tuple((state[0], state[1]) for state in states)
    movement_cost = 0.0
    perimeter_bias_cost = 0.0
    turn_cost = 0.0
    for previous_state, state in zip(states, states[1:], strict=False):
        transition = _transition_costs(
            validated=validated,
            node=(state[0], state[1]),
            previous_node=(previous_state[0], previous_state[1]),
            direction=state[2],
            previous_direction=previous_state[2],
        )
        movement_cost += transition[0]
        perimeter_bias_cost += transition[1]
        turn_cost += transition[2]

    costs = validated.config.costs
    manhattan_steps = abs(source.x_index - destination.x_index) + abs(
        source.y_index - destination.y_index
    )
    return _ResolvedRoute(
        rule=rule,
        source=source,
        destination=destination,
        nodes=nodes,
        movement_cost=movement_cost,
        perimeter_bias_cost=perimeter_bias_cost,
        turn_cost=turn_cost,
        total_cost=movement_cost + perimeter_bias_cost + turn_cost,
        turn_count=tie_values[final_state][0],
        manhattan_reference_cost=(
            max(0, manhattan_steps - 1) * costs.empty_node_cost
            + costs.traversable_hint_node_cost
        ),
    )


def _inside_grid(validated: _ValidatedRouting, node: _Node) -> bool:
    return (
        0 <= node[0] < validated.x_node_count
        and 0 <= node[1] < validated.y_node_count
    )


def _can_enter(
    *,
    validated: _ValidatedRouting,
    node: _Node,
    target: _Node,
    rule: CirculationRouteRule,
    hallway_classes: Mapping[tuple[str, int], HallwayTrafficClass],
) -> bool:
    if node == target:
        return True

    occupant = validated.occupied_nodes.get(node)
    if occupant is None:
        return True

    room_type = occupant.point.room_type
    if room_type is RoomType.HALLWAY and not _hallway_allows_route(
        route_class=rule.traffic_class,
        hallway_class=hallway_classes.get(
            (occupant.point.source_room_id, occupant.point.hint_index)
        ),
    ):
        return False

    return (
        room_type in validated.config.always_traversable_room_types
        or room_type in rule.allowed_transit_room_types
    )


def _hallway_allows_route(
    *,
    route_class: CirculationTrafficClass,
    hallway_class: HallwayTrafficClass | None,
) -> bool:
    if hallway_class is None:
        return True
    if hallway_class in {
        HallwayTrafficClass.MIXED,
        HallwayTrafficClass.UNCLASSIFIED,
    }:
        return True
    if hallway_class is HallwayTrafficClass.UNUSED:
        return False
    if hallway_class is HallwayTrafficClass.PUBLIC:
        return route_class is CirculationTrafficClass.PUBLIC
    return route_class is CirculationTrafficClass.PRIVATE


def _transition_costs(
    *,
    validated: _ValidatedRouting,
    node: _Node,
    previous_node: _Node,
    direction: int,
    previous_direction: int,
) -> tuple[float, float, float]:
    costs = validated.config.costs
    movement_cost = (
        costs.traversable_hint_node_cost
        if node in validated.occupied_nodes
        else costs.empty_node_cost
    )
    perimeter_bias_cost = _perimeter_bias_cost(
        validated,
        previous_node,
        node,
    )
    turn_cost = (
        costs.turn_cost
        if previous_direction != _NONE_DIRECTION
        and previous_direction != direction
        else 0.0
    )
    return movement_cost, perimeter_bias_cost, turn_cost


def _perimeter_bias_cost(
    validated: _ValidatedRouting,
    start: _Node,
    end: _Node,
) -> float:
    max_cost = validated.config.costs.perimeter_bias_max_cost
    if max_cost == 0:
        return 0.0

    grid = validated.config.grid
    midpoint_x = grid.origin_x + ((start[0] + end[0]) / 2.0) * grid.scale
    midpoint_y = grid.origin_y + ((start[1] + end[1]) / 2.0) * grid.scale
    center_x = grid.origin_x + grid.width / 2.0
    center_y = grid.origin_y + grid.length / 2.0
    normalized_x = abs(midpoint_x - center_x) / (grid.width / 2.0)
    normalized_y = abs(midpoint_y - center_y) / (grid.length / 2.0)
    perimeter_ratio = min(1.0, max(normalized_x, normalized_y))
    return perimeter_ratio * max_cost


def _reconstruct_states(
    start: _State,
    end: _State,
    predecessors: Mapping[_State, _State],
) -> tuple[_State, ...]:
    reversed_states = [end]
    current = end
    while current != start:
        current = predecessors[current]
        reversed_states.append(current)
    reversed_states.reverse()
    return tuple(reversed_states)


def _weighted_efficiency_score(
    routes: tuple[_ResolvedRoute, ...],
    total_expected_weight: float,
) -> float:
    if total_expected_weight <= 0:
        return 0.0
    return _clamp_score(
        sum(
            route.path_efficiency_score * route.rule.importance_weight
            for route in routes
        )
        / total_expected_weight
    )


def _failure_finding(failure: _RouteFailure) -> ScoreFinding:
    subject_ids = [failure.source.point.source_room_id]
    if failure.destination is not None:
        subject_ids.append(failure.destination.point.source_room_id)
    return ScoreFinding(
        code="RELATION_PATH_MISSING",
        message=failure.message,
        severity=FindingSeverity.WARNING,
        subject_ids=tuple(subject_ids),
    )


def _debug_metrics(
    *,
    active_rules: tuple[CirculationRouteRule, ...],
    routes: tuple[_ResolvedRoute, ...],
    failures: tuple[_RouteFailure, ...],
    score: float,
) -> dict[str, float]:
    return {
        "active_rule_count": float(len(active_rules)),
        "resolved_route_count": float(len(routes)),
        "failed_route_count": float(len(failures)),
        "path_efficiency_score": score,
        "average_route_cost": (
            sum(route.total_cost for route in routes) / len(routes)
            if routes
            else 0.0
        ),
    }


def _debug_details(
    validated: _ValidatedRouting,
    routes: tuple[_ResolvedRoute, ...],
    failures: tuple[_RouteFailure, ...],
    score: float,
) -> RelationshipQualityDetails:
    return RelationshipQualityDetails(
        floor_width=validated.data.floor_width,
        floor_length=validated.data.floor_length,
        grid_node_count=validated.grid_node_count,
        path_efficiency_score=score,
        paths=tuple(_path_details(validated, route) for route in routes),
        route_failures=tuple(_failure_details(failure) for failure in failures),
    )


def _path_details(
    validated: _ValidatedRouting,
    route: _ResolvedRoute,
) -> RelationshipPathDetails:
    grid = validated.config.grid
    return RelationshipPathDetails(
        rule_id=route.rule.id,
        rule_name=route.rule.name,
        traffic_class=route.rule.traffic_class,
        destination_selection=route.rule.destination_selection,
        source_point_id=route.source.point.room_id,
        source_room_id=route.source.point.source_room_id,
        source_room_type=route.source.point.room_type,
        destination_point_id=route.destination.point.room_id,
        destination_room_id=route.destination.point.source_room_id,
        destination_room_type=route.destination.point.room_type,
        nodes=tuple(
            CirculationGridNode(
                x_index=x_index,
                y_index=y_index,
                x=grid.origin_x + x_index * grid.scale,
                y=grid.origin_y + y_index * grid.scale,
            )
            for x_index, y_index in route.nodes
        ),
        step_count=route.step_count,
        manhattan_step_count=route.manhattan_step_count,
        detour_step_count=route.step_count - route.manhattan_step_count,
        turn_count=route.turn_count,
        manhattan_reference_cost=route.manhattan_reference_cost,
        costs=RouteCostBreakdown(
            movement_cost=route.movement_cost,
            perimeter_bias_cost=route.perimeter_bias_cost,
            turn_cost=route.turn_cost,
            traffic_conflict_cost=0.0,
            total_cost=route.total_cost,
        ),
        path_efficiency_score=route.path_efficiency_score,
    )


def _failure_details(
    failure: _RouteFailure,
) -> RelationshipRouteFailureDetails:
    return RelationshipRouteFailureDetails(
        rule_id=failure.rule.id,
        rule_name=failure.rule.name,
        traffic_class=failure.rule.traffic_class,
        source_point_id=failure.source.point.room_id,
        source_room_id=failure.source.point.source_room_id,
        destination_point_id=(
            failure.destination.point.room_id
            if failure.destination is not None
            else None
        ),
        destination_room_id=(
            failure.destination.point.source_room_id
            if failure.destination is not None
            else None
        ),
        message=failure.message,
    )


def _missing_path_message(
    rule: CirculationRouteRule,
    source: _IndexedPoint,
    destination: _IndexedPoint,
) -> str:
    return (
        f"Route rule {rule.id} ('{rule.name}') could not resolve "
        f"'{source.point.room_id}' to '{destination.point.room_id}' while "
        "respecting transit and hallway traffic restrictions."
    )


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))
