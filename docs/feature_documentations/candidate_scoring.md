# Candidate Scoring

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Internal feature `README.md` files are development notes and are not the consumer contract. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Scores a candidate hint map on a 0..100 scale using independently configurable
critical and quality evaluators. Built-ins cover relative zone suitability, exterior
clearance, route relationship quality, and spatial distribution. Use it to rank
candidate points before room geometry exists.

## Public API

```python
evaluate_candidate(
    scoring_input: CandidateScoringInput,
    *, registry: EvaluatorRegistry,
    config: ScoringConfig,
    context_factory: ScoringContextFactory | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> ScoringResult

create_default_registry() -> EvaluatorRegistry
create_default_config(*, zone_suitability_config=None) -> ScoringConfig
```

The feature root also exports evaluator keys/classes, registry/manager/context
extension contracts, rules/settings, result/finding/status contracts, and DEBUG detail
types.

`CandidateScoreManager(registry, config, context_factory=None)` is the reusable
object form; its operation is `score(scoring_input, *,
mode=ExecutionMode.PRODUCTION) -> ScoringResult`.
`ScoringContextFactory.build(scoring_input) -> ScoringContext` constructs
the normalized evaluator context. Registry method signatures are in the extension
section.

## Inputs

`CandidateScoringInput(specification, candidate, hallway_classifications=())` requires
typed matching contracts and unique hallway classification identities. Each
`EvaluatorRule(key, category, enabled=True, order=0, weight=1.0,
minimum_score=None, settings={})` selects a registered evaluator.

## Configuration

- `ScoringConfig.evaluator_rules` must be non-empty and unique. Enabled quality rules
  need positive weights; critical rules need a 0..100 `minimum_score`.
- `fail_fast_on_critical_failure=True` skips later evaluation after a failed critical
  threshold. `not_applicable_quality_contributes=False` excludes N/A weight rather
  than treating it as full credit. `raise_on_evaluator_error=False` converts
  unexpected evaluator failures to structured error results; `True` propagates them.
- `ZoneSuitabilityConfig(zone_count_per_axis=3, falloff_multiplier=1.5,
  valid_zones=DEFAULT_VALID_ZONES)` uses 1-based cells; a larger falloff multiplier
  penalizes distance from preferred cells faster.

| `DEFAULT_VALID_ZONES` room type | Exact 1-based `(x, y)` cells |
|---|---|
| `VERANDA` | `(1,1)`, `(2,1)`, `(3,1)` |
| `GARAGE` | `(1,1)`, `(3,1)` |
| `KITCHEN` | `(1,1)`, `(2,1)`, `(3,1)`, `(1,2)`, `(3,2)`, `(1,3)`, `(2,3)`, `(3,3)` |
| `HALLWAY` | `(1,2)`, `(2,2)`, `(3,2)`, `(1,3)`, `(2,3)`, `(3,3)` |
| `LIVING_ROOM` | `(1,1)`, `(2,1)`, `(3,1)`, `(1,2)`, `(2,2)`, `(3,2)` |
| `BATHROOM` | `(1,1)`, `(2,1)`, `(3,1)`, `(1,2)`, `(3,2)`, `(1,3)`, `(2,3)`, `(3,3)` |
- `ExteriorClearanceRule` chooses room types, required qualifying room count,
  positive corridor width, and front/back/left/right direction.
- `RelationshipQualityConfig` uses shared routing costs/rules and defaults hallways as
  always traversable.
- Spatial-distribution settings are passed in the evaluator rule mapping. Defaults are
  `nnd_weight=0.4`, `coverage_weight=0.6`, `nnd_cv_sensitivity=8`,
  `sample_count_per_axis=20`, and `gap_zero_score_ratio=1.5`; both weights must be
  non-negative with a positive sum, sensitivities positive, and samples at least 2.

## Recommended values

Start with `create_default_config()` and `create_default_registry()`. It uses weights
20/20/25 for zone/clearance/distribution and 20-unit clearance rules; these are
package baselines, not universal architectural standards. Use DEBUG metrics to
calibrate project-specific zones and weights.

