from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model

from ..domain import OpeningType, RoomId
from .config import FloorPlanOpeningsConfig
from .constraints import (
    RequiredRoomAccessConstraint,
    RoomDoorLimitConstraint,
    SharedPlacementConstraint,
)
from .constraints.base import OpeningConstraint
from .domain import (
    AnalyzedWall,
    OpeningDemand,
    PlacementOption,
    PreparedFloorPlan,
    WallOrientation,
)
from .exceptions import OpeningConfigurationError
from .registry import OpeningFeatureRegistry


@dataclass(slots=True)
class PlacementVariables:
    demand: OpeningDemand
    option: PlacementOption
    wall: AnalyzedWall
    selected: Any
    start: Any
    end: Any
    interval: Any
    position_cost: Any
    option_cost: int


@dataclass(slots=True)
class OpeningModelContext:
    model: Any
    prepared: PreparedFloorPlan
    config: FloorPlanOpeningsConfig
    demands: tuple[OpeningDemand, ...]
    all_variables: list[PlacementVariables] = field(default_factory=list)
    variables_by_demand: dict[str, list[PlacementVariables]] = field(
        default_factory=lambda: defaultdict(list)
    )
    variables_by_wall: dict[str, list[PlacementVariables]] = field(
        default_factory=lambda: defaultdict(list)
    )
    applied_constraints: list[str] = field(default_factory=list)
    objective_terms: list[str] = field(default_factory=list)
    _counter: int = 0

    @property
    def window_spacing(self) -> int:
        return round(self.config.geometry.window_spacing * self.prepared.scale)

    def new_name(self, prefix: str, *parts: object) -> str:
        self._counter += 1
        suffix = "_".join(str(part).replace(":", "_") for part in parts)
        return f"{prefix}_{suffix}_{self._counter}"


@dataclass(frozen=True, slots=True)
class BuiltOpeningModel:
    context: OpeningModelContext
    has_objective: bool


def _build_demands(
    prepared: PreparedFloorPlan,
    config: FloorPlanOpeningsConfig,
    registry: OpeningFeatureRegistry,
) -> tuple[OpeningDemand, ...]:
    demands: list[OpeningDemand] = []
    for feature_id in config.enabled_features:
        demands.extend(registry.resolve(feature_id).build_demands(prepared, config))
    ids = [demand.id for demand in demands]
    if len(ids) != len(set(ids)):
        raise OpeningConfigurationError("opening demand IDs must be unique")
    return tuple(demands)


def _room_corner_axes(
    context: OpeningModelContext,
    wall: AnalyzedWall,
    room_id: RoomId,
) -> tuple[int, ...]:
    room = context.prepared.rooms_by_id[room_id]
    scale = context.prepared.scale
    points = room.boundary.points
    coordinates: set[int] = set()

    for index, first in enumerate(points):
        second = points[(index + 1) % len(points)]
        x1, y1 = round(first.x * scale), round(first.y * scale)
        x2, y2 = round(second.x * scale), round(second.y * scale)

        if wall.orientation is WallOrientation.HORIZONTAL:
            if y1 != wall.fixed_coordinate or y2 != wall.fixed_coordinate:
                continue
            edge_start, edge_end = sorted((x1, x2))
        else:
            if x1 != wall.fixed_coordinate or x2 != wall.fixed_coordinate:
                continue
            edge_start, edge_end = sorted((y1, y2))

        if min(edge_end, wall.end) <= max(edge_start, wall.start):
            continue
        coordinates.update((edge_start, edge_end))

    return tuple(sorted(coordinates))


def _endpoint_corner_distance(
    context: OpeningModelContext,
    wall: AnalyzedWall,
    room_id: RoomId,
    *,
    use_end: bool,
) -> int:
    corners = _room_corner_axes(context, wall, room_id)
    if not corners:
        return wall.length
    endpoint = wall.end if use_end else wall.start
    return min(abs(endpoint - corner) for corner in corners)


def _preferred_door_end(
    context: OpeningModelContext,
    demand: OpeningDemand,
    wall: AnalyzedWall,
) -> str:
    room_ids = tuple(
        room_id
        for room_id in (demand.room_ids or wall.room_ids)
        if room_id in context.prepared.rooms_by_id
    )
    if not room_ids:
        return "start"

    priority_by_type = context.config.policy.door_priority_by_room_type
    priorities = {
        room_id: priority_by_type.get(
            context.prepared.rooms_by_id[room_id].room_type,
            0,
        )
        for room_id in room_ids
    }
    levels = sorted(set(priorities.values()), reverse=True)

    def score(*, use_end: bool) -> tuple[int, ...]:
        return tuple(
            sum(
                _endpoint_corner_distance(
                    context,
                    wall,
                    room_id,
                    use_end=use_end,
                )
                for room_id in room_ids
                if priorities[room_id] == level
            )
            for level in levels
        )

    start_score = score(use_end=False)
    end_score = score(use_end=True)
    return "end" if end_score < start_score else "start"


