from __future__ import annotations

import heapq
import itertools
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TypeAlias

from ..domain import RoomType
from .config import CirculationRouteRule
from .domain import DestinationSelection, HallwayTrafficClass, TrafficClass
from .exceptions import CirculationPathNotFoundError
from .validation import IndexedCandidatePoint, ValidatedCirculationInput

_Node: TypeAlias = tuple[int, int]
_Direction: TypeAlias = int
_State: TypeAlias = tuple[int, int, int]

_NONE_DIRECTION = -1
_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (1, 0),
    (0, 1),
    (-1, 0),
    (0, -1),
)


@dataclass(frozen=True, slots=True)
class ResolvedRoute:
    rule: CirculationRouteRule
    source: IndexedCandidatePoint
    destination: IndexedCandidatePoint
    nodes: tuple[_Node, ...]
    movement_cost: float
    perimeter_bias_cost: float
    turn_cost: float
    traffic_conflict_cost: float
    total_cost: float
    turn_count: int
    manhattan_reference_cost: float

    @property
    def step_count(self) -> int:
        return max(0, len(self.nodes) - 1)

    @property
    def diagnostic_score(self) -> float:
        if self.total_cost <= 0:
            return 100.0
        return max(
            0.0,
            min(100.0, 100.0 * self.manhattan_reference_cost / self.total_cost),
        )

    @property
    def manhattan_step_count(self) -> int:
        return abs(self.source.x_index - self.destination.x_index) + abs(
            self.source.y_index - self.destination.y_index
        )




@dataclass(slots=True)
class HallwayTraffic:
    public_route_count: int = 0
    private_route_count: int = 0
    public_importance_weight: float = 0.0
    private_importance_weight: float = 0.0


@dataclass(frozen=True, slots=True)
class RoutingPassResult:
    pass_number: int
    routes: tuple[ResolvedRoute, ...]
    hallway_traffic: dict[str, HallwayTraffic]
    hallway_classes: dict[str, HallwayTrafficClass]


def run_routing_passes(
    validated: ValidatedCirculationInput,
) -> tuple[RoutingPassResult, ...]:
    hallway_points = tuple(
        point
        for point in validated.indexed_points
        if point.point.room_type is RoomType.HALLWAY
    )
    previous_classes: dict[str, HallwayTrafficClass] = {}
    passes: list[RoutingPassResult] = []

    for pass_number in range(1, validated.source.config.max_routing_passes + 1):
        active_classes = previous_classes if pass_number > 1 else {}
        routes = _resolve_all_rules(validated, active_classes)
        traffic = _collect_hallway_traffic(hallway_points, routes)
        classes = _classify_hallways(hallway_points, traffic)
        current_pass = RoutingPassResult(
            pass_number=pass_number,
            routes=routes,
            hallway_traffic=traffic,
            hallway_classes=classes,
        )
        passes.append(current_pass)

        if pass_number == 1:
            previous_classes = classes
            continue

        if classes == previous_classes:
            break
        previous_classes = classes

    return tuple(passes)


def _resolve_all_rules(
    validated: ValidatedCirculationInput,
    hallway_classes: dict[str, HallwayTrafficClass],
) -> tuple[ResolvedRoute, ...]:
    points_by_type: dict[RoomType, list[IndexedCandidatePoint]] = defaultdict(list)
    for point in validated.indexed_points:
        room_type = point.point.room_type
        if room_type is not None:
            points_by_type[room_type].append(point)

    routes: list[ResolvedRoute] = []
    for rule in validated.source.config.route_rules:
        sources = points_by_type[rule.source_room_type]
        destinations = points_by_type[rule.destination_room_type]

        for source in sources:
            candidates: list[ResolvedRoute] = []
            for destination in destinations:
                route = _route_between(
                    validated=validated,
                    rule=rule,
                    source=source,
                    destination=destination,
                    hallway_classes=hallway_classes,
                )
                if route is not None:
                    candidates.append(route)
                elif rule.destination_selection is DestinationSelection.ALL_MATCHING:
                    raise CirculationPathNotFoundError(
                        _missing_path_message(rule, source, destination)
                    )

            if rule.destination_selection is DestinationSelection.ALL_MATCHING:
                routes.extend(candidates)
                continue

            if not candidates:
                raise CirculationPathNotFoundError(
                    f"Route rule {rule.id} ('{rule.name}') could not reach any "
                    f"{rule.destination_room_type.value} point from "
                    f"'{source.point_key}'."
                )
            routes.append(
                min(
                    candidates,
                    key=lambda route: (
                        route.total_cost,
                        route.turn_count,
                        route.step_count,
                        route.destination.point_key,
                    ),
                )
            )

    return tuple(routes)


