# FPG Core Feature Reference

This document provides four independent package-style references for:

- `fpg_core.candidate_circulation`
- `fpg_core.candidate_scoring`
- `fpg_core.candidate_search`
- `fpg_core.floor_plan_preprocessing`

Each section documents the feature on its own: purpose, public API, contracts, behavior, configuration, recommended values, outputs, errors, performance, and current limitations.

This is intentionally **not** an end-to-end pipeline guide.

---

## Shared Conventions

### Project units

FPG Core uses project units for architectural dimensions:

```text
10 project units = 1 metre
1 project unit   = 10 centimetres
100 square project units = 1 square metre
```

Recommendations in this document use that convention. They are practical starting points, not regulatory or construction-code requirements.

### Execution modes

```python
from fpg_core.domain import ExecutionMode

ExecutionMode.PRODUCTION
ExecutionMode.DEBUG
```

`PRODUCTION` keeps normal result data and omits large diagnostic details. `DEBUG` enables feature-specific diagnostics where implemented.

### Standard execution envelope

Some features return:

```text
FeatureExecution[TResult, TDetails]
├── result
├── details
└── metadata
```

`metadata` contains the selected execution mode and elapsed duration.

---

# `fpg_core.candidate_circulation`

## Overview

Candidate Circulation resolves orthogonal grid routes between candidate hint points, classifies hallway traffic, and removes unused hallway hints.

The feature is deterministic and has no external side effects.

### Main responsibilities

- Resolve required room-type routes on an orthogonal grid.
- Support “all matching destinations” and “lowest-cost destination” rules.
- Restrict traversal through occupied hint points.
- Classify hallway hints from route usage.
- Run multiple passes to reduce public/private hallway conflicts.
- Remove hallway hints unused by all final routes.
- Return detailed route diagnostics in `DEBUG` mode.

## Public imports

```python
from fpg_core.candidate_circulation import (
    CandidateCirculationConfig,
    CandidateCirculationDetails,
    CandidateCirculationInput,
    CandidateCirculationResult,
    CandidateCirculationError,
    CandidateCirculationInputError,
    CirculationPathNotFoundError,
    GridAlignmentError,
    RoutingCostProfile,
    refine_candidate_circulation,
)
```

Shared circulation contracts are also re-exported by the feature, but their canonical home is `fpg_core.domain`:

```python
from fpg_core.domain import (
    CandidatePoint,
    CirculationGrid,
    CirculationRouteRule,
    CirculationTrafficClass,
    DestinationSelection,
    ExecutionMode,
    HallwayClassification,
    HallwayTrafficClass,
    RoomType,
)
```

`TrafficClass` remains available as a compatibility alias for `CirculationTrafficClass`.

## Quick start

```python
from fpg_core.candidate_circulation import (
    CandidateCirculationConfig,
    CandidateCirculationInput,
    RoutingCostProfile,
    refine_candidate_circulation,
)
from fpg_core.domain import (
    CandidatePoint,
    CirculationGrid,
    CirculationRouteRule,
    CirculationTrafficClass,
    DestinationSelection,
    ExecutionMode,
    RoomType,
)

points = (
    CandidatePoint("veranda", 10, 10, RoomType.VERANDA),
    CandidatePoint("living", 40, 20, RoomType.LIVING_ROOM),
    CandidatePoint("bedroom_1", 70, 50, RoomType.BEDROOM),
    CandidatePoint("bedroom_2", 30, 60, RoomType.BEDROOM),
    CandidatePoint("hallway", 40, 30, RoomType.HALLWAY, hint_index=1),
    CandidatePoint("hallway", 50, 40, RoomType.HALLWAY, hint_index=2),
)

config = CandidateCirculationConfig(
    grid=CirculationGrid(
        width=100,
        length=80,
        scale=10,
    ),
    costs=RoutingCostProfile(
        empty_node_cost=2.0,
        traversable_hint_node_cost=1.0,
        turn_cost=0.25,
        perimeter_bias_max_cost=0.20,
        traffic_conflict_cost=25.0,
    ),
    route_rules=(
        CirculationRouteRule(
            id=1,
            name="Veranda to living",
            source_room_type=RoomType.VERANDA,
            destination_room_type=RoomType.LIVING_ROOM,
            destination_selection=DestinationSelection.LOWEST_COST_MATCH,
            traffic_class=CirculationTrafficClass.PUBLIC,
            allowed_transit_room_types=(),
            importance_weight=1.0,
        ),
        CirculationRouteRule(
            id=2,
            name="Living to all bedrooms",
            source_room_type=RoomType.LIVING_ROOM,
            destination_room_type=RoomType.BEDROOM,
            destination_selection=DestinationSelection.ALL_MATCHING,
            traffic_class=CirculationTrafficClass.PRIVATE,
            allowed_transit_room_types=(),
            importance_weight=2.0,
        ),
    ),
    always_traversable_room_types=(RoomType.HALLWAY,),
    max_routing_passes=3,
)

execution = refine_candidate_circulation(
    CandidateCirculationInput(points=points, config=config),
    mode=ExecutionMode.PRODUCTION,
)

cleaned_points = execution.result.points
hallway_classifications = execution.result.hallway_classifications
```

## Main operation

```python
refine_candidate_circulation(
    circulation_input: CandidateCirculationInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]
```

The input is not mutated.

## Input contracts

### `CandidateCirculationInput`

```python
CandidateCirculationInput(
    points: tuple[CandidatePoint, ...],
    config: CandidateCirculationConfig,
)
```

Requirements:

- At least one point is required.
- Every item must be a `CandidatePoint`.
- Every point must have a non-`None` `room_type`.
- Point identities must be unique.
- Points may not overlap on the routing grid.
- Points must lie inside the configured grid.
- Points must align exactly to the configured grid scale.

### `CandidatePoint`

```python
CandidatePoint(
    room_id: RoomId,
    x: float,
    y: float,
    room_type: RoomType | None = None,
    hint_index: int = 1,
)
```

Identity is exposed as:

```python
point.point_key  # e.g. "hallway[2]"
```

Only hallway points may use `hint_index > 1`.

## `CandidateCirculationConfig`

```python
CandidateCirculationConfig(
    grid: CirculationGrid,
    costs: RoutingCostProfile,
    route_rules: tuple[CirculationRouteRule, ...],
    always_traversable_room_types: tuple[RoomType, ...],
    max_routing_passes: int = 3,
)
```

### Configuration reference

| Field | Required behavior | Recommended starting value |
|---|---|---|
| `grid` | Positive dimensions and scale | Match the candidate coordinate system exactly |
| `costs` | Positive movement/conflict costs; non-negative turn/perimeter costs | Balanced profile shown below |
| `route_rules` | Non-empty, unique rule IDs | Keep rules explicit and small |
| `always_traversable_room_types` | Unique room types | `(RoomType.HALLWAY,)` |
| `max_routing_passes` | Integer from `2` to `10` | `3` |

## Grid configuration

### `CirculationGrid`

```python
CirculationGrid(
    width: float,
    length: float,
    scale: float,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
)
```

The number of nodes is:

```text
(width / scale + 1) × (length / scale + 1)
```

Both extents must be exact multiples of `scale`.

The implementation rejects grids exceeding `250,000` nodes.

### Recommended grid scale

| Scale | Real-world step | Suggested use |
|---:|---:|---|
| `10` | 1.0 m | Fast coarse route classification |
| `5` | 0.5 m | Balanced residential routing |
| `2` | 0.2 m | Detailed R&D routing |
| `1` | 0.1 m | Expensive and usually unnecessary for candidate-stage routing |

Recommended baseline:

```python
scale=5.0
```

Use `10.0` for fast candidate exploration and `5.0` when route shape matters more.

All candidate coordinates must be exact grid coordinates. When another feature generates the points, use the same resolution or explicitly snap them before calling this feature.

## Route rules

### `CirculationRouteRule`

```python
CirculationRouteRule(
    id: int,
    name: str,
    source_room_type: RoomType,
    destination_room_type: RoomType,
    destination_selection: DestinationSelection,
    traffic_class: CirculationTrafficClass,
    allowed_transit_room_types: tuple[RoomType, ...],
    importance_weight: float,
)
```

Requirements:

- `id` must be a non-negative integer.
- Rule IDs must be unique within the config.
- Source and destination types must differ.
- At least one matching source and destination point must exist.
- `allowed_transit_room_types` must be unique.
- `importance_weight` must be positive.

### Destination selection

#### `ALL_MATCHING`

Each matching source must route to every matching destination.

```text
LIVING_ROOM -> all BEDROOM points
```

Any unresolved source/destination pair raises `CirculationPathNotFoundError`.

#### `LOWEST_COST_MATCH`

Each source selects the cheapest reachable matching destination.

```text
BEDROOM -> cheapest reachable BATHROOM
```

Selection tie-break order is:

