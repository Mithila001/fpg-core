from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model

from ..domain import OpeningType, RoomId
from .config import FloorPlanOpeningsConfig
from .constraints import OPENING_CONSTRAINT_TYPES
from .constraints.base import OpeningConstraint
from .domain import (
    AnalyzedWall,
    OpeningDemand,
    PlacementOption,
    PreparedFloorPlan,
    WallKind,
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
    clearance_deficit: Any
    window_clearance_deficit: Any


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
    secondary_objective: Any
    clearance_deficits: tuple[Any, ...]


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
    maximum_cost = wall.length
    position_cost = context.model.NewIntVar(
        0,
        maximum_cost,
        context.new_name("position_cost", option.id),
    )

    interior = demand.opening_type is OpeningType.DOOR and wall.kind is WallKind.SHARED
    policy = (
        context.config.interior_doors.resolve(
            tuple(
                context.prepared.rooms_by_id[room_id].room_type
                for room_id in wall.room_ids
            )
        )
        if interior
        else None
    )
    if demand.opening_type is OpeningType.DOOR and (
        policy is None or policy.placement_preference == "wall_end"
    ):
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
        full_position_cost = edge_deviation
    else:
        center_expression = 2 * start + option.width - wall.length
        center_deviation = context.model.NewIntVar(
            0,
            wall.length,
            context.new_name("center_deviation", option.id),
        )
        context.model.AddAbsEquality(center_deviation, center_expression)
        full_position_cost = center_deviation

    context.model.Add(position_cost == full_position_cost).OnlyEnforceIf(selected)
    context.model.Add(position_cost == 0).OnlyEnforceIf(selected.Not())
    return position_cost


def _create_variables(context: OpeningModelContext) -> None:
    walls = context.prepared.wall_by_id()
    for demand in context.demands:
        for option_index, option in enumerate(demand.options):
            wall = walls[option.wall_id]
            interior = (
                demand.opening_type is OpeningType.DOOR and wall.kind is WallKind.SHARED
            )
            policy = (
                context.config.interior_doors.resolve(
                    tuple(
                        context.prepared.rooms_by_id[room_id].room_type
                        for room_id in wall.room_ids
                    )
                )
                if interior
                else None
            )
            window_policy = (
                context.config.window_policy(
                    context.prepared.rooms_by_id[wall.room_ids[0]].room_type
                )
                if demand.opening_type is OpeningType.WINDOW
                else None
            )
            clearance = round(
                (
                    policy.minimum_clearance
                    if policy
                    else window_policy.minimum_clearance
                    if window_policy
                    else context.config.geometry.corner_clearance
                )
                * context.prepared.scale
            )
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
            deficit = 0
            window_deficit = 0
            if policy:
                preferred = round(policy.preferred_clearance * context.prepared.scale)
                deficits = []
                for distance in (start, wall.length - end):
                    raw = context.model.NewIntVar(
                        0,
                        preferred,
                        context.new_name("raw_clearance_deficit", option.id),
                    )
                    context.model.AddMaxEquality(raw, [0, preferred - distance])
                    active = context.model.NewIntVar(
                        0, preferred, context.new_name("clearance_deficit", option.id)
                    )
                    context.model.Add(active == raw).OnlyEnforceIf(selected)
                    context.model.Add(active == 0).OnlyEnforceIf(selected.Not())
                    deficits.append(active)
                deficit = sum(deficits)
            if window_policy:
                preferred = round(
                    window_policy.preferred_clearance * context.prepared.scale
                )
                deficits = []
                for distance in (start, wall.length - end):
                    raw = context.model.NewIntVar(
                        0, preferred, context.new_name("window_raw_deficit", option.id)
                    )
                    context.model.AddMaxEquality(raw, [0, preferred - distance])
                    active = context.model.NewIntVar(
                        0, preferred, context.new_name("window_deficit", option.id)
                    )
                    context.model.Add(active == raw).OnlyEnforceIf(selected)
                    context.model.Add(active == 0).OnlyEnforceIf(selected.Not())
                    deficits.append(active)
                window_deficit = sum(deficits)
            variables = PlacementVariables(
                demand=demand,
                option=option,
                wall=wall,
                selected=selected,
                start=start,
                end=end,
                interval=interval,
                position_cost=position_cost,
                clearance_deficit=deficit,
                window_clearance_deficit=window_deficit,
                option_cost=(
                    option.preference_rank * (len(demand.options) + 1) + option_index
                ),
            )
            context.all_variables.append(variables)
            context.variables_by_demand[demand.id].append(variables)
            context.variables_by_wall[wall.id].append(variables)


def _apply_constraints(context: OpeningModelContext) -> None:
    constraints: dict[str, OpeningConstraint] = {
        constraint_type.constraint_id: constraint_type()
        for constraint_type in OPENING_CONSTRAINT_TYPES
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


def _apply_objective(context: OpeningModelContext) -> tuple[bool, Any]:
    if not context.all_variables:
        return False, 0
    maximum_position = sum(item.wall.length for item in context.all_variables)
    option_stride = maximum_position + len(context.all_variables) + 1
    maximum_preference = sum(
        item.wall.length + 1 + item.option_cost * option_stride
        for item in context.all_variables
    )
    clearance_stride = maximum_preference + 1
    maximum_window_deficit = sum(
        2
        * round(
            context.config.window_policy(
                context.prepared.rooms_by_id[item.wall.room_ids[0]].room_type
            ).preferred_clearance
            * context.prepared.scale
        )
        for item in context.all_variables
        if item.demand.opening_type is OpeningType.WINDOW
    )
    maximum_preference += maximum_window_deficit * clearance_stride

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

    objective_bound = sum(
        item.wall.length
        + 1
        + item.option_cost * option_stride
        + coefficient_by_tier[item.demand.objective_tier]
        for item in context.all_variables
    )
    objective_bound += maximum_window_deficit * clearance_stride
    if objective_bound >= (1 << 62):
        raise OpeningConfigurationError("opening objective exceeds safe integer limits")
    preference_costs = [
        item.position_cost
        + (item.option_cost * option_stride + 1) * item.selected
        + item.window_clearance_deficit * clearance_stride
        for item in context.all_variables
    ]
    rewards = []
    for demand in context.demands:
        selection = demand_selection[demand.id]
        if demand.options and not (
            demand.feature_id == "interior_doors"
            and demand.category == "other_interior"
        ):
            rewards.append(coefficient_by_tier[demand.objective_tier] * selection)
            context.objective_terms.append(
                f"select:{demand.id}:{demand.objective_tier}"
            )
    secondary = sum(rewards) - sum(preference_costs)
    context.model.Minimize(
        sum(item.clearance_deficit for item in context.all_variables)
    )
    context.objective_terms.append("interior_clearance_deficit")
    context.objective_terms.append("wall_preference_and_opening_positioning")
    return True, secondary


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
    has_objective, secondary = _apply_objective(context)
    return BuiltOpeningModel(
        context=context,
        has_objective=has_objective,
        secondary_objective=secondary,
        clearance_deficits=tuple(
            item.clearance_deficit for item in context.all_variables
        ),
    )