def _create_position_cost(
    context: OpeningModelContext,
    demand: OpeningDemand,
    wall: AnalyzedWall,
    option: PlacementOption,
    selected: Any,
    start: Any,
    *,
    clearance: int,
    latest: int,
) -> Any:
    maximum_cost = wall.length * (wall.length + 1) + wall.length
    position_cost = context.model.NewIntVar(
        0,
        maximum_cost,
        context.new_name("position_cost", option.id),
    )

    if demand.opening_type is OpeningType.DOOR:
        preferred_end = _preferred_door_end(context, demand, wall)
        edge_deviation = context.model.NewIntVar(
            0,
            wall.length,
            context.new_name("edge_deviation", option.id),
        )
        if preferred_end == "end":
            context.model.Add(edge_deviation == latest - start)
        else:
            context.model.Add(edge_deviation == start - clearance)
        full_position_cost = edge_deviation * (wall.length + 1) + start
    else:
        center_expression = 2 * start + option.width - wall.length
        center_deviation = context.model.NewIntVar(
            0,
            wall.length,
            context.new_name("center_deviation", option.id),
        )
        context.model.AddAbsEquality(center_deviation, center_expression)
        full_position_cost = center_deviation * (wall.length + 1) + start

    context.model.Add(position_cost == full_position_cost).OnlyEnforceIf(selected)
    context.model.Add(position_cost == 0).OnlyEnforceIf(selected.Not())
    return position_cost


def _create_variables(context: OpeningModelContext) -> None:
    walls = context.prepared.wall_by_id()
    clearance = round(
        context.config.geometry.corner_clearance * context.prepared.scale
    )
    for demand in context.demands:
        for option_index, option in enumerate(demand.options):
            wall = walls[option.wall_id]
            latest = wall.length - clearance - option.width
            if latest < clearance:
                raise OpeningConfigurationError(
                    f"option {option.id!r} does not fit its analyzed wall"
                )
            selected = context.model.NewBoolVar(context.new_name("selected", option.id))
            start = context.model.NewIntVar(
                clearance, latest, context.new_name("start", option.id)
            )
            end = context.model.NewIntVar(
                clearance + option.width,
                wall.length - clearance,
                context.new_name("end", option.id),
            )
            context.model.Add(end == start + option.width)
            interval = context.model.NewOptionalIntervalVar(
                start,
                option.width,
                end,
                selected,
                context.new_name("interval", option.id),
            )
            position_cost = _create_position_cost(
                context,
                demand,
                wall,
                option,
                selected,
                start,
                clearance=clearance,
                latest=latest,
            )
            variables = PlacementVariables(
                demand=demand,
                option=option,
                wall=wall,
                selected=selected,
                start=start,
                end=end,
                interval=interval,
                position_cost=position_cost,
                option_cost=(
                    option.preference_rank * (len(demand.options) + 1) + option_index
                ),
            )
            context.all_variables.append(variables)
            context.variables_by_demand[demand.id].append(variables)
            context.variables_by_wall[wall.id].append(variables)


def _apply_constraints(context: OpeningModelContext) -> None:
    constraints: dict[str, OpeningConstraint] = {
        "shared_placement": SharedPlacementConstraint(),
        "room_door_limits": RoomDoorLimitConstraint(),
        "required_room_access": RequiredRoomAccessConstraint(),
    }
    for constraint_id in context.config.enabled_constraints:
        try:
            constraint = constraints[constraint_id]
        except KeyError as exc:
            raise OpeningConfigurationError(
                f"unknown opening constraint '{constraint_id}'"
            ) from exc
        constraint.apply(context)
        context.applied_constraints.append(constraint_id)


def _apply_objective(context: OpeningModelContext) -> bool:
    if not context.all_variables:
        return False
    maximum_position = sum(
        item.wall.length * (item.wall.length + 1) + item.wall.length
        for item in context.all_variables
    )
    option_stride = maximum_position + 1
    preference_costs = [
        item.position_cost + item.option_cost * option_stride * item.selected
        for item in context.all_variables
    ]
    maximum_preference = sum(
        item.wall.length * (item.wall.length + 1)
        + item.wall.length
        + item.option_cost * option_stride
        for item in context.all_variables
    )

    demand_selection = {
        demand.id: sum(
            item.selected for item in context.variables_by_demand.get(demand.id, ())
        )
        for demand in context.demands
    }
    coefficient_by_tier: dict[str, int] = {}
    lower_maximum = maximum_preference
    for tier in context.config.objective.tier_order:
        coefficient_by_tier[tier] = lower_maximum + 1
        tier_count = sum(
            1 for demand in context.demands if demand.objective_tier == tier
        )
        lower_maximum += coefficient_by_tier[tier] * tier_count

    unknown = {
        demand.objective_tier
        for demand in context.demands
        if demand.objective_tier not in coefficient_by_tier
    }
    if unknown:
        raise OpeningConfigurationError(
            f"objective tiers are not configured: {', '.join(sorted(unknown))}"
        )

    rewards = []
    for demand in context.demands:
        selection = demand_selection[demand.id]
        if demand.options:
            rewards.append(coefficient_by_tier[demand.objective_tier] * selection)
            context.objective_terms.append(
                f"select:{demand.id}:{demand.objective_tier}"
            )
    context.model.Maximize(sum(rewards) - sum(preference_costs))
    context.objective_terms.append("wall_preference_and_opening_positioning")
    return True


def build_opening_model(
    prepared: PreparedFloorPlan,
    config: FloorPlanOpeningsConfig,
    registry: OpeningFeatureRegistry,
) -> BuiltOpeningModel:
    demands = _build_demands(prepared, config, registry)
    context = OpeningModelContext(
        model=cp_model.CpModel(),
        prepared=prepared,
        config=config,
        demands=demands,
    )
    _create_variables(context)
    _apply_constraints(context)
    has_objective = _apply_objective(context)
    return BuiltOpeningModel(context=context, has_objective=has_objective)