1. total route cost,
2. turn count,
3. step count,
4. destination point key.

### Traffic classes

```python
CirculationTrafficClass.PUBLIC
CirculationTrafficClass.PRIVATE
```

Traffic class is used by later routing passes to discourage using a hallway classified for the opposite traffic type.

### Transit behavior

A route may enter:

- an empty grid node,
- its destination node,
- a point whose room type appears in `always_traversable_room_types`,
- a point whose room type appears in that rule's `allowed_transit_room_types`.

All other occupied hint nodes are blocked.

Recommended default:

```python
always_traversable_room_types=(RoomType.HALLWAY,)
```

Do not add bedrooms, kitchens, or living rooms merely to make routing succeed. Doing so changes the architectural meaning of the route.

## Routing cost model

### `RoutingCostProfile`

```python
RoutingCostProfile(
    empty_node_cost: float,
    traversable_hint_node_cost: float,
    turn_cost: float,
    perimeter_bias_max_cost: float,
    traffic_conflict_cost: float,
)
```

Each route transition accumulates:

```text
total_cost =
    movement_cost
    + perimeter_bias_cost
    + turn_cost
    + traffic_conflict_cost
```

### Cost meaning

| Field | Meaning |
|---|---|
| `empty_node_cost` | Cost for entering an unoccupied grid node |
| `traversable_hint_node_cost` | Cost for entering an allowed occupied hint node |
| `turn_cost` | Additional cost when direction changes |
| `perimeter_bias_max_cost` | Maximum per-step cost near the floor perimeter |
| `traffic_conflict_cost` | Later-pass penalty for using an opposite-class hallway |

The perimeter bias is `0` at the floor center and approaches `perimeter_bias_max_cost` near the perimeter.

### Recommended balanced profile

```python
RoutingCostProfile(
    empty_node_cost=2.0,
    traversable_hint_node_cost=1.0,
    turn_cost=0.25,
    perimeter_bias_max_cost=0.20,
    traffic_conflict_cost=25.0,
)
```

### Recommended value ranges

| Setting | Suggested range | Guidance |
|---|---:|---|
| `empty_node_cost` | `1.0-3.0` | Use as the base route-length cost |
| `traversable_hint_node_cost` | `0.5-1.5` | Keep below or near empty-node cost to encourage valid hallway reuse |
| `turn_cost` | `0.10-0.50` | Small preference for straighter paths |
| `perimeter_bias_max_cost` | `0.00-0.30` | Keep small because it is charged per step |
| `traffic_conflict_cost` | `10-50` | Make opposite-class hallway use clearly more expensive than a reasonable detour |

### Cost profiles

#### Fast and permissive

```python
RoutingCostProfile(1.0, 0.75, 0.10, 0.0, 10.0)
```

#### Balanced

```python
RoutingCostProfile(2.0, 1.0, 0.25, 0.20, 25.0)
```

#### Strong traffic separation

```python
RoutingCostProfile(2.0, 1.0, 0.35, 0.15, 50.0)
```

Keep the relative scale stable. Increasing every cost by the same factor normally does not improve route quality.

## `importance_weight`

Recommended vocabulary:

| Weight | Suggested meaning |
|---:|---|
| `0.5` | Minor route |
| `1.0` | Standard route |
| `2.0` | Important route |
| `3.0-5.0` | High-priority diagnostic route |

Current behavior:

- It weights `circulation_efficiency_score` in `DEBUG` output.
- It is accumulated in hallway traffic diagnostics.
- It does **not** change route selection.
- It does **not** decide whether a hallway becomes public, private, or mixed; hallway classification currently compares route counts.

## Multi-pass behavior

Pass 1 routes without traffic conflict penalties because hallway classifications do not yet exist.

Later passes:

- penalize public routes using private hallways,
- penalize private routes using public hallways,
- reclassify hallway hints from the newly resolved routes.

Execution stops when classifications stabilize or `max_routing_passes` is reached.

Recommended settings:

| Pass count | Use |
|---:|---|
| `2` | Minimum valid configuration and fast checks |
| `3` | Recommended default |
| `4-5` | R&D when classifications continue changing |
| `6-10` | Rarely useful; profile before using |

## Hallway classification

Final hallway classes are:

| Class | Meaning |
|---|---|
| `PUBLIC` | Used by more public routes than private routes |
| `PRIVATE` | Used by more private routes than public routes |
| `MIXED` | Equal public and private route counts |
| `UNCLASSIFIED` | A used hallway when only one hallway hint exists |
| `UNUSED` | Not used by any final route |

All original hallway identities appear in `hallway_classifications`, including `UNUSED` hallway hints.

`UNUSED` hallway points are removed from `result.points`.

## Route efficiency diagnostics

For each resolved route:

```text
path_efficiency_score =
    clamp(100 × Manhattan reference cost / routed total cost)
```

The overall debug score is:

```text
circulation_efficiency_score =
    weighted average of path_efficiency_score by importance_weight
```

These are diagnostic values only. They are not automatically included in Candidate Scoring.

## Output contracts

### `CandidateCirculationResult`

Always returned under `execution.result`:

```python
execution.result.points
execution.result.hallway_classifications
```

- `points`: original points minus final `UNUSED` hallway hints.
- `hallway_classifications`: classifications for every original hallway hint.

### `CandidateCirculationDetails`

Returned only in `DEBUG`:

```python
execution.details.circulation_efficiency_score
execution.details.routing_pass_count
execution.details.grid_node_count
execution.details.passes
execution.details.final_hallway_traffic
execution.details.removed_hallway_points
```

Each path detail includes nodes, costs, turn count, detour count, and path efficiency.

## Exceptions

| Exception | Typical cause |
|---|---|
| `CandidateCirculationInputError` | Missing room type, duplicate identity, overlap, missing endpoint type, or excessive grid size |
| `GridAlignmentError` | Grid extent or point coordinate does not align to the scale |
| `CirculationPathNotFoundError` | A required route cannot be resolved |
| `CandidateCirculationError` | Base feature exception |
| `TypeError` / `ValueError` | Invalid dataclass field or configuration value |

## Performance

Routing cost grows with:

- grid node count,
- number of route rules,
- expanded source/destination pairs,
- number of routing passes.

`ALL_MATCHING` may expand rapidly. For `S` sources and `D` destinations, it requests `S × D` routes.

Recommended optimization order:

1. increase grid scale,
2. reduce unnecessary `ALL_MATCHING` rules,
3. reduce routing passes,
4. simplify allowed transit behavior.

## Current limitations

- Orthogonal routing only.
- Grid-aligned hint points only.
- No diagonal movement.
- Hallway classification uses route counts, not importance weights.
- Traffic separation is a soft cost penalty, not a hard prohibition.
- The feature operates on hint points, not final room polygons.

---

# `fpg_core.candidate_scoring`

## Overview

Candidate Scoring evaluates candidate hint-point arrangements before deterministic floor-plan solving.

It supports:

- critical evaluators that may reject a candidate,
- quality evaluators combined into a normalized score,
- configurable evaluator order and weights,
- typed findings,
- production-safe results,
- detailed R&D data in `DEBUG` mode,
- custom evaluator registration.

Built-in evaluators:

- Zone Suitability
- Exterior Clearance
- Spatial Distribution
- Relationship Quality

Relationship Quality is opt-in because it requires project-specific route rules and grid settings.

## Public imports

```python
from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    CandidateScoreManager,
    EvaluatorCategory,
    EvaluatorRegistry,
    EvaluatorRule,
    ScoringConfig,
    ScoringResult,
    create_default_config,
    create_default_registry,
    evaluate_candidate,
)
```

Evaluator-specific configuration and keys are also public:

```python
from fpg_core.candidate_scoring import (
    DEFAULT_VALID_ZONES,
    EXTERIOR_CLEARANCE_KEY,
    RELATIONSHIP_QUALITY_KEY,
    SPATIAL_DISTRIBUTION_KEY,
    ZONE_SUITABILITY_KEY,
    ExteriorClearanceRule,
    RelationshipQualityConfig,
    ZoneSuitabilityConfig,
)
```

## Quick start with built-in defaults

```python
from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    create_default_config,
    create_default_registry,
    evaluate_candidate,
)
from fpg_core.domain import ExecutionMode

registry = create_default_registry()
config = create_default_config()

result = evaluate_candidate(
    CandidateScoringInput(
        specification=generation_spec,
        candidate=candidate_points,
    ),
    registry=registry,
    config=config,
    mode=ExecutionMode.PRODUCTION,
)

score = result.total_score
```

The default registry contains:

- `zone_suitability`
- `exterior_clearance`
- `spatial_distribution`

Default quality weights are:

```text
zone_suitability:     20
exterior_clearance:   20
spatial_distribution: 25
```

Because quality weights are normalized, their effective shares are approximately:

```text
30.77%, 30.77%, 38.46%
```

## Main operation