## Outputs

`ScoringResult` contains `total_score` (0..100), `passed_critical_checks`,
`stopped_early`, optional `stop_reason`, evaluator executions, and findings. Each
execution reports raw score, configured/normalized weight, contribution, optional
threshold result, and status. DEBUG mode includes evaluator metrics/details;
PRODUCTION deliberately removes them.

## Warnings / diagnostics

Candidate Scoring communicates non-fatal observations through structured `ScoreFinding` values. `FindingSeverity` values are `info`, `warning`, and `error`. `ScoringResult.findings` contains manager-level findings, while evaluator execution results may contain evaluator findings. In `DEBUG`, evaluator `metrics` and `details` payloads may be populated; in `PRODUCTION` those diagnostic payloads are intentionally stripped/empty while normal scores/findings remain consumer-visible as documented. Candidate Scoring is the current execution-envelope exception: it returns `ScoringResult` directly rather than `FeatureExecution`.

## Errors / failure conditions

Handle the exception classes importable from
`fpg_core.candidate_scoring.exceptions` for invalid input/configuration,
registration, and evaluator contract violations. Missing evaluator keys, duplicate
rules, bad weights/thresholds/settings, non-finite/out-of-range scores, or DEBUG data
returned in PRODUCTION are invalid. Individual evaluators may be `NOT_APPLICABLE`.

## Usage example

```python
from fpg_core.candidate_scoring import (
    CandidateScoringInput, create_default_config, create_default_registry,
    evaluate_candidate,
)

result = evaluate_candidate(
    CandidateScoringInput(example_specification, example_candidate),
    registry=create_default_registry(),
    config=create_default_config(),
)
if result.passed_critical_checks:
    ranking_score = result.total_score
```

## Important behavioral notes

The default config does not enable relationship quality, although its evaluator is in
the default registry. Candidate scoring returns `ScoringResult` directly, not a
`FeatureExecution`. Zone and distribution grids are scoring overlays; relationship
routing alone uses `candidate.grid`.

## Public Export Inventory

The supported feature-root import surface is `fpg_core.candidate_scoring`. Its current exported symbols are:

- `CandidateEvaluator`
- `CandidateScoreManager`
- `CandidateScoringInput`
- `ClearanceCorridorBounds`
- `ClearanceCorridorDebug`
- `DEFAULT_VALID_ZONES`
- `EXTERIOR_CLEARANCE_KEY`
- `EvaluationStatus`
- `EvaluatorCategory`
- `EvaluatorExecutionResult`
- `EvaluatorKey`
- `EvaluatorRegistry`
- `EvaluatorResult`
- `EvaluatorRule`
- `ExteriorClearanceDetails`
- `ExteriorClearanceEvaluator`
- `ExteriorClearanceRoomEvaluation`
- `ExteriorClearanceRule`
- `ExteriorClearanceRuleEvaluation`
- `FindingSeverity`
- `RELATIONSHIP_QUALITY_KEY`
- `RelationshipPathDetails`
- `RelationshipQualityConfig`
- `RelationshipQualityDetails`
- `RelationshipQualityEvaluator`
- `RelationshipRouteFailureDetails`
- `SPATIAL_DISTRIBUTION_KEY`
- `ScoreFinding`
- `ScoringConfig`
- `ScoringContext`
- `ScoringContextFactory`
- `ScoringResult`
- `SpatialDistributionDetails`
- `SpatialDistributionEvaluator`
- `SpatialDistributionPointDetails`
- `ZONE_SUITABILITY_KEY`
- `ZoneSuitabilityConfig`
- `ZoneSuitabilityDetails`
- `ZoneSuitabilityEvaluator`
- `ZoneSuitabilityPointDetails`
- `ZoneSuitabilityRuleDetails`
- `create_default_config`
- `create_default_registry`
- `evaluate_candidate`

Consumers should prefer the feature-root import surface shown above and `fpg_core.domain` for canonical shared contracts. Implementation submodules are not part of the supported consumer surface unless explicitly documented.

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
