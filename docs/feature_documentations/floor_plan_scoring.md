# Floor Plan Scoring

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Internal feature `README.md` files are development notes and are not the consumer contract. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Scores completed room geometry against its generation specification and returns a
0..100 quality score plus structured findings. Critical geometry checks remain hard
gates. The default functional scoring now uses the generic `room_size_consistency`
evaluator instead of the former default `living_room_balance` and `bedroom_quality`
evaluators.

## Public API

```python
score_floor_plan(
    scoring_input: FloorPlanScoringInput,
    *,
    registry: EvaluatorRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanScoringExecution

create_default_config() -> FloorPlanScoringConfig
create_default_registry() -> EvaluatorRegistry

# Compatibility names:
create_default_profile() -> ScoringProfile
```

`ScoringProfile` is an alias of `FloorPlanScoringConfig`.
`DEFAULT_SCORING_PROFILE` is the same object as
`DEFAULT_FLOOR_PLAN_SCORING_CONFIG`.

## Inputs

```python
FloorPlanScoringInput(
    floor_plan: FloorPlan,
    specification: FloorPlanGenerationSpec,
    config: FloorPlanScoringConfig,
)
```

The specification is required because evaluators use room IDs, relations, and room
size ranges. The room-size-consistency feasibility adjustment reads `RoomSizeSpec.min_area`
and `max_area` directly from this specification; consumers do not supply a second copy
of those ranges.

## Configuration

```python
ScoringGroupRule(
    key: GroupKey,
    enabled: bool = True,
    order: int = 0,
    weight: float = 1.0,
)

EvaluatorRule(
    key: EvaluatorKey,
    group_key: GroupKey,
    settings: object,
    enabled: bool = True,
    order: int = 0,
    weight: float = 1.0,
    minimum_score: float | None = None,
)

FloorPlanScoringConfig(
    groups: tuple[ScoringGroupRule, ...],
    evaluators: tuple[EvaluatorRule, ...],
)
```

An enabled critical evaluator requires a `minimum_score` in `0..100`; non-critical
evaluators must not define one. Enabled group/evaluator weights must be finite and
positive. Keys must be unique, each enabled group must have an enabled evaluator, and
one enabled `critical` group acts as the gate before later groups.

Built-in group keys are `critical`, `functional`, `aesthetic`, and `extra`.

## Room-size consistency

The public evaluator key is:

```python
ROOM_SIZE_CONSISTENCY_KEY = EvaluatorKey("room_size_consistency")
```

Public aggregation values:

```python
RoomAreaAggregation.MIN      # "min"
RoomAreaAggregation.AVERAGE  # "average"
RoomAreaAggregation.MAX      # "max"
RoomAreaAggregation.TOTAL    # "total"
```

Cross-type relation rule:

```python
RoomSizeRelationRule(
    reference_type: RoomType,
    compared_type: RoomType,
    min_ratio: float | None = None,
    max_ratio: float | None = None,
    reference_aggregation: RoomAreaAggregation = RoomAreaAggregation.MAX,
    compared_aggregation: RoomAreaAggregation = RoomAreaAggregation.MAX,
    weight: float = 1.0,
    full_penalty_ratio_delta: float | None = None,
)
```

The evaluated ratio is:

```text
compared area / reference area
```

`reference_type` and `compared_type` must differ. At least one of `min_ratio` or
`max_ratio` is required. Configured ratios and rule weight must be positive; when both
bounds are present, `min_ratio <= max_ratio`. A rule-specific
`full_penalty_ratio_delta`, when supplied, must be positive.

Same-type consistency rule:

```python
RoomTypeConsistencyRule(
    room_type: RoomType,
    maximum_spread_ratio: float,
    weight: float = 1.0,
    full_penalty_ratio_delta: float | None = None,
)
```

`maximum_spread_ratio` is:

```text
largest room area / smallest room area - 1
```

It must be non-negative. Weight and any rule-specific full-penalty delta must be
positive.

Evaluator settings:

```python
RoomSizeConsistencySettings(
    relation_rules: tuple[RoomSizeRelationRule, ...] = (),
    consistency_rules: tuple[RoomTypeConsistencyRule, ...] = (),
    default_full_penalty_ratio_delta: float = 0.5,
)
```

At least one relation or consistency rule is required. Relation `(reference_type,
compared_type)` pairs must be unique; same-type consistency rules may define each room
type only once. `default_full_penalty_ratio_delta` must be positive.

### Feasibility adjustment

