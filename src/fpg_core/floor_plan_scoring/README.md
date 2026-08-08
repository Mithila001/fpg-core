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
- `specification: FloorPlanGenerationSpec` — generation requirements used to evaluate that plan.
- `config: FloorPlanScoringConfig` — reusable scoring policy controlling groups, evaluator settings, weights, thresholds, ordering, and enabled state.

`ExecutionMode.PRODUCTION` is the default. `ExecutionMode.DEBUG` enables detailed evaluator diagnostics.

An optional `EvaluatorRegistry` may be passed directly to `score_floor_plan()` when custom evaluator implementations are required. The registry is an extension point, not request data.

#### Configuration

`FloorPlanScoringConfig` contains:

- `groups: tuple[ScoringGroupRule, ...]`
- `evaluators: tuple[EvaluatorRule, ...]`

Use `create_default_config()` for the built-in scoring setup.

`ScoringProfile`, `DEFAULT_SCORING_PROFILE`, and `create_default_profile()` remain supported compatibility names. `ScoringProfile` is an alias of `FloorPlanScoringConfig`.

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