```python
evaluate_candidate(
    scoring_input: CandidateScoringInput,
    *,
    registry: EvaluatorRegistry,
    config: ScoringConfig,
    context_factory: ScoringContextFactory | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> ScoringResult
```

Unlike the other three documented features, Candidate Scoring currently returns `ScoringResult` directly rather than `FeatureExecution`.

## Input contract

### `CandidateScoringInput`

```python
CandidateScoringInput(
    specification: FloorPlanGenerationSpec,
    candidate: object,
    hallway_classifications: tuple[HallwayClassification, ...] = (),
)
```

### Supported candidate shapes

The built-in adapter accepts:

- a tuple or list of `CandidatePoint`,
- an object with `candidate_points`, `points`, or `positions`,
- a mapping of room IDs to point-like values,
- point-like objects or mappings with `x`, `y`, and room metadata,
- coordinate sequences where room metadata can be resolved elsewhere.

Recommended stable input:

```python
candidate: tuple[CandidatePoint, ...]
```

Candidate points require resolvable room type and finite coordinates.

Only hallway rooms may have multiple points with the same source room ID.

### Hallway classifications

Optional hallway tags use shared domain contracts:

```python
hallway_classifications=(
    HallwayClassification(...),
)
```

They currently affect Relationship Quality only.

An empty tuple means no hallway traffic restriction.

## Registry

### `EvaluatorRegistry`

```python
registry = EvaluatorRegistry((
    ZoneSuitabilityEvaluator(),
    ExteriorClearanceEvaluator(),
    SpatialDistributionEvaluator(),
    RelationshipQualityEvaluator(),
))
```

Methods:

```python
registry.register(evaluator)
registry.get(key)
registry.contains(key)
```

Evaluator keys must be unique.

## Scoring configuration

### `EvaluatorRule`

```python
EvaluatorRule(
    key: EvaluatorKey,
    category: EvaluatorCategory,
    enabled: bool = True,
    order: int = 0,
    weight: float = 1.0,
    minimum_score: float | None = None,
    settings: Mapping[str, Any] = {},
)
```

### Rule fields

| Field | Meaning |
|---|---|
| `key` | Stable registered evaluator key |
| `category` | `CRITICAL` or `QUALITY` |
| `enabled` | Whether the manager runs the evaluator |
| `order` | Execution order within the category |
| `weight` | Relative quality weight; required positive for quality evaluators |
| `minimum_score` | Required `0..100` threshold for critical evaluators |
| `settings` | Immutable evaluator-specific settings |

### `ScoringConfig`

```python
ScoringConfig(
    evaluator_rules: tuple[EvaluatorRule, ...],
    fail_fast_on_critical_failure: bool = True,
    not_applicable_quality_contributes: bool = False,
    raise_on_evaluator_error: bool = False,
)
```

### Recommended manager settings

#### Development

```python
ScoringConfig(
    evaluator_rules=rules,
    fail_fast_on_critical_failure=False,
    not_applicable_quality_contributes=False,
    raise_on_evaluator_error=True,
)
```

This exposes evaluator failures immediately and allows all critical checks to run.

#### Production search loop

```python
ScoringConfig(
    evaluator_rules=rules,
    fail_fast_on_critical_failure=True,
    not_applicable_quality_contributes=False,
    raise_on_evaluator_error=False,
)
```

This rejects quickly and returns structured evaluator errors.

#### Strict production

```python
ScoringConfig(
    evaluator_rules=rules,
    fail_fast_on_critical_failure=True,
    not_applicable_quality_contributes=False,
    raise_on_evaluator_error=True,
)
```

Use when evaluator failure must never be silently excluded from quality weighting.

## Manager behavior

### Critical evaluators

Critical evaluators run first in `(order, key)` order.

A critical check passes when:

- it returns `NOT_APPLICABLE`, or
- it returns `COMPLETED` with `score >= minimum_score`.

A failed or errored critical evaluator causes:

```text
total_score = 0
passed_critical_checks = False
stopped_early = True
```

When fail-fast is enabled, later evaluators are returned as `SKIPPED`.

### Quality evaluators

Eligible quality weights are normalized:

```text
normalized_weight = configured_weight / sum(eligible weights)
contribution = raw_score × normalized_weight
total_score = sum(contributions)
```

Only `COMPLETED` evaluators are eligible by default.

When `not_applicable_quality_contributes=True`, `NOT_APPLICABLE` evaluators enter the denominator with a raw contribution of zero.

### Important error behavior

With `raise_on_evaluator_error=False`:

- an evaluator exception becomes an `ERROR` result,
- an errored quality evaluator is excluded from the eligible-weight denominator,
- remaining quality evaluators are renormalized.

This can make a score look better after an evaluator fails. Use `raise_on_evaluator_error=True` while developing and wherever failure must invalidate the score.

## Recommended evaluator weights

Weights are relative. They do not need to total `100`.

### Balanced profile

| Evaluator | Weight |
|---|---:|
| Zone Suitability | `25` |
| Exterior Clearance | `20` |
| Spatial Distribution | `20` |
| Relationship Quality | `35` |

### Early exploration profile

| Evaluator | Weight |
|---|---:|
| Zone Suitability | `35` |
| Exterior Clearance | `20` |
| Spatial Distribution | `30` |
| Relationship Quality | `15` |

### Circulation-focused profile

| Evaluator | Weight |
|---|---:|
| Zone Suitability | `20` |
| Exterior Clearance | `15` |
| Spatial Distribution | `20` |
| Relationship Quality | `45` |

### General weight guidance

| Weight share | Suggested meaning |
|---:|---|
| `10%-20%` | Supporting preference |
| `20%-35%` | Normal major criterion |
| `35%-50%` | Dominant criterion |
| Above `50%` | Use only when the evaluator should control most ranking decisions |

Avoid assigning a high weight until the evaluator's score distribution has been measured across real candidate trials.

## Recommended critical thresholds

| Threshold | Interpretation |
|---:|---|
| `50-60` | Permissive rejection gate |
| `65-75` | Balanced gate |
| `80-90` | Strict gate |
| `100` | Exact satisfaction only |

Use a critical evaluator only for conditions that should reject the candidate. A strong preference normally belongs under `QUALITY` with a high weight instead.

---

## Zone Suitability

### Purpose

Scores whether selected room types occupy preferred normalized floor regions.

### Configuration

```python
ZoneSuitabilityConfig(
    grid_size: int = 3,
    falloff_multiplier: float = 1.5,
    valid_zones: Mapping[RoomType, tuple[tuple[int, int], ...]] = DEFAULT_VALID_ZONES,
)
```

Example:

```python
from fpg_core.candidate_scoring import ZoneSuitabilityConfig
from fpg_core.domain import RoomType

zone_config = ZoneSuitabilityConfig(
    grid_size=3,
    falloff_multiplier=1.5,
    valid_zones={
        RoomType.LIVING_ROOM: ((1, 1), (2, 1), (3, 1)),
        RoomType.KITCHEN: ((1, 3), (2, 3), (3, 3)),
        RoomType.BEDROOM: ((1, 2), (2, 2), (3, 2)),
    },
)
```

Pass it through:

```python
EvaluatorRule(
    key=ZONE_SUITABILITY_KEY,
    category=EvaluatorCategory.QUALITY,
    weight=25,
    settings={"zone_config": zone_config},
)
```

### Coordinate layout

For a `3 × 3` grid:

```text
(1,1) (2,1) (3,1)   low y / FRONT
(1,2) (2,2) (3,2)
(1,3) (2,3) (3,3)   high y / BACK
 low x         high x
 LEFT           RIGHT
```

### Formula

A point inside a preferred cell scores `100`.

Outside all preferred cells:

```text
score = clamp(100 × (1 - normalized_distance × falloff_multiplier))
```

Evaluator score:

```text
mean(point scores for room types with configured zones)
```

Multiple hallway hints are scored as separate points.

Room types absent from `valid_zones` are ignored.

### Recommended settings

| Setting | Suggested value | Guidance |
|---|---:|---|
| `grid_size` | `3` | Best default for broad architectural zones |
| `grid_size` | `4-5` | Finer control with more configuration |
| `falloff_multiplier` | `0.75-1.25` | Lenient |
| `falloff_multiplier` | `1.25-1.75` | Balanced; default `1.5` |
| `falloff_multiplier` | `2.0-3.0` | Strict |

The score reaches zero at approximately:

```text
normalized_distance = 1 / falloff_multiplier
```

Example at normalized distance `0.10`:

| Multiplier | Score |
|---:|---:|
| `1.0` | `90` |
| `1.5` | `85` |
| `2.0` | `80` |
| `3.0` | `70` |

### Default-zone note

`DEFAULT_VALID_ZONES` does not include every `RoomType`. In the current snapshot, bedrooms, dining rooms, and attached bathrooms are not scored unless the caller supplies zones for them.

### Findings