The evaluator does not penalize a configured ratio that the generation specification
makes impossible. It derives a feasible ratio range from the matching room specs'
`min_area` and `max_area` values and relaxes an impossible configured bound to the
nearest feasible threshold for that project.

Example:

```text
Living:  200..250
Kitchen: 220..260
Configured kitchen/living max ratio: 0.80
Best feasible ratio: 220 / 250 = 0.88
Effective max ratio: 0.88
```

The configured preference remains unchanged in the config; only scoring uses the
effective threshold. The same principle applies to a same-type spread rule when the
room-size ranges themselves force a minimum spread.

### Penalty behavior

Violations are gradual. Once the violation exceeds the effective boundary,
`full_penalty_ratio_delta` controls how much further ratio deviation produces a zero
rule score. If the individual rule leaves it `None`,
`default_full_penalty_ratio_delta` is used. Applicable rules are combined by their
individual `weight` values.

### Exact default room-size rules

The default config uses `RoomSizeConsistencySettings` with:

```python
relation_rules=(
    RoomSizeRelationRule(
        reference_type=RoomType.LIVING_ROOM,
        compared_type=RoomType.KITCHEN,
        max_ratio=0.80,
        reference_aggregation=RoomAreaAggregation.MAX,
        compared_aggregation=RoomAreaAggregation.MAX,
    ),
    RoomSizeRelationRule(
        reference_type=RoomType.KITCHEN,
        compared_type=RoomType.DINING_ROOM,
        max_ratio=1.00,
        reference_aggregation=RoomAreaAggregation.MAX,
        compared_aggregation=RoomAreaAggregation.MAX,
    ),
    RoomSizeRelationRule(
        reference_type=RoomType.LIVING_ROOM,
        compared_type=RoomType.BEDROOM,
        max_ratio=0.90,
        reference_aggregation=RoomAreaAggregation.MAX,
        compared_aggregation=RoomAreaAggregation.MAX,
    ),
)
consistency_rules=(
    RoomTypeConsistencyRule(
        room_type=RoomType.BEDROOM,
        maximum_spread_ratio=0.25,
    ),
)
default_full_penalty_ratio_delta=0.50
```

These are **scoring preferences**, not solver constraints.

## Exact default scoring config

`DEFAULT_FLOOR_PLAN_SCORING_CONFIG` / `create_default_config()` contains two groups:

```text
critical   order=10, weight=1.0
functional order=20, weight=1.0
```

Critical evaluators, all requiring score `100`:

| Evaluator | Order | Exact settings |
|---|---:|---|
| `geometry_integrity` | 10 | tolerance `1e-6` |
| `required_adjacency` | 20 | minimum shared boundary `10.0`, tolerance `1e-6` |
| `enclosed_voids` | 30 | area tolerance `1e-6` |
| `inward_recess` | 40 | maximum length `20.0`, tolerance `1e-6` |

Functional evaluators:

| Evaluator | Order | Weight | Exact settings |
|---|---:|---:|---|
| `room_size_consistency` | 10 | `2.0` | exact rules listed above |
| `kitchen_dining` | 20 | `1.0` | minimum shared boundary `10.0`, maximum distance `2000.0`, tolerance `1e-6` |

`LivingRoomBalanceEvaluator` and `BedroomQualityEvaluator` remain exported and are
still registered by `create_default_registry()` for compatibility with custom
configs. They are **not enabled by the default scoring config**.

## Recommended values

Use `create_default_config()` as the canonical baseline. The four critical checks are
strict 100-point gates. The default functional allocation gives
`room_size_consistency` twice the configured weight of `kitchen_dining` before
normalization. Treat the built-in room-size ratios as package preferences that can be
replaced by project-specific values.

## Outputs

```python
FloorPlanScoringResult(
    total_score: float,
    passed_critical: bool,
    critical_failure: ScoreFinding | None,
)

FloorPlanScoringDetails(
    group_results: tuple[ScoringGroupResult, ...],
    evaluator_results: tuple[EvaluatorExecutionResult, ...],
    findings: tuple[ScoreFinding, ...] = (),
)
```

`FloorPlanScoringExecution` is
`FeatureExecution[FloorPlanScoringResult, FloorPlanScoringDetails]`.
`details=None` in PRODUCTION. DEBUG details include group results, evaluator raw and
normalized contributions, thresholds, findings, metrics, and optional visualization
payloads.

For `room_size_consistency`, DEBUG metrics/findings expose configured, feasible,
effective, actual, and violation ratios/spreads where applicable.

