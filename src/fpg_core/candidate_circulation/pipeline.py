from __future__ import annotations

from time import perf_counter

from ..domain import (
    CandidateMap,
    CirculationGridNode,
    ExecutionMetadata,
    ExecutionMode,
    FeatureExecution,
    HallwayClassification,
    HallwayTrafficClass,
    RoomType,
    RouteCostBreakdown,
)
from .consolidation import HallwayConsolidationResult, consolidate_hallways
from .contracts import (
    CandidateCirculationDetails,
    CandidateCirculationInput,
    CandidateCirculationResult,
)
from .domain import (
    CirculationPathDetails,
    HallwayRemovalReason,
    HallwayTrafficDetails,
    RemovedHallwayPointDetails,
    RoutingPassDetails,
)
from .routing import ResolvedRoute, RoutingPassResult, run_routing_passes
from .validation import ValidatedCirculationInput, validate_circulation_input


def refine_candidate_circulation(
    circulation_input: CandidateCirculationInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]:
    """Resolve routes, classify hallways, and remove redundant hallway hints."""

    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance.")

    started_at = perf_counter()
    validated = validate_circulation_input(circulation_input)
    routing_passes = run_routing_passes(validated)
    initial_final_pass = routing_passes[-1]
    unused_keys = {
        point_key
        for point_key, traffic_class in initial_final_pass.hallway_classes.items()
        if traffic_class is HallwayTrafficClass.UNUSED
    }

    consolidation = consolidate_hallways(validated, unused_keys=unused_keys)
    if consolidation is None:
        consolidated_keys: set[str] = set()
        final_validated = validated
        final_pass = initial_final_pass
        cleaned_points = tuple(
            indexed.point
            for indexed in validated.indexed_points
            if indexed.point_key not in unused_keys
        )
    else:
        consolidated_keys = set(consolidation.removed_keys)
        final_validated = consolidation.validated
        final_pass = consolidation.routing_passes[-1]
        cleaned_points = tuple(indexed.point for indexed in final_validated.indexed_points)

    removal_reasons = {
        **{key: HallwayRemovalReason.UNUSED for key in unused_keys},
        **{key: HallwayRemovalReason.CONSOLIDATED for key in consolidated_keys},
    }
    removed_keys = set(removal_reasons)

    result = CandidateCirculationResult(
        candidate=CandidateMap(
            grid=validated.source.candidate.grid,
            points=cleaned_points,
        ),
        hallway_classifications=_hallway_classifications(
            validated,
            initial_final_pass,
            final_pass,
            unused_keys,
            consolidation,
        ),
    )
    details = (
        _build_details(
            validated,
            routing_passes,
            initial_final_pass,
            final_pass,
            removal_reasons,
            consolidation,
        )
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


def _hallway_classifications(
    validated: ValidatedCirculationInput,
    initial_final_pass: RoutingPassResult,
    final_pass: RoutingPassResult,
    unused_keys: set[str],
    consolidation: HallwayConsolidationResult | None,
) -> tuple[HallwayClassification, ...]:
    classifications: list[HallwayClassification] = []
    for point in validated.indexed_points:
        if point.point.room_type is not RoomType.HALLWAY:
            continue

        if point.point_key in unused_keys:
            traffic_class = HallwayTrafficClass.UNUSED
        elif (
            consolidation is not None
            and point.point_key in consolidation.removed_snapshots
        ):
            traffic_class = consolidation.removed_snapshots[
                point.point_key
            ].traffic_class
        else:
            traffic_class = final_pass.hallway_classes.get(
                point.point_key,
                initial_final_pass.hallway_classes[point.point_key],
            )

        classifications.append(
            HallwayClassification(
                room_id=point.point.room_id,
                hint_index=point.point.hint_index,
                traffic_class=traffic_class,
            )
        )
    return tuple(classifications)


def _build_details(
    validated: ValidatedCirculationInput,
    passes: tuple[RoutingPassResult, ...],
    initial_final_pass: RoutingPassResult,
    final_pass: RoutingPassResult,
    removal_reasons: dict[str, HallwayRemovalReason],
    consolidation: HallwayConsolidationResult | None,
) -> CandidateCirculationDetails:
    pass_details = tuple(
        _routing_pass_details(
            validated,
            routing_pass,
            removal_reasons,
            previous_classes=(
                passes[index - 1].hallway_classes if index > 0 else None
            ),
        )
        for index, routing_pass in enumerate(passes)
    )
    final_hallway_traffic = _final_hallway_traffic_details(
        validated,
        initial_final_pass,
        final_pass,
        removal_reasons,
        consolidation,
    )
    removed_points = tuple(
        RemovedHallwayPointDetails(
            point_key=point.point_key,
            room_id=str(point.point.room_id),
            hint_index=point.point.hint_index,
            x=point.point.x,
            y=point.point.y,
            reason=removal_reasons[point.point_key],
        )
        for point in validated.indexed_points
        if point.point_key in removal_reasons
    )
    return CandidateCirculationDetails(
        circulation_efficiency_score=_circulation_efficiency_score(
            final_pass.routes
        ),
        routing_pass_count=len(passes),
        grid_node_count=validated.grid_node_count,
        passes=pass_details,
        final_hallway_traffic=final_hallway_traffic,
        removed_hallway_points=removed_points,
        hallway_consolidation_attempts=(
            consolidation.attempts if consolidation is not None else ()
        ),
    )


def _routing_pass_details(
    validated: ValidatedCirculationInput,
    routing_pass: RoutingPassResult,
    removal_reasons: dict[str, HallwayRemovalReason],
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
            removal_reasons,
        ),
    )