- `ROOM_OUTSIDE_PREFERRED_ZONE`
- `NO_ZONE_SCORABLE_ROOMS`

### DEBUG details

`ZoneSuitabilityDetails` includes normalized rules and per-point distances and scores.

---

## Exterior Clearance

### Purpose

Scores whether selected room hints have an unobstructed directional corridor to a floor boundary.

This is candidate-stage hint-point logic, not final room-polygon clearance.

### Rule configuration

```python
ExteriorClearanceRule(
    room_types: tuple[RoomType, ...],
    required_clear_room_count: int,
    clearance_width: float,
    direction: LandSide,
)
```

Example:

```python
from fpg_core.candidate_scoring import ExteriorClearanceRule
from fpg_core.domain import LandSide, RoomType

rules = (
    ExteriorClearanceRule(
        room_types=(RoomType.VERANDA,),
        required_clear_room_count=1,
        clearance_width=20,
        direction=LandSide.FRONT,
    ),
    ExteriorClearanceRule(
        room_types=(RoomType.KITCHEN, RoomType.DINING_ROOM),
        required_clear_room_count=1,
        clearance_width=20,
        direction=LandSide.BACK,
    ),
)
```

Pass through evaluator settings:

```python
settings={"rules": rules}
```

### Direction mapping

| Direction | Corridor extends toward |
|---|---|
| `FRONT` | `y = 0` |
| `BACK` | `y = floor_length` |
| `LEFT` | `x = 0` |
| `RIGHT` | `x = floor_width` |

### Corridor behavior

`clearance_width` is the corridor's cross-axis width. The implementation places half on each side of the hint coordinate.

Another room's hint point blocks the corridor when it lies inside or on the corridor bounds.

Points belonging to the same source room do not block each other.

A room with multiple hints qualifies when at least one hint is clear.

### Formula

Per applicable rule:

```text
rule_score =
    min(clear_room_count, required_clear_room_count)
    / required_clear_room_count
    × 100
```

Final evaluator score:

```text
mean(applicable rule scores)
```

Rules are equally weighted inside this evaluator.

### Recommended values

| Setting | Suggested range | Guidance |
|---|---:|---|
| `clearance_width` | `10-15` | Lenient, 1.0-1.5 m hint corridor |
| `clearance_width` | `20-30` | Balanced, 2.0-3.0 m |
| `clearance_width` | `30-40` | Strict or large-site profile |
| `required_clear_room_count` | `1` | At least one room in the group |
| `required_clear_room_count` | `2-3` | Several rooms must qualify |

Keep `required_clear_room_count` at or below the expected eligible room count. The class does not reject a larger value, but a score of `100` then becomes impossible.

Suggested starting rules:

| Intent | Room types | Count | Width | Direction |
|---|---|---:|---:|---|
| Main entrance exposure | `VERANDA` | `1` | `20` | `FRONT` |
| Garage access | `GARAGE` | `1` | `25-35` | `FRONT` |
| Rear service exposure | `KITCHEN`, `DINING_ROOM` | `1` | `15-25` | `BACK` |

### Findings

- `NO_EXTERIOR_CLEARANCE_RULES`
- `NO_ELIGIBLE_EXTERIOR_CLEARANCE_ROOMS`
- `EXTERIOR_CLEARANCE_REQUIREMENT_UNMET`

### DEBUG details

`ExteriorClearanceDetails` contains:

- per-rule scores,
- eligible and clear room counts,
- per-room qualification,
- corridor bounds,
- blocking point IDs,
- selected scoring hints.

---

## Spatial Distribution

### Purpose

Scores anti-clumping and whole-floor point coverage.

### Settings

```python
settings={
    "nnd_weight": 0.40,
    "coverage_weight": 0.60,
    "nnd_cv_sensitivity": 8.0,
    "grid_size": 20,
    "gap_zero_score_ratio": 1.5,
}
```

Weights are normalized internally, so `40/60` and `0.4/0.6` are equivalent.

### Combined score

```text
final_score =
    nnd_score × normalized_nnd_weight
    + coverage_score × normalized_coverage_weight
```

### Nearest-neighbor component

The evaluator calculates nearest distances using candidate points and fixed boundary anchors.

```text
CV = nearest-distance standard deviation / mean nearest distance
nnd_score = 100 × exp(-CV × nnd_cv_sensitivity)
```

### Sensitivity recommendations

| Sensitivity | Behavior |
|---:|---|
| `2-3` | Lenient |
| `4-6` | Balanced |
| `8` | Current default and strict |
| `10+` | Usually overly harsh |

Example with `CV = 0.20`:

| Sensitivity | Approximate score |
|---:|---:|
| `2` | `67` |
| `4` | `45` |
| `6` | `30` |
| `8` | `20` |

Recommended normal starting value:

```python
nnd_cv_sensitivity=4.0
```

Use `8.0` only when strong spacing uniformity is intentional.

### Coverage component

A square sampling grid measures distance to the nearest candidate point.

The 95th-percentile gap is compared with:

```text
theoretical_gap = sqrt(floor_area / point_count) / sqrt(2)
gap_ratio = coverage_gap_95 / theoretical_gap
```

Coverage score:

```text
100 × (1 - (gap_ratio - 1) / (gap_zero_score_ratio - 1))
```

The result is clamped to `0..100`.

### `gap_zero_score_ratio`

Must be greater than `1.0`.

| Value | Behavior |
|---:|---|
| `1.25-1.40` | Strict |
| `1.50-1.70` | Balanced; default `1.5` |
| `1.80-2.00` | Lenient |

### Sampling grid size

Approximate cost:

```text
grid_size² × candidate_point_count
```

| Grid size | Use |
|---:|---|
| `12-16` | Fast search-loop scoring |
| `20-30` | Balanced; default `20` |
| `40-60` | Detailed post-search DEBUG analysis |

Recommended search-loop value:

```python
grid_size=16
```

Recommended balanced value:

```python
grid_size=20
```

### Weight recommendations

| Profile | NND | Coverage |
|---|---:|---:|
| Spacing-focused | `0.60` | `0.40` |
| Balanced | `0.40` | `0.60` |
| Coverage-focused | `0.25` | `0.75` |

### Findings

- `NO_CANDIDATE_POINTS`
- `IRREGULAR_POINT_SPACING` when coefficient of variation exceeds `0.8`
- `LARGE_UNCOVERED_REGION` when gap ratio exceeds `1.3`

### DEBUG details

`SpatialDistributionDetails` includes:

- candidate points,
- nearest-distance sampling matrix,
- ideal point distance,
- theoretical gap,
- configured grid size,
- zero-score ratio.

---

## Relationship Quality

### Purpose

Scores the efficiency and reachability of configured room relationships using one orthogonal routing pass.

It uses shared routing contracts but does not call or import Candidate Circulation internals.

### Registration

Relationship Quality is not in the default registry.

```python
from fpg_core.candidate_scoring import (
    EvaluatorRegistry,
    RelationshipQualityEvaluator,
    create_default_registry,
)

registry = create_default_registry()
registry.register(RelationshipQualityEvaluator())
```

### Configuration

```python
RelationshipQualityConfig(
    grid: CirculationGrid,
    costs: GridRoutingCostProfile,
    route_rules: tuple[CirculationRouteRule, ...],
    always_traversable_room_types: tuple[RoomType, ...] = (RoomType.HALLWAY,),
)
```

Example:

```python
from fpg_core.candidate_scoring import RelationshipQualityConfig
from fpg_core.domain import (
    CirculationGrid,
    CirculationRouteRule,
    CirculationTrafficClass,
    DestinationSelection,
    GridRoutingCostProfile,
    RoomType,
)

relationship_config = RelationshipQualityConfig(
    grid=CirculationGrid(width=100, length=80, scale=5),
    costs=GridRoutingCostProfile(
        empty_node_cost=2.0,
        traversable_hint_node_cost=1.0,
        turn_cost=0.25,
        perimeter_bias_max_cost=0.20,
    ),
    route_rules=(
        CirculationRouteRule(
            id=1,
            name="Living to bedrooms",
            source_room_type=RoomType.LIVING_ROOM,
            destination_room_type=RoomType.BEDROOM,
            destination_selection=DestinationSelection.ALL_MATCHING,
            traffic_class=CirculationTrafficClass.PRIVATE,
            allowed_transit_room_types=(),
            importance_weight=2.0,
        ),
    ),
)
```

Evaluator rule:

```python
EvaluatorRule(
    key=RELATIONSHIP_QUALITY_KEY,
    category=EvaluatorCategory.QUALITY,
    weight=35,
    settings={"routing_config": relationship_config},
)
```

### Validation

- Grid width and length must match the specification floor exactly.
- Grid extents must be exact multiples of scale.
- Candidate points must align with the grid.
- Candidate points may not overlap.
- Grid size may not exceed `250,000` nodes.
- Rules with absent endpoint room types are inactive rather than errors.