## Warnings / diagnostics

Floor-plan scoring uses structured `ScoreFinding` values instead of free-form warning logs. Findings carry a code, message, severity, subject IDs, and evaluator-specific metrics where applicable. `FindingSeverity` values are `info`, `warning`, and `error`. In `DEBUG`, `FloorPlanScoringDetails` exposes group results, evaluator execution results, findings, metrics, thresholds, contributions, and evaluator details; `PRODUCTION` keeps the normal `FloorPlanScoringResult` while omitting the DEBUG detail envelope.

## Errors / failure conditions

`FloorPlanScoringError` subclasses cover invalid input, inconsistent scoring config,
registry errors, evaluator contract violations, and unexpected evaluator execution.
A critical score below threshold is a normal scoring result: `passed_critical=False`,
later groups are skipped, and no exception is required solely for failing the gate.
If no critical evaluator is applicable, the manager raises `EvaluatorExecutionError`.

## Usage example

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_scoring import (
    FloorPlanScoringInput,
    create_default_config,
    score_floor_plan,
)

execution = score_floor_plan(
    FloorPlanScoringInput(
        floor_plan=example_floor_plan,
        specification=example_specification,
        config=create_default_config(),
    ),
    mode=ExecutionMode.DEBUG,
)
score = execution.result.total_score
```

## Important behavioral notes

Scoring does not mutate the plan or generation specification. Openings do not affect
the current built-in scoring results. The old `FloorPlanScoringInput(..., profile=...)`
constructor form is no longer valid; use `config=`. Compatibility profile helper names
remain available only as aliases for the configuration object/helper.

## Public Export Inventory

The supported feature-root import surface is `fpg_core.floor_plan_scoring`. Its current exported symbols are:

- `AESTHETIC_GROUP`
- `BEDROOM_QUALITY_KEY`
- `CRITICAL_GROUP`
- `DEFAULT_FLOOR_PLAN_SCORING_CONFIG`
- `DEFAULT_SCORING_PROFILE`
- `ENCLOSED_VOIDS_KEY`
- `EXTRA_GROUP`
- `FUNCTIONAL_GROUP`
- `GEOMETRY_INTEGRITY_KEY`
- `INWARD_RECESS_KEY`
- `KITCHEN_DINING_KEY`
- `LIVING_ROOM_BALANCE_KEY`
- `ROOM_SIZE_CONSISTENCY_KEY`
- `REQUIRED_ADJACENCY_KEY`
- `BedroomQualityEvaluator`
- `BedroomQualitySettings`
- `EnclosedVoidsEvaluator`
- `EnclosedVoidsSettings`
- `EvaluationStatus`
- `EvaluatorContractError`
- `EvaluatorExecutionError`
- `EvaluatorExecutionResult`
- `EvaluatorKey`
- `EvaluatorRegistrationError`
- `EvaluatorRegistry`
- `EvaluatorResult`
- `EvaluatorRule`
- `FindingSeverity`
- `FloorPlanEvaluator`
- `FloorPlanScoringConfig`
- `FloorPlanScoringDetails`
- `FloorPlanScoringError`
- `FloorPlanScoringExecution`
- `FloorPlanScoringInput`
- `FloorPlanScoringResult`
- `GeometryIntegrityEvaluator`
- `GeometryIntegritySettings`
- `GroupKey`
- `GroupStatus`
- `InwardRecessEvaluator`
- `InwardRecessSettings`
- `KitchenDiningEvaluator`
- `KitchenDiningSettings`
- `LivingRoomBalanceEvaluator`
- `LivingRoomBalanceSettings`
- `RoomAreaAggregation`
- `RoomSizeConsistencyEvaluator`
- `RoomSizeConsistencySettings`
- `RoomSizeRelationRule`
- `RoomTypeConsistencyRule`
- `RequiredAdjacencyEvaluator`
- `RequiredAdjacencySettings`
- `ScoreFinding`
- `ScoreMetric`
- `ScoringConfigurationError`
- `ScoringContext`
- `ScoringGroupResult`
- `ScoringGroupRule`
- `ScoringInputError`
- `ScoringProfile`
- `create_default_config`
- `create_default_profile`
- `create_default_registry`
- `score_floor_plan`

Consumers should prefer the feature-root import surface shown above and `fpg_core.domain` for canonical shared contracts. Implementation submodules are not part of the supported consumer surface unless explicitly documented.

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