def _route_between(
    *,
    validated: ValidatedCirculationInput,
    rule: CirculationRouteRule,
    source: IndexedCandidatePoint,
    destination: IndexedCandidatePoint,
    hallway_classes: dict[str, HallwayTrafficClass],
) -> ResolvedRoute | None:
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
            ):
                continue

            transition = _transition_costs(
                validated=validated,
                node=next_node,
                previous_node=node,
                direction=direction,
                previous_direction=previous_direction,
                rule=rule,
                hallway_classes=hallway_classes,
            )
            new_cost = cost + sum(transition)
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
                if math.isclose(
                    new_cost,
                    existing_cost,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ) and existing_tie is not None and candidate_tie >= existing_tie:
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
    traffic_conflict_cost = 0.0
    for previous_state, state in zip(states, states[1:], strict=False):
        transition = _transition_costs(
            validated=validated,
            node=(state[0], state[1]),
            previous_node=(previous_state[0], previous_state[1]),
            direction=state[2],
            previous_direction=previous_state[2],
            rule=rule,
            hallway_classes=hallway_classes,
        )
        movement_cost += transition[0]
        perimeter_bias_cost += transition[1]
        turn_cost += transition[2]
        traffic_conflict_cost += transition[3]

    resolved = ResolvedRoute(
        rule=rule,
        source=source,
        destination=destination,
        nodes=nodes,
        movement_cost=movement_cost,
        perimeter_bias_cost=perimeter_bias_cost,
        turn_cost=turn_cost,
        traffic_conflict_cost=traffic_conflict_cost,
        total_cost=(
            movement_cost
            + perimeter_bias_cost
            + turn_cost
            + traffic_conflict_cost
        ),
        turn_count=tie_values[final_state][0],
        manhattan_reference_cost=(
            max(0, abs(source.x_index - destination.x_index)
                + abs(source.y_index - destination.y_index) - 1)
            * validated.source.config.costs.empty_node_cost
            + validated.source.config.costs.traversable_hint_node_cost
        ),
    )
    return resolved


def _inside_grid(validated: ValidatedCirculationInput, node: _Node) -> bool:
    return (
        0 <= node[0] < validated.x_node_count
        and 0 <= node[1] < validated.y_node_count
    )


def _can_enter(
    *,
    validated: ValidatedCirculationInput,
    node: _Node,
    target: _Node,
    rule: CirculationRouteRule,
) -> bool:
    if node == target:
        return True
    occupant = validated.occupied_nodes.get(node)
    if occupant is None:
        return True
    room_type = occupant.point.room_type
    if room_type is None:
        return False
    return (
        room_type in validated.source.config.always_traversable_room_types
        or room_type in rule.allowed_transit_room_types
    )


def _transition_costs(
    *,
    validated: ValidatedCirculationInput,
    node: _Node,
    previous_node: _Node,
    direction: _Direction,
    previous_direction: _Direction,
    rule: CirculationRouteRule,
    hallway_classes: dict[str, HallwayTrafficClass],
) -> tuple[float, float, float, float]:
    costs = validated.source.config.costs
    occupant = validated.occupied_nodes.get(node)
    movement_cost = (
        costs.traversable_hint_node_cost
        if occupant is not None
        else costs.empty_node_cost
    )
    perimeter_bias_cost = _perimeter_bias_cost(
        validated,
        previous_node,
        node,
    )
    turn_cost = (
        costs.turn_cost
        if previous_direction != _NONE_DIRECTION and previous_direction != direction
        else 0.0
    )
    conflict_cost = 0.0
    if occupant is not None and occupant.point.room_type is RoomType.HALLWAY:
        hallway_class = hallway_classes.get(occupant.point_key)
        if _is_traffic_conflict(rule.traffic_class, hallway_class):
            conflict_cost = costs.traffic_conflict_cost
    return movement_cost, perimeter_bias_cost, turn_cost, conflict_cost


