# Candidate Scoring

Scores candidate room hint arrangements before floor-plan solving. Critical evaluators can reject a candidate; quality evaluators contribute to a normalized 0-100 score.

Orthogonal relationship routing and unused-hallway removal now belong to `fpg_core.candidate_circulation`. The legacy relationship evaluator remains importable for compatibility but is not part of the default registry or default scoring configuration.

## Guide

### Public API

```python
from fpg_core.candidate_scoring.api import evaluate_candidate
from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    create_default_config,
    create_default_registry,
)
from fpg_core.domain import ExecutionMode

result = evaluate_candidate(
    CandidateScoringInput(
        specification=generation_spec,
        candidate=candidate_points,
    ),
    registry=create_default_registry(),
    config=create_default_config(),
    mode=ExecutionMode.PRODUCTION,
)
```

### Inputs

- `CandidateScoringInput.specification`: shared `FloorPlanGenerationSpec`.
- `CandidateScoringInput.candidate`: a candidate object or point collection supported by the scoring adapters.
- `EvaluatorRegistry`: registered evaluator implementations.
- `ScoringConfig`: evaluator category, order, weight, threshold, settings, and failure policy.
- Optional `ScoringContextFactory`: prepares shared derived data for custom evaluators.
- `ExecutionMode.PRODUCTION` omits exterior-clearance debug geometry.
- `ExecutionMode.DEBUG` includes exterior-clearance corridors, blockers, and detailed rule calculations.

#### Exterior-clearance rules

The exterior-clearance evaluator accepts typed rules through its evaluator settings:

```python
from fpg_core.candidate_scoring import ExteriorClearanceRule
from fpg_core.domain import LandSide, RoomType

settings = {
    "rules": (
        ExteriorClearanceRule(
            room_types=(RoomType.KITCHEN, RoomType.HALLWAY),
            required_clear_room_count=1,
            clearance_width=30.0,
            direction=LandSide.RIGHT,
        ),
    )
}
```

A corridor starts at each matching hint point, extends to the floor boundary in the configured global direction, and uses `clearance_width` across the perpendicular axis. A source room qualifies when any of its hints has no other room hint inside that corridor. Multiple hints belonging to the same source room do not block one another and count as one room.

Rule score:

```text
min(clear room count, required clear room count)
------------------------------------------------- × 100
          required clear room count
```

Rules matching no candidate rooms are ignored. The final exterior-clearance score is the average of applicable rule scores.

### Outputs

`ScoringResult` contains:

- total quality score from 0 to 100;
- whether critical checks passed;
- whether evaluation stopped early and why;
- execution result, findings, metrics, and optional visualization payload for every evaluator.

For exterior clearance:

- production returns the evaluator score and findings;
- debug additionally returns `ExteriorClearanceDetails` through `visualization_payload`.

### Errors and Expected Behaviour

Configuration, input, registry, and evaluator-contract problems use subclasses of `CandidateScoringError`.

By default, evaluator execution failures are converted into evaluator results. Set `raise_on_evaluator_error=True` to propagate evaluator exceptions. Critical failure may stop later evaluators when fail-fast is enabled.

### Extension Points

Custom evaluators implement the evaluator contract, are registered in `EvaluatorRegistry`, and receive evaluator-specific settings through `ScoringConfig`.

## AI Instructions

- Keep candidate scoring independent from Optuna and CP-SAT orchestration.
- Preserve the evaluator result contract and 0-100 score scale.
- Update this README when evaluator categories, weighting, default evaluators, or failure policy change.
- Keep feature tests under `tests/candidate_scoring/test_end_to_end.py` unless extra tests are explicitly justified.