### Route score

```text
path_efficiency_score =
    clamp(100 × Manhattan reference cost / routed total cost)
```

Final score:

```text
sum(resolved path score × importance_weight)
/ total expected route weight
```

Missing expected routes remain in the denominator and therefore contribute zero.

### Destination expansion

For `ALL_MATCHING`, expected weight is added for every source/destination pair.

For `LOWEST_COST_MATCH`, expected weight is added once per source.

A rule with many matching destinations can dominate the evaluator. Choose weights with expanded route count in mind.

### Hallway restrictions

When matching hallway classifications are supplied:

| Route class | Allowed hallway classes |
|---|---|
| Public | `PUBLIC`, `MIXED`, `UNCLASSIFIED`, or untagged |
| Private | `PRIVATE`, `MIXED`, `UNCLASSIFIED`, or untagged |
| Any | `UNUSED` is blocked |

Unlike Candidate Circulation, these are hard traversal restrictions rather than conflict penalties.

### Recommended routing costs

```python
GridRoutingCostProfile(
    empty_node_cost=2.0,
    traversable_hint_node_cost=1.0,
    turn_cost=0.25,
    perimeter_bias_max_cost=0.20,
)
```

Recommended ranges:

| Setting | Suggested range |
|---|---:|
| `empty_node_cost` | `1.0-3.0` |
| `traversable_hint_node_cost` | `0.5-1.5` |
| `turn_cost` | `0.10-0.50` |
| `perimeter_bias_max_cost` | `0.00-0.30` |

### Recommended importance weights

| Weight | Meaning |
|---:|---|
| `0.5` | Minor preference |
| `1.0` | Standard relationship |
| `2.0` | Important relationship |
| `3.0-5.0` | Dominant soft requirement |

### Findings

- `NO_ACTIVE_RELATION_ROUTES`
- `RELATION_PATH_MISSING`

### DEBUG details

`RelationshipQualityDetails` contains:

- grid node count,
- aggregate path efficiency,
- resolved path geometry and costs,
- failed route records.

---

## Full custom scoring example

```python
from fpg_core.candidate_scoring import (
    EXTERIOR_CLEARANCE_KEY,
    RELATIONSHIP_QUALITY_KEY,
    SPATIAL_DISTRIBUTION_KEY,
    ZONE_SUITABILITY_KEY,
    EvaluatorCategory,
    EvaluatorRegistry,
    EvaluatorRule,
    ExteriorClearanceEvaluator,
    RelationshipQualityEvaluator,
    ScoringConfig,
    SpatialDistributionEvaluator,
    ZoneSuitabilityEvaluator,
)

registry = EvaluatorRegistry((
    ZoneSuitabilityEvaluator(),
    ExteriorClearanceEvaluator(),
    SpatialDistributionEvaluator(),
    RelationshipQualityEvaluator(),
))

config = ScoringConfig(
    evaluator_rules=(
        EvaluatorRule(
            key=ZONE_SUITABILITY_KEY,
            category=EvaluatorCategory.QUALITY,
            order=10,
            weight=25,
            settings={"zone_config": zone_config},
        ),
        EvaluatorRule(
            key=EXTERIOR_CLEARANCE_KEY,
            category=EvaluatorCategory.QUALITY,
            order=20,
            weight=20,
            settings={"rules": clearance_rules},
        ),
        EvaluatorRule(
            key=SPATIAL_DISTRIBUTION_KEY,
            category=EvaluatorCategory.QUALITY,
            order=30,
            weight=20,
            settings={
                "nnd_weight": 0.40,
                "coverage_weight": 0.60,
                "nnd_cv_sensitivity": 4.0,
                "grid_size": 20,
                "gap_zero_score_ratio": 1.6,
            },
        ),
        EvaluatorRule(
            key=RELATIONSHIP_QUALITY_KEY,
            category=EvaluatorCategory.QUALITY,
            order=40,
            weight=35,
            settings={"routing_config": relationship_config},
        ),
    ),
    fail_fast_on_critical_failure=True,
    not_applicable_quality_contributes=False,
    raise_on_evaluator_error=True,
)
```

## Output contracts

### `ScoringResult`

```python
result.total_score
result.passed_critical_checks
result.stopped_early
result.stop_reason
result.evaluator_results
result.findings
```

### `EvaluatorExecutionResult`

```python
execution.evaluator_key
execution.category
execution.status
execution.raw_score
execution.configured_weight
execution.normalized_weight
execution.contribution
execution.threshold
execution.passed_threshold
execution.findings
execution.metrics
execution.details
```

Statuses:

```python
EvaluationStatus.COMPLETED
EvaluationStatus.NOT_APPLICABLE
EvaluationStatus.SKIPPED
EvaluationStatus.ERROR
```

In `PRODUCTION`, evaluator `metrics` must be empty and `details` must be `None`.

## Custom evaluators

Implement `CandidateEvaluator`:

```python
class MyEvaluator(CandidateEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return EvaluatorKey("my_evaluator")

    def evaluate(self, context, settings) -> EvaluatorResult:
        return EvaluatorResult(
            evaluator_key=self.key,
            status=EvaluationStatus.COMPLETED,
            score=75.0,
        )
```

Contract requirements:

- Completed scores must be finite and between `0` and `100`.
- Non-completed results must have `score=None`.
- Returned key must match the registered/configured key.
- Production evaluators may not return metrics or details.

## Exceptions

| Exception | Typical cause |
|---|---|
| `ScoringConfigurationError` | Invalid rule, missing registry entry, duplicate key, or no positive quality weight |
| `ScoringInputError` | Structurally invalid specification or candidate |
| `EvaluatorContractError` | Evaluator returned an invalid result |
| `EvaluatorRegistrationError` | Duplicate or missing evaluator registration |
| `CandidateScoringError` | Base framework exception |

## Performance

Primary cost drivers:

- number of evaluators,
- Spatial Distribution sampling grid size,
- Relationship Quality grid node count,
- expanded relationship route count,
- amount of `DEBUG` detail collected.

Recommended search-loop setup:

- `PRODUCTION` mode,
- Spatial Distribution grid `12-20`,
- relationship scale `5-10`,
- only necessary relationship rules,
- `raise_on_evaluator_error=True` during tuning.

## Current limitations

- Candidate Scoring returns `ScoringResult`, not `FeatureExecution`.
- Candidate input is intentionally flexible and typed as `object`; prefer canonical `CandidatePoint` tuples.
- Built-in evaluators score hint points, not final room polygons.
- Relationship Quality duplicates routing logic intentionally to avoid feature-to-feature coupling.
- Default zone rules do not cover every room type.
- Exterior Clearance rules have equal internal weight.

---

# `fpg_core.candidate_search`

## Overview

Candidate Search uses an Optuna TPE study to maximize a caller-provided score over room hint-point positions.

The feature does not know how points are evaluated. The evaluator callback is an application- or algorithm-level extension point.

### Main responsibilities

- Sample grid-aligned room hint coordinates.
- Give each non-hallway target exactly one point.
- Sample a configurable number of hints for each hallway target.
- Maximize a finite numeric evaluator score.
- Support one-shot and incremental trial orchestration.
- Preserve deterministic sampling when a fixed seed is used.

## Public imports

```python
from fpg_core.candidate_search import (
    CandidateEvaluator,
    CandidatePoint,
    CandidateSearchInput,
    CandidateSearchResult,
    CandidateSearchSession,
    CandidateSearchSettings,
    CandidateSearchStateError,
    CandidateSearchTarget,
    CandidateSuggestion,
    CandidateTrialResult,
    search_candidates,
)
```

The feature also exports:

```python
DEFAULT_MIN_HALLWAY_HINT_COUNT  # 1
DEFAULT_MAX_HALLWAY_HINT_COUNT  # 5
CandidateSearchConfig
```

`CandidateSearchSettings` is the configuration consumed by the public search operation and session. `CandidateSearchConfig` currently contains only hallway-count fields and is not used by those entry points.

## Quick start

```python
from fpg_core.candidate_search import (
    CandidateSearchInput,
    CandidateSearchSettings,
    CandidateSearchTarget,
    search_candidates,
)
from fpg_core.domain import ExecutionMode, RoomType


def evaluator(points):
    # Candidate Search accepts any finite numeric value and maximizes it.
    return 100.0


search_input = CandidateSearchInput(
    targets=(
        CandidateSearchTarget("living", RoomType.LIVING_ROOM),
        CandidateSearchTarget("bedroom_1", RoomType.BEDROOM),
        CandidateSearchTarget("hallway", RoomType.HALLWAY),
    ),
    settings=CandidateSearchSettings(
        min_x=0,
        max_x=100,
        min_y=0,
        max_y=80,
        grid_resolution=5,
        trial_count=200,
        random_seed=7,
        min_hallway_hint_count=1,
        max_hallway_hint_count=4,
    ),
    evaluator=evaluator,
)

execution = search_candidates(
    search_input,
    mode=ExecutionMode.PRODUCTION,
)

best_points = execution.result.points
best_score = execution.result.score
```

