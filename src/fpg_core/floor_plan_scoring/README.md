# Floor Plan Scoring

Evaluates a completed floor plan against the generation specification using grouped critical, functional, aesthetic, or optional evaluators.

## Guide

### Public API

```python
from fpg_core.floor_plan_scoring.api import score_floor_plan
from fpg_core.floor_plan_scoring import create_default_profile

result = score_floor_plan(
    floor_plan=floor_plan,
    specification=generation_spec,
    profile=create_default_profile(),
)
```

Pass a custom `EvaluatorRegistry` only when adding or replacing evaluator implementations.

### Inputs

- Completed shared `FloorPlan`.
- Original shared `FloorPlanGenerationSpec`.
- `ScoringProfile` containing group weights and evaluator rules.
- Optional evaluator registry.

### Outputs

`FloorPlanScoringResult` contains:

- total score;
- critical-pass flag and optional critical failure;
- per-group score and status;
- per-evaluator raw score, normalized weight, contribution, threshold, findings, metrics, and optional visualization payload.

### Errors and Expected Behaviour

Invalid input, configuration, registration, evaluator contracts, and evaluator execution use subclasses of `FloorPlanScoringError`.

Critical evaluators may stop scoring with a failed critical result. Non-applicable and skipped evaluators are represented explicitly. The operation does not mutate the floor plan.

### Extension Points

Custom evaluators implement `FloorPlanEvaluator`, are registered in `EvaluatorRegistry`, and receive typed settings from evaluator rules.

## AI Instructions

- Keep final floor-plan scoring separate from candidate scoring.
- Preserve evaluator/group keys and structured findings.
- Update this README when groups, default evaluators, score aggregation, or result fields change.
- Keep feature tests under `tests/floor_plan_scoring/test_end_to_end.py` unless extra tests are explicitly justified.