def _path_details(
    validated: ValidatedCirculationInput,
    route: ResolvedRoute,
) -> CirculationPathDetails:
    grid = validated.source.candidate.grid
    nodes = tuple(
        CirculationGridNode(
            x_index=x_index,
            y_index=y_index,
            x=grid.x_positions[x_index],
            y=grid.y_positions[y_index],
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
        required_transit_room_types=route.rule.required_transit_room_types,
        required_transit_point_keys=route.required_transit_point_keys,
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
        detour_step_count=route.step_count - route.manhattan_step_count,
        turn_count=route.turn_count,
        manhattan_reference_cost=route.manhattan_reference_cost,
        costs=RouteCostBreakdown(
            movement_cost=route.movement_cost,
            perimeter_bias_cost=route.perimeter_bias_cost,
            turn_cost=route.turn_cost,
            traffic_conflict_cost=route.traffic_conflict_cost,
            total_cost=route.total_cost,
        ),
        path_efficiency_score=route.path_efficiency_score,
    )


def _hallway_traffic_details(
    validated: ValidatedCirculationInput,
    routing_pass: RoutingPassResult,
    removal_reasons: dict[str, HallwayRemovalReason],
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
                removed=point.point_key in removal_reasons,
                removal_reason=removal_reasons.get(point.point_key),
            )
        )
    return tuple(details)


def _final_hallway_traffic_details(
    validated: ValidatedCirculationInput,
    initial_final_pass: RoutingPassResult,
    final_pass: RoutingPassResult,
    removal_reasons: dict[str, HallwayRemovalReason],
    consolidation: HallwayConsolidationResult | None,
) -> tuple[HallwayTrafficDetails, ...]:
    details: list[HallwayTrafficDetails] = []
    for point in validated.indexed_points:
        if point.point.room_type is not RoomType.HALLWAY:
            continue

        reason = removal_reasons.get(point.point_key)
        if reason is HallwayRemovalReason.UNUSED:
            usage = initial_final_pass.hallway_traffic[point.point_key]
            traffic_class = HallwayTrafficClass.UNUSED
        elif (
            reason is HallwayRemovalReason.CONSOLIDATED
            and consolidation is not None
        ):
            snapshot = consolidation.removed_snapshots[point.point_key]
            usage = snapshot.traffic
            traffic_class = snapshot.traffic_class
        else:
            usage = final_pass.hallway_traffic[point.point_key]
            traffic_class = final_pass.hallway_classes[point.point_key]

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
                traffic_class=traffic_class,
                removed=reason is not None,
                removal_reason=reason,
            )
        )
    return tuple(details)


def _circulation_efficiency_score(routes: tuple[ResolvedRoute, ...]) -> float:
    total_importance_weight = sum(route.rule.importance_weight for route in routes)
    if total_importance_weight <= 0:
        return 0.0
    return sum(
        route.path_efficiency_score * route.rule.importance_weight
        for route in routes
    ) / total_importance_weight