def _perimeter_bias_cost(
    validated: ValidatedCirculationInput,
    start: _Node,
    end: _Node,
) -> float:
    max_cost = validated.source.config.costs.perimeter_bias_max_cost
    if max_cost == 0:
        return 0.0

    grid = validated.source.config.grid
    midpoint_x = grid.origin_x + ((start[0] + end[0]) / 2.0) * grid.scale
    midpoint_y = grid.origin_y + ((start[1] + end[1]) / 2.0) * grid.scale
    center_x = grid.origin_x + grid.width / 2.0
    center_y = grid.origin_y + grid.length / 2.0
    normalized_x = abs(midpoint_x - center_x) / (grid.width / 2.0)
    normalized_y = abs(midpoint_y - center_y) / (grid.length / 2.0)
    perimeter_ratio = min(1.0, max(normalized_x, normalized_y))
    return perimeter_ratio * max_cost


def _is_traffic_conflict(
    traffic_class: TrafficClass,
    hallway_class: HallwayTrafficClass | None,
) -> bool:
    return (
        traffic_class is TrafficClass.PUBLIC
        and hallway_class is HallwayTrafficClass.PRIVATE
    ) or (
        traffic_class is TrafficClass.PRIVATE
        and hallway_class is HallwayTrafficClass.PUBLIC
    )


def _reconstruct_states(
    start: _State,
    end: _State,
    predecessors: dict[_State, _State],
) -> tuple[_State, ...]:
    reversed_states = [end]
    current = end
    while current != start:
        current = predecessors[current]
        reversed_states.append(current)
    reversed_states.reverse()
    return tuple(reversed_states)


def _collect_hallway_traffic(
    hallway_points: tuple[IndexedCandidatePoint, ...],
    routes: tuple[ResolvedRoute, ...],
) -> dict[str, HallwayTraffic]:
    hallway_by_node = {
        (point.x_index, point.y_index): point for point in hallway_points
    }
    traffic = {point.point_key: HallwayTraffic() for point in hallway_points}

    for route in routes:
        used_keys = {
            hallway_by_node[node].point_key
            for node in route.nodes
            if node in hallway_by_node
        }
        for point_key in used_keys:
            usage = traffic[point_key]
            if route.rule.traffic_class is TrafficClass.PUBLIC:
                usage.public_route_count += 1
                usage.public_importance_weight += route.rule.importance_weight
            else:
                usage.private_route_count += 1
                usage.private_importance_weight += route.rule.importance_weight
    return traffic


def _classify_hallways(
    hallway_points: tuple[IndexedCandidatePoint, ...],
    traffic: dict[str, HallwayTraffic],
) -> dict[str, HallwayTrafficClass]:
    single_hallway = len(hallway_points) == 1
    classifications: dict[str, HallwayTrafficClass] = {}

    for point in hallway_points:
        usage = traffic[point.point_key]
        total_route_count = (
            usage.public_route_count + usage.private_route_count
        )
        if total_route_count == 0:
            classifications[point.point_key] = HallwayTrafficClass.UNUSED
        elif single_hallway:
            classifications[point.point_key] = HallwayTrafficClass.UNCLASSIFIED
        elif usage.public_route_count == usage.private_route_count:
            classifications[point.point_key] = HallwayTrafficClass.MIXED
        elif usage.public_route_count > usage.private_route_count:
            classifications[point.point_key] = HallwayTrafficClass.PUBLIC
        else:
            classifications[point.point_key] = HallwayTrafficClass.PRIVATE

    return classifications


def _missing_path_message(
    rule: CirculationRouteRule,
    source: IndexedCandidatePoint,
    destination: IndexedCandidatePoint,
) -> str:
    return (
        f"Route rule {rule.id} ('{rule.name}') could not resolve "
        f"'{source.point_key}' to '{destination.point_key}'."
    )