## One-shot operation

```python
search_candidates(
    search_input: CandidateSearchInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[CandidateSearchResult, None]
```

The operation runs trials until `trial_count` completed trials have been recorded.

Candidate-search-specific details are not implemented, so `execution.details` is `None` in both modes.

## Target contract

### `CandidateSearchTarget`

```python
CandidateSearchTarget(
    room_id: RoomId,
    room_type: RoomType | None = None,
)
```

Requirements:

- `room_id` must be a non-empty string.
- Target room IDs must be unique.
- `room_type`, when supplied, must be a `RoomType`.

A target is treated as a hallway only when:

```python
target.room_type is RoomType.HALLWAY
```

Always provide `room_type` when downstream logic depends on typed points.

## Settings contract

### `CandidateSearchSettings`

```python
CandidateSearchSettings(
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
    grid_resolution: float,
    trial_count: int,
    random_seed: int | None = None,
    min_hallway_hint_count: int = 1,
    max_hallway_hint_count: int = 5,
)
```

### Validation rules

- Bounds and resolution must be finite.
- Minimum bounds may equal maximum bounds.
- Minimum bounds may not exceed maximum bounds.
- `grid_resolution` must be greater than zero.
- `trial_count` must be a positive integer.
- Hallway hint counts must be positive integers.
- Minimum hallway count may not exceed maximum.
- `random_seed` must be an integer or `None`.

## Search-space behavior

Coordinates are generated as:

```text
minimum + integer_index × grid_resolution
```

Maximum index is calculated using floor division.

When the span is not exactly divisible by the resolution, the largest sampled coordinate is below the configured maximum.

Example:

```text
min = 0
max = 12
resolution = 5
reachable values = 0, 5, 10
```

The maximum bound is conceptually inclusive only when it lies on the grid.

## Hallway hint sampling

Every non-hallway target receives exactly one point.

Each hallway target first samples a hint count, then samples that many coordinates.

Do not duplicate a hallway target to request multiple hints. Use one hallway target and the configured hint-count range.

### Recommended hallway ranges

| Range | Use |
|---|---|
| `1-2` | Small/simple plans |
| `1-3` | Conservative normal profile |
| `1-4` | Recommended balanced profile |
| `1-5` | Current broad defaults |
| Above `5` | Only when later features explicitly benefit |

More hallway hints add search dimensions and increase overlap and cleanup work.

## Grid-resolution recommendations

| Resolution | Real-world step | Use |
|---:|---:|---|
| `10` | 1.0 m | Smoke tests and coarse exploration |
| `5` | 0.5 m | Recommended balanced default |
| `2` | 0.2 m | Fine R&D search |
| `1` | 0.1 m | Expensive detailed exploration |

Recommended starting value:

```python
grid_resolution=5.0
```

Use a resolution compatible with any later grid-based feature. Exact equality with the later routing scale is the safest option.

## Trial-count recommendations

| Trials | Use |
|---:|---|
| `20-50` | Smoke tests |
| `100-300` | Normal development |
| `300-1000` | Medium-size R&D searches |
| `1000+` | Deep exploration when evaluation is cheap enough |

Recommended baseline:

```python
trial_count=200
```

Increase trial count when:

- room count increases,
- hallway hint range increases,
- resolution becomes finer,
- bounds become larger,
- evaluator behavior is discontinuous,
- score improvements are still occurring near the final trials.

### Approximate search dimensionality

For each non-hallway target:

```text
2 integer parameters: x and y
```

For a hallway target with sampled hint count `H`:

```text
1 count parameter + 2H coordinate parameters
```

This is why broad hallway-count ranges can make the study substantially harder.

## Evaluator contract

```python
CandidateEvaluator = Callable[[tuple[CandidatePoint, ...]], float]
```

The returned value must be:

- numeric,
- finite,
- not boolean.

The study maximizes the value.

Candidate Search does not enforce a `0..100` range.

### Recommended score convention

```text
0      = invalid or unusable candidate
1-49   = poor
50-69  = acceptable
70-84  = good
85-100 = strong
```

Keep the evaluator deterministic for the same points where possible. A noisy objective reduces reproducibility and makes TPE convergence harder to interpret.

## Invalid candidates

Candidate Search does not reject:

- overlapping coordinates,
- blocked circulation,
- poor zoning,
- geometrically impossible room arrangements,
- duplicate coordinates across different room IDs.

The evaluator must penalize or reject those cases.

Recommended callback pattern:

```python
def evaluator(points):
    try:
        return evaluate_valid_candidate(points)
    except ExpectedCandidateFailure:
        return 0.0
```

Unexpected programming errors should normally propagate during development.

## Incremental session API

Use `CandidateSearchSession` when external work must occur between suggestion and scoring.

```python
from fpg_core.candidate_search import CandidateSearchSession

session = CandidateSearchSession(search_input)

while session.has_remaining_trials:
    suggestion = session.ask_next_trial()
    try:
        score = evaluator(suggestion.points)
        trial_result = session.record_score(suggestion, score)
    except Exception:
        session.fail_pending_trial()
        raise

best = session.best_result()
```

### Session properties

```python
session.search_input
session.completed_trials
session.remaining_trials
session.has_remaining_trials
session.has_pending_trial
```

### Lifecycle methods

| Method | Purpose |
|---|---|
| `ask_next_trial()` | Create one unscored suggestion |
| `record_score(suggestion, score)` | Complete the pending trial |
| `fail_pending_trial()` | Mark the pending Optuna trial failed |
| `run_next_trial()` | Ask, call the stored evaluator, and record |
| `best_result()` | Return the highest-scoring completed result |

Rules:

- Only one trial may be pending.
- Record or fail it before asking for another.
- `best_result()` requires at least one completed trial.
- A failed trial does not increment `completed_trials`.
- The suggestion passed to `record_score()` must equal the pending suggestion.

## Result contracts

### `CandidateSuggestion`

```python
suggestion.trial_number
suggestion.points
```

### `CandidateTrialResult`

```python
trial_result.trial_number
trial_result.points
trial_result.score
trial_result.completed_trials
```

### `CandidateSearchResult`

```python
result.points
result.score
result.completed_trials
```

Only hallway rooms may contain multiple points sharing a room ID, and their hint indices must be unique.

## Random seed and reproducibility

Recommended behavior:

- fixed integer for tests and controlled comparisons,
- `None` for intentionally varied runs.

Example:

```python
random_seed=7
```

Reproducibility also depends on:

- Optuna version,
- target order,
- settings,
- evaluator behavior,
- exact trial lifecycle call order.

## Exceptions

| Exception | Typical cause |
|---|---|
| `CandidateSearchStateError` | Invalid session lifecycle or missing completed trial |
| `CandidateSearchError` | Base feature exception |
| `TypeError` | Invalid contract type or evaluator return type |
| `ValueError` | Invalid range, count, non-finite score, or candidate structure |

Evaluator exceptions propagate after the pending Optuna trial is marked failed.

## Performance

Total runtime is approximately:

```text
trial_count × evaluator runtime
```

Sampling itself is usually cheaper than candidate scoring, circulation, or solver execution.

Recommended tuning order:

1. use a coarse grid,
2. use `100-300` trials,
3. restrict hallway hints to `1-3` or `1-4`,
4. profile evaluator cost,
5. then increase resolution or trial count.

## Current limitations

- No timeout or wall-clock budget field.
- No pruning API exposed by the feature.
- No persistent Optuna storage.
- No search details under `ExecutionMode.DEBUG`.
- TPE sampler settings beyond `seed` are not configurable.
- Search constraints are expressed only through evaluator scores.

---

# `fpg_core.floor_plan_preprocessing`

## Overview

Floor Plan Preprocessing converts a client-facing room request and one reference/configuration object into a validated canonical `FloorPlanGenerationSpec`.

The feature is deterministic, request-independent, and has no external side effects.

### Main responsibilities

- Validate client room types and room counts.
- Parse and canonicalize requested aspect ratio.
- Generate missing room IDs and names.
- Normalize room-size labels.
- Apply room-size selection policy.
- Enforce mandatory room types.
- Validate attached-bathroom count.
- Derive hallways.
- Resolve room-size references.
- Select floor dimensions.
- Expand room-type relations to room-ID relations.
- Validate the final generation specification.
- Return detailed decisions in `DEBUG` mode.

## Public imports

```python
from fpg_core.floor_plan_preprocessing import (
    AspectRatioRule,
    ExcessAttachedBathroomPolicy,
    FloorLimits,
    PreprocessingConfig,
    PreprocessingInput,
    PreprocessingRequest,
    RequestedRoom,
    RoomCountRule,
    RoomRelationReference,
    RoomSizeReference,
    RoomSizeSelectionStrategy,
    prepare_generation_input,
)
```

