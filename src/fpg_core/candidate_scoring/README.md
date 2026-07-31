# Candidate Scoring

Scores candidate room hint arrangements before floor-plan solving. Critical evaluators can reject a candidate; quality evaluators contribute to a normalized 0-100 score.

## Guide

### Public API

```python
from fpg_core.candidate_scoring.api import evaluate_candidate
from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    create_default_config,
    create_default_registry,
)

result = evaluate_candidate(
    CandidateScoringInput(
        specification=generation_spec,
        candidate=candidate_points,
    ),
    registry=create_default_registry(),
    config=create_default_config(),
)
```

### Inputs

- `CandidateScoringInput.specification`: shared `FloorPlanGenerationSpec`.
- `CandidateScoringInput.candidate`: a candidate object or point collection supported by the scoring adapters.
- `EvaluatorRegistry`: registered evaluator implementations.
- `ScoringConfig`: evaluator category, order, weight, threshold, settings, and failure policy.
- Optional `ScoringContextFactory`: prepares shared derived data for custom evaluators.

### Outputs

`ScoringResult` contains:

- total quality score from 0 to 100;
- whether critical checks passed;
- whether evaluation stopped early and why;
- execution result, findings, metrics, and optional visualization payload for every evaluator.

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
