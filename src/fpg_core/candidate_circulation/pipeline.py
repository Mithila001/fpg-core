from __future__ import annotations

from time import perf_counter

from ..domain import ExecutionMetadata, ExecutionMode, FeatureExecution, RoomType
from .contracts import (
    CandidateCirculationDetails,
    CandidateCirculationInput,
    CandidateCirculationResult,
)
from .domain import (
    CirculationPathDetails,
    GridNode,
    HallwayTrafficClass,
    HallwayTrafficDetails,
    RemovedHallwayPointDetails,
    RouteCostBreakdown,
    RoutingPassDetails,
)
from .routing import ResolvedRoute, RoutingPassResult, run_routing_passes
from .validation import ValidatedCirculationInput, validate_circulation_input


def refine_candidate_circulation(
    circulation_input: CandidateCirculationInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]:
    """Resolve configured routes and remove hallway hints unused by final traffic."""

    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance.")

    started_at = perf_counter()
    validated = validate_circulation_input(circulation_input)
    routing_passes = run_routing_passes(validated)
    final_pass = routing_passes[-1]
    removed_keys = {
        point_key
        for point_key, traffic_class in final_pass.hallway_classes.items()
        if traffic_class.value == "unused"
    }
    cleaned_points = tuple(
        indexed.point
        for indexed in validated.indexed_points
        if indexed.point_key not in removed_keys
    )
    result = CandidateCirculationResult(points=cleaned_points)
    details = (
        _build_details(validated, routing_passes, removed_keys)
        if mode is ExecutionMode.DEBUG
        else None
    )

    return FeatureExecution(
        result=result,
        details=details,
        metadata=ExecutionMetadata(
            mode=mode,
            duration_seconds=perf_counter() - started_at,
        ),
    )


def _build_details(
    validated: ValidatedCirculationInput,
    passes: tuple[RoutingPassResult, ...],
    removed_keys: set[str],
) -> CandidateCirculationDetails:
    pass_details = tuple(
        _routing_pass_details(
            validated,
            routing_pass,
            removed_keys,
            previous_classes=(
                passes[index - 1].hallway_classes if index > 0 else None
            ),
        )
        for index, routing_pass in enumerate(passes)
    )
    final_pass = passes[-1]
    final_hallway_traffic = _hallway_traffic_details(
        validated,
        final_pass,
        removed_keys,
    )
    removed_points = tuple(
        RemovedHallwayPointDetails(
            point_key=point.point_key,
            room_id=str(point.point.room_id),
            hint_index=point.point.hint_index,
            x=point.point.x,
            y=point.point.y,
        )
        for point in validated.indexed_points
        if point.point_key in removed_keys
    )
    return CandidateCirculationDetails(
        diagnostic_score=_diagnostic_score(final_pass.routes),
        routing_pass_count=len(passes),
        grid_node_count=validated.grid_node_count,
        passes=pass_details,
        final_hallway_traffic=final_hallway_traffic,
        removed_hallway_points=removed_points,
    )


def _routing_pass_details(
    validated: ValidatedCirculationInput,
    routing_pass: RoutingPassResult,
    removed_keys: set[str],
    previous_classes: dict[str, HallwayTrafficClass] | None,
) -> RoutingPassDetails:
    return RoutingPassDetails(
        pass_number=routing_pass.pass_number,
        classifications_changed_from_previous=(
            previous_classes is not None
            and routing_pass.hallway_classes != previous_classes
        ),
        paths=tuple(
            _path_details(validated, route) for route in routing_pass.routes
        ),
        hallway_traffic=_hallway_traffic_details(
            validated,
            routing_pass,
            removed_keys,
        ),
    )


def _path_details(
    validated: ValidatedCirculationInput,
    route: ResolvedRoute,
) -> CirculationPathDetails:
    grid = validated.source.config.grid
    nodes = tuple(
        GridNode(
            x_index=x_index,
            y_index=y_index,
            x=grid.origin_x + x_index * grid.scale,
            y=grid.origin_y + y_index * grid.scale,
        )
        for x_index, y_index in route.nodes
    )
    source_type = route.source.point.room_type
    destination_type = route.destination.point.room_type
    if source_type is None or destination_type is None:
        raise RuntimeError("Validated route endpoints must have room types.")

    return CirculationPathDetails(
        rule_id=route.rule.id,
        rule_name=route.rule.name,
        traffic_class=route.rule.traffic_class,
        destination_selection=route.rule.destination_selection,
        allowed_transit_room_types=route.rule.allowed_transit_room_types,
        importance_weight=route.rule.importance_weight,
        source_point_key=route.source.point_key,
        source_room_id=str(route.source.point.room_id),
        source_room_type=source_type,
        destination_point_key=route.destination.point_key,
        destination_room_id=str(route.destination.point.room_id),
        destination_room_type=destination_type,
        nodes=nodes,
        step_count=route.step_count,
        manhattan_step_count=route.manhattan_step_count,
        detour_step_count=(
            route.step_count - route.manhattan_step_count
        ),
        turn_count=route.turn_count,
        manhattan_reference_cost=route.manhattan_reference_cost,
        costs=RouteCostBreakdown(
            movement_cost=route.movement_cost,
            perimeter_bias_cost=route.perimeter_bias_cost,
            turn_cost=route.turn_cost,
            traffic_conflict_cost=route.traffic_conflict_cost,
            total_cost=route.total_cost,
        ),
        diagnostic_score=route.diagnostic_score,
    )


def _hallway_traffic_details(
    validated: ValidatedCirculationInput,
    routing_pass: RoutingPassResult,
    removed_keys: set[str],
) -> tuple[HallwayTrafficDetails, ...]:
    details: list[HallwayTrafficDetails] = []
    for point in validated.indexed_points:
        if point.point.room_type is not RoomType.HALLWAY:
            continue
        usage = routing_pass.hallway_traffic[point.point_key]
        details.append(
            HallwayTrafficDetails(
                point_key=point.point_key,
                room_id=str(point.point.room_id),
                hint_index=point.point.hint_index,
                x=point.point.x,
                y=point.point.y,
                public_route_count=usage.public_route_count,
                private_route_count=usage.private_route_count,
                public_importance_weight=usage.public_importance_weight,
                private_importance_weight=usage.private_importance_weight,
                traffic_class=routing_pass.hallway_classes[point.point_key],
                removed=point.point_key in removed_keys,
            )
        )
    return tuple(details)


def _diagnostic_score(routes: tuple[ResolvedRoute, ...]) -> float:
    total_importance_weight = sum(
        route.rule.importance_weight for route in routes
    )
    if total_importance_weight <= 0:
        return 0.0
    return sum(
        route.diagnostic_score * route.rule.importance_weight
        for route in routes
    ) / total_importance_weight