`PreprocessingPolicy` and `PreprocessingReferenceData` are compatibility aliases for `PreprocessingConfig`.

## Quick start

```python
from fpg_core.domain import (
    ConstraintStrength,
    ExecutionMode,
    MatchPolicy,
    RoomType,
)
from fpg_core.floor_plan_preprocessing import (
    AspectRatioRule,
    ExcessAttachedBathroomPolicy,
    FloorLimits,
    PreprocessingConfig,
    PreprocessingInput,
    PreprocessingRequest,
    RequestedRoom,
    RoomCountRule,
    RoomRelationReference,
    RoomSizeReference,
    prepare_generation_input,
)

request = PreprocessingRequest(
    floor_limits=FloorLimits(max_width=120, max_length=100),
    aspect_ratio="1:1",
    rooms=(
        RequestedRoom(RoomType.LIVING_ROOM, id="living"),
        RequestedRoom(RoomType.KITCHEN, id="kitchen"),
        RequestedRoom(RoomType.BEDROOM, id="bedroom_1"),
        RequestedRoom(RoomType.BEDROOM, id="bedroom_2"),
        RequestedRoom(RoomType.BATHROOM, id="bathroom"),
    ),
)

config = PreprocessingConfig(
    room_count_rules=(
        RoomCountRule(RoomType.LIVING_ROOM, 1, 1),
        RoomCountRule(RoomType.KITCHEN, 1, 1),
        RoomCountRule(RoomType.BEDROOM, 1, 4),
        RoomCountRule(RoomType.BATHROOM, 1, 2),
        RoomCountRule(RoomType.ATTACHED_BATHROOM, 0, 4),
        RoomCountRule(RoomType.DINING_ROOM, 0, 1),
        RoomCountRule(RoomType.VERANDA, 0, 1),
        RoomCountRule(RoomType.GARAGE, 0, 1),
        RoomCountRule(
            RoomType.HALLWAY,
            0,
            0,
            client_selectable=False,
        ),
    ),
    supported_aspect_ratios=(
        AspectRatioRule("1:1", 1.0),
        AspectRatioRule("4:3", 4 / 3),
        AspectRatioRule("3:2", 1.5),
    ),
    room_sizes=(
        RoomSizeReference(RoomType.LIVING_ROOM, "medium", 35, 55, 1400, 2600),
        RoomSizeReference(RoomType.KITCHEN, "medium", 28, 45, 900, 1600),
        RoomSizeReference(RoomType.BEDROOM, "medium", 28, 42, 900, 1600),
        RoomSizeReference(RoomType.BATHROOM, "medium", 18, 30, 350, 700),
        RoomSizeReference(
            RoomType.ATTACHED_BATHROOM,
            "medium",
            18,
            30,
            350,
            700,
        ),
        RoomSizeReference(RoomType.DINING_ROOM, "medium", 28, 45, 800, 1500),
        RoomSizeReference(RoomType.VERANDA, "medium", 20, 50, 500, 1200),
        RoomSizeReference(RoomType.GARAGE, "medium", 28, 60, 1500, 3000),
    ),
    room_relations=(
        RoomRelationReference(
            source_room_type=RoomType.ATTACHED_BATHROOM,
            target_room_types=(RoomType.BEDROOM,),
            match_policy=MatchPolicy.AND,
            strength=ConstraintStrength.HARD,
            required=True,
        ),
    ),
    mandatory_room_types=(
        RoomType.LIVING_ROOM,
        RoomType.KITCHEN,
        RoomType.BEDROOM,
        RoomType.BATHROOM,
    ),
    floor_area_buffer=800,
    hallway_area_buffer=500,
    hallway_count=1,
    hallway_min_width=10,
    default_room_size="medium",
    min_aspect_ratio=0.75,
    max_aspect_ratio=1.5,
    excess_attached_bathrooms=ExcessAttachedBathroomPolicy.REJECT,
)

execution = prepare_generation_input(
    PreprocessingInput(request=request, config=config),
    mode=ExecutionMode.PRODUCTION,
)

generation_spec = execution.result.generation_spec
```

## Main operation

```python
prepare_generation_input(
    input: PreprocessingInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> PreprocessingExecution
```

Return type:

```text
FeatureExecution[PreparedGenerationInput, PreprocessingReport]
```

## Request contracts

### `FloorLimits`

```python
FloorLimits(
    max_width: float,
    max_length: float,
)
```

Both values must be finite and greater than zero.

They are maximum permitted floor dimensions, not guaranteed output dimensions.

### `RequestedRoom`

```python
RequestedRoom(
    room_type: RoomType,
    id: str | None = None,
    name: str | None = None,
    requested_size: str | None = None,
)
```

Missing values:

- ID becomes `<room_type>_<number>`.
- Name is generated from the final ID.
- Size participates in the configured size-selection strategy.

### `PreprocessingRequest`

```python
PreprocessingRequest(
    floor_limits: FloorLimits,
    aspect_ratio: float | str,
    rooms: tuple[RequestedRoom, ...],
)
```

At least one room is required.

## Aspect ratio

String ratios use:

```text
first part / second part
```

The resulting value is then applied as:

```text
selected_length = selected_width × aspect_ratio
```

Example:

```text
"4:3" -> 4 / 3 -> length is 1.333... × width
```

The requested numeric ratio must match one configured `AspectRatioRule.canonical_value` within tolerance `1e-6`.

It must also lie between `min_aspect_ratio` and `max_aspect_ratio`.

### Recommended aspect ratios

| Ratio | Use |
|---:|---|
| `1.0` | Square floor |
| `1.2-1.35` | Moderately elongated |
| `1.5` | Clearly elongated |
| Below `0.75` or above `1.75` | Use only for intentionally unusual plots |

Recommended policy bounds:

```python
min_aspect_ratio=0.75
max_aspect_ratio=1.50
```

Keep `supported_aspect_ratios` narrow and intentional rather than accepting arbitrary values.

## Room count rules

### `RoomCountRule`

```python
RoomCountRule(
    room_type: RoomType,
    minimum: int,
    maximum: int,
    client_selectable: bool = True,
)
```

Only client-selectable rules participate in request count validation and allowed-client-type checks.

Recommended approach:

- `minimum=0` for optional room types.
- `minimum=1` for required client-supplied types.
- Keep maximums aligned with solver capacity.
- Mark derived room types such as hallways as `client_selectable=False`.

The dataclass itself does not currently validate `minimum >= 0` or `maximum >= minimum`; configuration authors must maintain these invariants.

### Recommended single-story count ranges

| Room type | Suggested minimum | Suggested maximum |
|---|---:|---:|
| Living room | `1` | `1` |
| Kitchen | `1` | `1` |
| Dining room | `0` | `1` |
| Bedroom | `1` | `4-5` |
| Bathroom | `1` | `2-3` |
| Attached bathroom | `0` | bedroom maximum |
| Veranda | `0` | `1-2` |
| Garage | `0` | `1` |
| Hallway | `0` | `0`, not client selectable |

These are package-tuning suggestions, not regulatory limits.

## Room-size references

### `RoomSizeReference`

```python
RoomSizeReference(
    room_type: RoomType,
    size: str,
    min_width: float,
    max_width: float,
    min_area: float,
    max_area: float,
)
```

Requirements:

- Positive finite width and area values.
- `min_width <= max_width`.
- `min_area <= max_area`.
- `max_area >= min_width²`.
- Unique `(room_type, normalized size label)` pair.

Size labels are normalized to lowercase underscore format:

```text
"Medium Room" -> "medium_room"
"large-room"  -> "large_room"
```

### Recommended residential starting ranges

| Room type | Width range | Area range | Approx. metric area |
|---|---:|---:|---:|
| Bedroom | `27-42` | `900-1600` | `9-16 m²` |
| Bathroom | `18-30` | `350-700` | `3.5-7 m²` |
| Attached bathroom | `18-30` | `350-700` | `3.5-7 m²` |
| Living room | `32-55` | `1400-2600` | `14-26 m²` |
| Kitchen | `24-45` | `800-1600` | `8-16 m²` |
| Dining room | `24-45` | `700-1500` | `7-15 m²` |
| Veranda | `15-50` | `400-1200` | `4-12 m²` |
| Garage | `28-60` | `1500-3000` | `15-30 m²` |

Use these only as initial solver/search profiles. Local standards, household needs, and the solver's geometric model must determine production values.

### Width axis behavior

Prepared rooms use:

- `RoomWidthAxis.X` for garage and veranda,
- `RoomWidthAxis.ANY` for other room types.

## Room-size selection

Only one strategy currently exists:

```python
RoomSizeSelectionStrategy.MAJORITY
```

Behavior:

1. Ignore room types listed in `size_normalization_exclusions`.
2. Count non-empty requested size labels.
3. Select the most common label.
4. If tied, use `default_room_size` when it is one of the tied labels.
5. Otherwise choose the lexicographically first tied label.
6. Apply the selected label to every non-excluded room.

This means individual non-excluded room size requests are normalized to one shared selected size.

Recommended configuration:

```python
size_normalization_exclusions=(RoomType.HALLWAY,)
default_room_size="medium"
```

Every room type that may survive preprocessing should have a reference for every size label that may become the selected majority.

## Mandatory room types

```python
mandatory_room_types=(
    RoomType.LIVING_ROOM,
    RoomType.KITCHEN,
    RoomType.BEDROOM,
    RoomType.BATHROOM,
)
```

Mandatory room types are validated but not automatically inserted.

Hallways are added later. Do not normally include `RoomType.HALLWAY` in `mandatory_room_types`, because the mandatory check occurs before hallway derivation.

## Hallway configuration

Fields:

```python
hallway_count: int
hallway_area_buffer: float
hallway_min_width: float
```

### Behavior

`hallway_count` is the number of new hallway rooms added by policy. It is not merely a minimum-total check.

Recommended practice:

- prevent clients from supplying hallways,
- derive them only through `hallway_count`.

Hallway IDs are generated as:

```text
hallway_1
hallway_2
...
```

The hallway room size is generated as:

```text
min_area = hallway_area_buffer
max_area = selected floor area
min/max width derived from hallway_min_width and hallway_area_buffer
```

### Recommended values

| Field | Suggested range | Guidance |
|---|---:|---|
| `hallway_count` | `1` | Normal single-story start |
| `hallway_count` | `0` | Explicit open-plan/no-hallway experiments |
| `hallway_count` | `2` | Larger or split circulation layouts |
| `hallway_min_width` | `10-12` | 1.0-1.2 m starting range |
| `hallway_area_buffer` | `400-800` | 4-8 m² per derived hallway |

`hallway_area_buffer` must be positive even when `hallway_count=0`.

## Floor-area buffer

```python
floor_area_buffer: float
```

This is an absolute area value, not a percentage.

Recommended calculation:

```python
summed_minimum_area = sum(selected room minimum areas)
floor_area_buffer = summed_minimum_area * 0.10
```

Recommended range:

```text
5%-15% of summed non-hallway minimum room area
```

Convert the percentage to square project units before storing it in the config.

Typical starting values for small/medium plans:

```text
500-1500 square project units
5-15 m²
```

## Floor selection formula

The feature calculates:

```text
minimum_required_area =
    sum(non-hallway minimum areas)
    + derived hallway count × hallway_area_buffer
    + floor_area_buffer

maximum_target_area =
    sum(non-hallway maximum areas)
    + derived hallway count × hallway_area_buffer
    + floor_area_buffer
```

Then:

```text
width = min(
    request.max_width,
    request.max_length / aspect_ratio,
    sqrt(maximum_target_area / aspect_ratio),
)

length = width × aspect_ratio
```

The selected floor must still satisfy `minimum_required_area`.

It also must accommodate every room's minimum width and configured hallway dimensions.

The selected dimensions are not quantized to any later routing or solver grid. Configure compatible floor limits, aspect ratios, and room references when exact grid divisibility is required elsewhere.

## Room relations

### `RoomRelationReference`

```python
RoomRelationReference(
    source_room_type: RoomType,
    target_room_types: tuple[RoomType, ...],
    match_policy: MatchPolicy | str,
    strength: ConstraintStrength | str,
    required: bool = True,
)
```

`match_policy` and `strength` strings are normalized into shared domain enums.

### Expansion behavior

For every source room, matching target room types are expanded to concrete room IDs.

- `required=True`: missing target type raises `RelationPreparationError`.
- `required=False`: unusable relation is omitted.
- Duplicate targets are removed.
- A room cannot target itself.

Special behavior:

```text
ATTACHED_BATHROOM -> BEDROOM
```

Attached bathrooms are paired by source index with bedrooms.

Other relation types normally expand to all matching targets.

## Attached bathrooms

Recommended policy:

```python
excess_attached_bathrooms=ExcessAttachedBathroomPolicy.REJECT
```

`REJECT` requires attached-bathroom count to be less than or equal to bedroom count.

Current implementation limitation:

`ExcessAttachedBathroomPolicy.REMOVE` disables the rejection branch but does not currently remove excess attached bathrooms. Do not use it as a production cleanup policy until removal behavior is implemented.

## Configuration reference

### `PreprocessingConfig`

| Field | Purpose | Recommended start |
|---|---|---|
| `room_count_rules` | Client room-type limits | Product/domain-specific |
| `supported_aspect_ratios` | Canonical accepted ratios | `1.0`, `4/3`, `1.5` |
| `room_sizes` | Width/area references | Complete matrix for supported sizes |
| `room_relations` | Type-level relation references | Only solver-supported relations |
| `mandatory_room_types` | Required request room types | Living, kitchen, bedroom, bathroom |
| `floor_area_buffer` | Extra absolute floor area | Around 10% of minimum room area |
| `hallway_area_buffer` | Area per derived hallway | `400-800` |
| `hallway_count` | Number of derived hallways | `1` |
| `hallway_min_width` | Hallway width control | `10-12` |
| `default_room_size` | Fallback/tie size label | `"medium"` |
| `min_aspect_ratio` | Lower ratio limit | `0.75` |
| `max_aspect_ratio` | Upper ratio limit | `1.50` |
| `room_size_strategy` | Shared size policy | `MAJORITY` |
| `size_normalization_exclusions` | Types retaining own handling | `(HALLWAY,)` |
| `excess_attached_bathrooms` | Excess attached-bath behavior | `REJECT` |

## Processing stages

The operation performs:

1. input validation,
2. request normalization,
3. normalized request validation,
4. reference-data preparation,
5. reference-data validation,
6. business rules,
7. room preparation,
8. floor selection,
9. hallway creation,
10. relation expansion,
11. context validation,
12. output validation.

## Output contracts

### Production result

```python
execution.result.generation_spec
```

The specification contains:

```python
generation_spec.floor
generation_spec.rooms
generation_spec.room_relations
```

### DEBUG report

```python
report = execution.details

report.normalizations
report.room_decisions
report.relation_decisions
report.selected_room_size
report.floor_selection
report.applied_defaults
report.warnings
```

`warnings` currently exists in the contract but is not populated by the current pipeline.

## Error model

All expected feature failures derive from:

```python
FloorPlanPreprocessingError
```

Each exception exposes:

```python
exc.stage
exc.code
exc.details
exc.message
```

### Stages

```python
PreprocessingStage.INPUT_VALIDATION
PreprocessingStage.NORMALIZATION
PreprocessingStage.REFERENCE_DATA
PreprocessingStage.BUSINESS_RULES
PreprocessingStage.ROOM_PREPARATION
PreprocessingStage.RELATION_PREPARATION
PreprocessingStage.FLOOR_PREPARATION
PreprocessingStage.CONTEXT_VALIDATION
PreprocessingStage.OUTPUT_VALIDATION
```

### Exception classes

| Exception | Typical cause |
|---|---|
| `InputValidationError` | Invalid request/config structure or room counts |
| `NormalizationError` | Unsupported aspect ratio or failed normalization |
| `ReferenceDataError` | Invalid size or relation reference |
| `BusinessRuleError` | Missing mandatory room or unsupported policy behavior |
| `RoomPreparationError` | Missing `(room_type, size)` reference |
| `RelationPreparationError` | Required relation target missing |
| `FloorPreparationError` | Floor limits cannot satisfy room requirements |
| `ContextValidationError` | Internally prepared context is invalid |
| `OutputValidationError` | Final generation specification is invalid |

## Recommended configuration profiles

### Small-plan profile

```text
hallway_count: 1
hallway_min_width: 10
hallway_area_buffer: 400
floor_area_buffer: 5%-8% of minimum room area
aspect ratios: 1.0, 1.2, 4/3
bedroom maximum: 3
```

### Balanced profile

```text
hallway_count: 1
hallway_min_width: 10-12
hallway_area_buffer: 500-700
floor_area_buffer: about 10%
aspect ratios: 1.0, 4/3, 1.5
bedroom maximum: 4
```

### Large-plan R&D profile

```text
hallway_count: 1-2
hallway_min_width: 12-15
hallway_area_buffer: 700-1000
floor_area_buffer: 10%-15%
aspect ratios: 1.0 through 1.75, explicitly enumerated
bedroom maximum: 5-6 only when solver limits support it
```

## Current limitations

- Only `MAJORITY` room-size selection is implemented.
- Excess attached-bathroom removal is not implemented.
- Mandatory room types are not auto-created.
- Hallways are added by count, not inferred from room graph complexity.
- Final floor dimensions are not grid-quantized.
- Relation expansion is type-based and has one special attached-bathroom pairing rule.
- The feature validates references but does not provide built-in national building-code profiles.
