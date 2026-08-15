# Floor Plan Scoring

Evaluates a completed floor plan against its generation specification. The feature keeps request-specific processing data separate from reusable scoring configuration.

## Guide

### Public API

Use the feature through `fpg_core.floor_plan_scoring.api`.

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_scoring.api import (
    FloorPlanScoringInput,
    create_default_config,
    score_floor_plan,
)

execution = score_floor_plan(
    FloorPlanScoringInput(
        floor_plan=floor_plan,
        specification=generation_spec,
        config=create_default_config(),
    ),
    mode=ExecutionMode.DEBUG,
)

score = execution.result.total_score
```

### Inputs

`FloorPlanScoringInput` clearly separates the values being processed from the scoring configuration:

- `floor_plan: FloorPlan` — completed floor plan being scored.
- `specification: FloorPlanGenerationSpec` — generation requirements used to evaluate that plan. The room `min_area` / `max_area` values used for feasibility adjustment come from this specification; callers do not provide them again.
- `config: FloorPlanScoringConfig` — reusable scoring policy controlling groups, evaluator settings, weights, thresholds, ordering, and enabled state.

`ExecutionMode.PRODUCTION` is the default. `ExecutionMode.DEBUG` enables detailed evaluator diagnostics.

An optional `EvaluatorRegistry` may be passed directly to `score_floor_plan()` when custom evaluator implementations are required. The registry is an extension point, not request data.

#### Configuration

`FloorPlanScoringConfig` contains:

- `groups: tuple[ScoringGroupRule, ...]`
- `evaluators: tuple[EvaluatorRule, ...]`

Use `create_default_config()` for the built-in scoring setup.

`ScoringProfile`, `DEFAULT_SCORING_PROFILE`, and `create_default_profile()` remain supported compatibility names. `ScoringProfile` is an alias of `FloorPlanScoringConfig`.

### Room-size consistency

The default configuration uses `room_size_consistency` instead of the former specialized `living_room_balance` and `bedroom_quality` evaluators.

A cross-type rule evaluates:

```text
compared room-type area / reference room-type area
```

Example custom configuration:

```python
from fpg_core.domain import RoomType
from fpg_core.floor_plan_scoring.api import (
    RoomAreaAggregation,
    RoomSizeConsistencySettings,
    RoomSizeRelationRule,
    RoomTypeConsistencyRule,
)

settings = RoomSizeConsistencySettings(
    relation_rules=(
        # Kitchen should preferably be <= 80% of the living room.
        RoomSizeRelationRule(
            reference_type=RoomType.LIVING_ROOM,
            compared_type=RoomType.KITCHEN,
            max_ratio=0.80,
        ),
        # Dining should preferably not be larger than the kitchen.
        RoomSizeRelationRule(
            reference_type=RoomType.KITCHEN,
            compared_type=RoomType.DINING_ROOM,
            max_ratio=1.00,
        ),
        # Catch a single oversized bedroom by comparing the largest instances.
        RoomSizeRelationRule(
            reference_type=RoomType.LIVING_ROOM,
            compared_type=RoomType.BEDROOM,
            max_ratio=0.90,
            reference_aggregation=RoomAreaAggregation.MAX,
            compared_aggregation=RoomAreaAggregation.MAX,
        ),
    ),
    consistency_rules=(
        RoomTypeConsistencyRule(
            room_type=RoomType.BEDROOM,
            maximum_spread_ratio=0.25,
        ),
    ),
    default_full_penalty_ratio_delta=0.50,
)
```

`RoomAreaAggregation` supports:

- `MIN`
- `AVERAGE`
- `MAX`
- `TOTAL`

For a same-type consistency rule, `maximum_spread_ratio` means:

```text
largest area / smallest area - 1
```

For example, `0.25` allows the largest bedroom to be up to 25% larger than the smallest bedroom before a penalty starts.

#### Feasibility adjustment

The evaluator does not blindly apply a ratio that the project room-size limits make impossible. It derives the feasible ratio range from the matching `RoomSizeSpec.min_area` and `RoomSizeSpec.max_area` values in `FloorPlanGenerationSpec`.

Example:

```text
Living:  200..250
Kitchen: 220..260
Configured kitchen/living max ratio: 0.80
Best feasible ratio: 220 / 250 = 0.88
Effective max ratio: 0.88
```

The configured preference is preserved in configuration, but scoring uses the feasible `0.88` threshold for that project. `DEBUG` results expose configured, feasible, effective, actual, and violation ratios through evaluator metrics and findings.

The same feasibility adjustment is applied to same-type consistency. If bedroom area ranges themselves force a minimum size spread, the evaluator relaxes an impossible configured spread to that minimum feasible spread.

#### Penalty behavior

Ratio violations are gradual. `full_penalty_ratio_delta` controls how far beyond an effective ratio boundary produces a zero score for that rule. If a rule does not override it, `default_full_penalty_ratio_delta` is used.

Each room-size relation and same-type consistency rule has its own `weight`. The evaluator returns the weighted average of all applicable rules.

#### Default room-size rules

The built-in configuration currently prefers:

- largest kitchen <= 80% of largest living room;
- largest dining room <= 100% of largest kitchen;
- largest bedroom <= 90% of largest living room;
- bedroom largest/smallest spread <= 25%.

These are scoring preferences, not hard solver constraints, and consumers may replace them in `FloorPlanScoringConfig`.

The former `LivingRoomBalanceEvaluator` and `BedroomQualityEvaluator` remain registered/exported for compatibility with existing custom scoring configurations, but they are no longer part of the default scoring configuration.

### Outputs

The API returns `FloorPlanScoringExecution`, an alias of `FeatureExecution[FloorPlanScoringResult, FloorPlanScoringDetails]`.

- `result` always contains the total score, critical-pass flag, and optional critical failure.
- `details` is `None` in `PRODUCTION`.
- In `DEBUG`, `details` contains scoring-group results, evaluator execution results, findings, metrics, thresholds, contributions, and evaluator visualization payloads when produced.
- `metadata` contains the execution mode and total duration.

### Errors and Expected Behaviour

Invalid processing input, scoring configuration, evaluator registration, evaluator contracts, and evaluator execution raise `FloorPlanScoringError` subclasses where applicable. Public API type misuse raises `TypeError` before scoring starts.

Critical evaluators may short-circuit later scoring groups. The feature does not mutate the supplied floor plan or specification.

### Extension Points

Custom evaluators implement `FloorPlanEvaluator`, provide a typed settings class, and are registered through `EvaluatorRegistry`. Custom scoring configurations reference registered evaluators through `EvaluatorRule`.

### Migration from the previous input contract

Old:

```python
FloorPlanScoringInput(
    floor_plan=floor_plan,
    specification=generation_spec,
    profile=create_default_profile(),
)
```

New:

```python
FloorPlanScoringInput(
    floor_plan=floor_plan,
    specification=generation_spec,
    config=create_default_config(),
)
```

The `profile=` input field was intentionally replaced by `config=` so callers can distinguish processing data from configuration directly from the public contract.

## AI Instructions

- Keep final floor-plan scoring separate from candidate scoring.
- Keep processing input separate from reusable scoring configuration.
- Preserve evaluator/group keys and structured findings.
- Keep this README synchronized with the public API and DEBUG details.
- Do not document private implementation modules as supported APIs.
- Do not import another feature's internal modules.
