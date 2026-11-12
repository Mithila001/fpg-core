# Floor Plan Scoring

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Implementation rationale is maintained in the internal architecture and feature notes. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

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

The default scoring configuration uses the same 12 upper-bound relationships as
[the solver](floor_plan_solver.md#room-size-relationships), each with maximum
ratio `1.0`. Bathrooms and attached bathrooms are compared with bedrooms, living
rooms, dining rooms, kitchens, and garages; bedrooms and kitchens are compared
with living rooms. Each rule compares the largest compared room with the smallest
reference room. The separate bedroom consistency rule permits a maximum spread
ratio of `0.25`; the default full-penalty ratio delta is `0.50`.

The evaluator and solver use independent configurations and different penalty
calculations. The scorer also adjusts impossible thresholds using the supplied
room specifications; sharing default values does not guarantee identical scores
or automatically synchronize custom rules.

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


## Warnings / diagnostics

Floor-plan scoring uses structured `ScoreFinding` values instead of free-form warning logs. Findings carry a code, message, severity, subject IDs, and evaluator-specific metrics where applicable. `FindingSeverity` values are `info`, `warning`, and `error`. In `DEBUG`, `FloorPlanScoringDetails` exposes group results, evaluator execution results, findings, metrics, thresholds, contributions, and evaluator details; `PRODUCTION` keeps the normal `FloorPlanScoringResult` while omitting the DEBUG detail envelope.

## Public Export Inventory

### `fpg_core.floor_plan_scoring` exports (64)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `AESTHETIC_GROUP` | constant/type alias | `'aesthetic'` | Documented in the corresponding feature/shared section. |
| `BEDROOM_QUALITY_KEY` | constant/type alias | `'bedroom_quality'` | Documented in the corresponding feature/shared section. |
| `CRITICAL_GROUP` | constant/type alias | `'critical'` | Documented in the corresponding feature/shared section. |
| `DEFAULT_FLOOR_PLAN_SCORING_CONFIG` | dataclass/contract | `constructor has no separately inspectable signature` | Reusable configuration controlling how a floor plan is scored. |
| `DEFAULT_SCORING_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Reusable configuration controlling how a floor plan is scored. |
| `ENCLOSED_VOIDS_KEY` | constant/type alias | `'enclosed_voids'` | Documented in the corresponding feature/shared section. |
| `EXTRA_GROUP` | constant/type alias | `'extra'` | Documented in the corresponding feature/shared section. |
| `FUNCTIONAL_GROUP` | constant/type alias | `'functional'` | Documented in the corresponding feature/shared section. |
| `GEOMETRY_INTEGRITY_KEY` | constant/type alias | `'geometry_integrity'` | Documented in the corresponding feature/shared section. |
| `INWARD_RECESS_KEY` | constant/type alias | `'inward_recess'` | Documented in the corresponding feature/shared section. |
| `KITCHEN_DINING_KEY` | constant/type alias | `'kitchen_dining_proximity'` | Documented in the corresponding feature/shared section. |
| `LIVING_ROOM_BALANCE_KEY` | constant/type alias | `'living_room_balance'` | Documented in the corresponding feature/shared section. |
| `ROOM_SIZE_CONSISTENCY_KEY` | constant/type alias | `'room_size_consistency'` | Stable key for the configurable room-size consistency evaluator. |
| `REQUIRED_ADJACENCY_KEY` | constant/type alias | `'required_adjacency'` | Documented in the corresponding feature/shared section. |
| `BedroomQualityEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `BedroomQualitySettings` | dataclass/contract | `(area_compliance_weight: 'float', consistency_weight: 'float', full_spread_penalty_ratio: 'float', maximum_spread_penalty: 'float') -> None` | BedroomQualitySettings(area_compliance_weight: 'float', consistency_weight: 'float', full_spread_penalty_ratio: 'float', maximum_spread_penalty: 'float') |
| `EnclosedVoidsEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `EnclosedVoidsSettings` | dataclass/contract | `(area_tolerance: 'float') -> None` | EnclosedVoidsSettings(area_tolerance: 'float') |
| `EvaluationStatus` | enum | `COMPLETED='completed'; NOT_APPLICABLE='not_applicable'; SKIPPED='skipped'` | Documented in the corresponding feature/shared section. |
| `EvaluatorContractError` | exception | `constructor has no separately inspectable signature` | Raised when an evaluator returns a result outside the common contract. |
| `EvaluatorExecutionError` | exception | `constructor has no separately inspectable signature` | Raised when an evaluator fails unexpectedly while scoring. |
| `EvaluatorExecutionResult` | dataclass/contract | `(evaluator_key: 'EvaluatorKey', group_key: 'GroupKey', status: 'EvaluationStatus', raw_score: 'float \| None', configured_weight: 'float', normalized_weight: 'float' = 0.0, contribution: 'float' = 0.0, threshold: 'float \| None' = None, passed_threshold: 'bool \| None' = None, findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = (), visualization_payload: 'object \| None' = None) -> None` | EvaluatorExecutionResult(evaluator_key: 'EvaluatorKey', group_key: 'GroupKey', status: 'EvaluationStatus', raw_score: 'float \| None', configured_weight: 'float', normalized_weight: 'float' = 0.0, contribution: 'float' = 0.0, threshold: 'float \| None' = None, passed_threshold: 'bool \| None' = None, findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = (), visualization_payload: 'object \| None' = None) |
| `EvaluatorKey` | constant/type alias | `NewType instance` | NewType creates simple unique types with almost zero runtime overhead. |
| `EvaluatorRegistrationError` | exception | `constructor has no separately inspectable signature` | Raised for duplicate or missing evaluator registrations. |
| `EvaluatorRegistry` | class/interface/registry | `(evaluators: 'Iterable[FloorPlanEvaluator]' = ()) -> 'None'` | Documented in the corresponding feature/shared section. |
| `EvaluatorResult` | dataclass/contract | `(evaluator_key: 'EvaluatorKey', status: 'EvaluationStatus', score: 'float \| None', findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = (), visualization_payload: 'object \| None' = None) -> None` | EvaluatorResult(evaluator_key: 'EvaluatorKey', status: 'EvaluationStatus', score: 'float \| None', findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = (), visualization_payload: 'object \| None' = None) |
| `EvaluatorRule` | dataclass/contract | `(key: 'EvaluatorKey', group_key: 'GroupKey', settings: 'object', enabled: 'bool' = True, order: 'int' = 0, weight: 'float' = 1.0, minimum_score: 'float \| None' = None) -> None` | Configuration for one registered evaluator inside a scoring group. |
| `FindingSeverity` | enum | `INFO='info'; WARNING='warning'; ERROR='error'` | Documented in the corresponding feature/shared section. |
| `FloorPlanEvaluator` | class/interface/registry | `()` | Common contract for all floor-plan evaluators. |
| `FloorPlanScoringConfig` | dataclass/contract | `(groups: 'tuple[ScoringGroupRule, ...]', evaluators: 'tuple[EvaluatorRule, ...]') -> None` | Reusable configuration controlling how a floor plan is scored. |
| `FloorPlanScoringDetails` | dataclass/contract | `(group_results: 'tuple[ScoringGroupResult, ...]', evaluator_results: 'tuple[EvaluatorExecutionResult, ...]', findings: 'tuple[ScoreFinding, ...]' = ()) -> None` | DEBUG-only scoring breakdown and evaluator diagnostics. |
| `FloorPlanScoringError` | exception | `constructor has no separately inspectable signature` | Base exception for the floor-plan scoring package. |
| `FloorPlanScoringExecution` | constant/type alias | `_GenericAlias instance` | Documented in the corresponding feature/shared section. |
| `FloorPlanScoringInput` | dataclass/contract | `(floor_plan: 'FloorPlan', specification: 'FloorPlanGenerationSpec', config: 'FloorPlanScoringConfig') -> None` | Request-specific scoring data plus reusable scoring configuration. |
| `FloorPlanScoringResult` | dataclass/contract | `(total_score: 'float', passed_critical: 'bool', critical_failure: 'ScoreFinding \| None') -> None` | FloorPlanScoringResult(total_score: 'float', passed_critical: 'bool', critical_failure: 'ScoreFinding \| None') |
| `GeometryIntegrityEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `GeometryIntegritySettings` | dataclass/contract | `(tolerance: 'float') -> None` | GeometryIntegritySettings(tolerance: 'float') |
| `GroupKey` | constant/type alias | `NewType instance` | NewType creates simple unique types with almost zero runtime overhead. |
| `GroupStatus` | enum | `COMPLETED='completed'; FAILED='failed'; NOT_APPLICABLE='not_applicable'; SKIPPED='skipped'` | Documented in the corresponding feature/shared section. |
| `InwardRecessEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `InwardRecessSettings` | dataclass/contract | `(maximum_length: 'float', tolerance: 'float') -> None` | InwardRecessSettings(maximum_length: 'float', tolerance: 'float') |
| `KitchenDiningEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `KitchenDiningSettings` | dataclass/contract | `(minimum_shared_boundary: 'float', maximum_distance: 'float', tolerance: 'float') -> None` | KitchenDiningSettings(minimum_shared_boundary: 'float', maximum_distance: 'float', tolerance: 'float') |
| `LivingRoomBalanceEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `LivingRoomBalanceSettings` | dataclass/contract | `(maximum_excess_ratio: 'float') -> None` | LivingRoomBalanceSettings(maximum_excess_ratio: 'float') |
| `RoomAreaAggregation` | enum | `MIN='min'; AVERAGE='average'; MAX='max'; TOTAL='total'` | Controls how multiple rooms of one type are reduced to one area for a relation rule. |
| `RoomSizeConsistencyEvaluator` | class/interface/registry | `()` | Evaluates configurable inter-type area ratios and same-type area spread. |
| `RoomSizeConsistencySettings` | dataclass/contract | `(relation_rules: 'tuple[RoomSizeRelationRule, ...]' = (), consistency_rules: 'tuple[RoomTypeConsistencyRule, ...]' = (), default_full_penalty_ratio_delta: 'float' = 0.5) -> None` | Settings container; requires at least one relation or consistency rule. |
| `RoomSizeRelationRule` | dataclass/contract | `(reference_type: 'RoomType', compared_type: 'RoomType', min_ratio: 'float | None' = None, max_ratio: 'float | None' = None, reference_aggregation: 'RoomAreaAggregation' = MAX, compared_aggregation: 'RoomAreaAggregation' = MAX, weight: 'float' = 1.0, full_penalty_ratio_delta: 'float | None' = None) -> None` | Configures preferred `compared_area / reference_area` bounds. |
| `RoomTypeConsistencyRule` | dataclass/contract | `(room_type: 'RoomType', maximum_spread_ratio: 'float', weight: 'float' = 1.0, full_penalty_ratio_delta: 'float | None' = None) -> None` | Configures preferred same-type area spread, `largest / smallest - 1`. |
| `RequiredAdjacencyEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `RequiredAdjacencySettings` | dataclass/contract | `(minimum_shared_boundary: 'float', tolerance: 'float') -> None` | RequiredAdjacencySettings(minimum_shared_boundary: 'float', tolerance: 'float') |
| `ScoreFinding` | dataclass/contract | `(code: 'str', message: 'str', severity: 'FindingSeverity' = <FindingSeverity.INFO: 'info'>, subject_ids: 'tuple[str, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = ()) -> None` | ScoreFinding(code: 'str', message: 'str', severity: 'FindingSeverity' = <FindingSeverity.INFO: 'info'>, subject_ids: 'tuple[str, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = ()) |
| `ScoreMetric` | dataclass/contract | `(name: 'str', value: 'float', unit: 'str \| None' = None) -> None` | ScoreMetric(name: 'str', value: 'float', unit: 'str \| None' = None) |
| `ScoringConfigurationError` | exception | `constructor has no separately inspectable signature` | Raised when a scoring profile or registry is inconsistent. |
| `ScoringContext` | dataclass/contract | `(mode: 'ExecutionMode', floor_width: 'float', floor_length: 'float', floor_points: 'tuple[tuple[float, float], ...]', floor_polygon: 'Polygon', rooms: 'tuple[NormalizedRoom, ...]', room_specs: 'tuple[NormalizedRoomSpec, ...]', relations: 'tuple[NormalizedRelation, ...]', rooms_by_id: 'Mapping[str, NormalizedRoom]', specs_by_id: 'Mapping[str, NormalizedRoomSpec]', identity_redirects: 'Mapping[str, str]', room_union: 'BaseGeometry \| None', geometry_build_error: 'str \| None', shared_boundary_lengths: 'Mapping[tuple[str, str], float]') -> None` | ScoringContext(mode: 'ExecutionMode', floor_width: 'float', floor_length: 'float', floor_points: 'tuple[tuple[float, float], ...]', floor_polygon: 'Polygon', rooms: 'tuple[NormalizedRoom, ...]', room_specs: 'tuple[NormalizedRoomSpec, ...]', relations: 'tuple[NormalizedRelation, ...]', rooms_by_id: 'Mapping[str, NormalizedRoom]', specs_by_id: 'Mapping[str, NormalizedRoomSpec]', identity_redirects: 'Mapping[str, str]', room_union: 'BaseGeometry \| None', geometry_build_error: 'str \| None', shared_boundary_lengths: 'Mapping[tuple[str, str], float]') |
| `ScoringGroupResult` | dataclass/contract | `(group_key: 'GroupKey', status: 'GroupStatus', normalized_maximum: 'float', raw_score: 'float \| None', contribution: 'float') -> None` | ScoringGroupResult(group_key: 'GroupKey', status: 'GroupStatus', normalized_maximum: 'float', raw_score: 'float \| None', contribution: 'float') |
| `ScoringGroupRule` | dataclass/contract | `(key: 'GroupKey', enabled: 'bool' = True, order: 'int' = 0, weight: 'float' = 1.0) -> None` | Configuration for one scoring group. |
| `ScoringInputError` | exception | `constructor has no separately inspectable signature` | Raised when floor-plan or specification data is structurally broken. |
| `ScoringProfile` | dataclass/contract | `(groups: 'tuple[ScoringGroupRule, ...]', evaluators: 'tuple[EvaluatorRule, ...]') -> None` | Reusable configuration controlling how a floor plan is scored. |
| `create_default_config` | function | `create_default_config() -> 'FloorPlanScoringConfig'` | Documented in the corresponding feature/shared section. |
| `create_default_profile` | function | `create_default_profile() -> 'ScoringProfile'` | Compatibility alias for create_default_config(). |
| `create_default_registry` | function | `create_default_registry() -> 'EvaluatorRegistry'` | Documented in the corresponding feature/shared section. |
| `score_floor_plan` | function | `score_floor_plan(scoring_input: 'FloorPlanScoringInput', *, registry: 'EvaluatorRegistry \| None' = None, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FloorPlanScoringExecution'` | Score one completed floor plan without application-layer orchestration. |

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
