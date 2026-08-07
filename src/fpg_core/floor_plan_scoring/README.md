# Floor Plan Scoring

Evaluates a completed floor plan against its generation specification using grouped critical, functional, aesthetic, and optional evaluators.

## Guide

### Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_scoring.api import (
    FloorPlanScoringInput,
    create_default_profile,
    score_floor_plan,
)

execution = score_floor_plan(
    FloorPlanScoringInput(
        floor_plan=floor_plan,
        specification=generation_spec,
        profile=create_default_profile(),
    ),
    mode=ExecutionMode.DEBUG,
)
score = execution.result.total_score
```

### Inputs

- `FloorPlanScoringInput` contains the completed shared floor plan, original generation specification, and scoring profile.
- An optional custom `EvaluatorRegistry` may add or replace evaluator implementations.
- `ExecutionMode.PRODUCTION` is the default; `ExecutionMode.DEBUG` enables evaluator analysis data.

### Outputs

The API returns `FloorPlanScoringExecution`, an alias of `FeatureExecution[FloorPlanScoringResult, FloorPlanScoringDetails]`.

- `result` always contains total score, the critical-pass flag, and an optional critical failure.
- `details` is `None` in PRODUCTION. In DEBUG it contains group results, evaluator executions, findings, metrics, thresholds, contributions, and visualization payloads.
- `metadata` contains the execution mode and total duration.

### Errors and Expected Behaviour

Invalid inputs, configuration, registration, evaluator contracts, and evaluator execution raise `FloorPlanScoringError` subclasses. Critical evaluators may short-circuit later groups. Scoring never mutates the source floor plan.

### Extension Points

Custom evaluators implement `FloorPlanEvaluator`, use typed settings, and are registered through `EvaluatorRegistry`.

## AI Instructions

- Keep final floor-plan scoring separate from candidate scoring.
- Preserve evaluator/group keys and structured findings.
- Keep this README synchronized with public contracts and DEBUG details.
- Do not import another feature's internal modules.
