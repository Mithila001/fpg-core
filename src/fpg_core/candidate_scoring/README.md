# Candidate Scoring

Framework for evaluating candidate room-position arrangements before the main
layout solver.

## Responsibilities

- Evaluators independently return a score from `0` to `100`.
- The score manager owns categories, execution order, critical thresholds,
  weights, fail-fast behavior, and final score aggregation.
- Critical evaluators act as gates. A failed gate returns a total score of `0`
  and skips remaining work when fail-fast is enabled.
- Quality evaluator weights are relative and normalized automatically.

Concrete evaluator implementations are intentionally excluded from this phase.

## Basic assembly

```python
registry = EvaluatorRegistry([
    MyCriticalEvaluator(),
    MyQualityEvaluator(),
])

config = ScoringConfig(
    evaluator_rules=(
        EvaluatorRule(
            key=EvaluatorKey("critical_geometry"),
            category=EvaluatorCategory.CRITICAL,
            minimum_score=70,
            order=10,
        ),
        EvaluatorRule(
            key=EvaluatorKey("spatial_distribution"),
            category=EvaluatorCategory.QUALITY,
            weight=3,
            order=20,
        ),
    )
)

manager = CandidateScoreManager(registry, config)
result = manager.score(
    CandidateScoringInput(
        specification=generation_spec,
        candidate=candidate_points,
    )
)
```

The specification uses the active
`fpg_core.types.FloorPlanGenerationSpec`. Candidate arrangements are
kept structurally typed because Candidate Search owns their point contract and
passes them to the scorer through its evaluator callback.

## Included evaluators

The package now includes four concrete evaluators. Every evaluator returns a raw
score on the common `0..100` scale and remains unaware of manager weights,
categories, thresholds, and execution order.

- `ZoneSuitabilityEvaluator`
- `ExteriorClearanceEvaluator`
- `RelationshipQualityEvaluator`
- `SpatialDistributionEvaluator`

Use the default registry and baseline quality-weight configuration:

```python
from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    create_default_config,
    create_default_registry,
    evaluate_candidate,
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

The baseline configuration is deliberately non-critical. Any evaluator can be
changed to `CRITICAL` and assigned a `minimum_score` through `EvaluatorRule`
without modifying the evaluator implementation.
