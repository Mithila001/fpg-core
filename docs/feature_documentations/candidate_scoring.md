# Candidate Scoring

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Implementation rationale is maintained in the internal architecture and feature notes. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

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


## Warnings / diagnostics

Candidate Scoring communicates non-fatal observations through structured `ScoreFinding` values. `FindingSeverity` values are `info`, `warning`, and `error`. `ScoringResult.findings` contains manager-level findings, while evaluator execution results may contain evaluator findings. In `DEBUG`, evaluator `metrics` and `details` payloads may be populated; in `PRODUCTION` those diagnostic payloads are intentionally stripped/empty while normal scores/findings remain consumer-visible as documented. Candidate Scoring is the current execution-envelope exception: it returns `ScoringResult` directly rather than `FeatureExecution`.

## Public Export Inventory

### `fpg_core.candidate_scoring` exports (44)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `CandidateEvaluator` | class/interface/registry | `()` | Contract implemented by every candidate-scoring evaluator. |
| `CandidateScoreManager` | class/interface/registry | `(registry: 'EvaluatorRegistry', config: 'ScoringConfig', context_factory: 'ScoringContextFactory \| None' = None) -> 'None'` | Runs configured evaluator stages and calculates the final score. |
| `CandidateScoringInput` | dataclass/contract | `(specification: 'FloorPlanGenerationSpec', candidate: 'CandidateMap', hallway_classifications: 'tuple[HallwayClassification, ...]' = ()) -> None` | One generation specification, candidate, and optional hallway tags. |
| `ClearanceCorridorBounds` | dataclass/contract | `(min_x: 'float', min_y: 'float', max_x: 'float', max_y: 'float') -> None` | Axis-aligned no-hint-point corridor bounds in project units. |
| `ClearanceCorridorDebug` | dataclass/contract | `(rule_index: 'int', point_id: 'str', source_room_id: 'str', room_name: 'str', room_type: 'RoomType', hint_x: 'float', hint_y: 'float', direction: 'LandSide', bounds: 'ClearanceCorridorBounds', blocker_point_ids: 'tuple[str, ...]', blocker_room_ids: 'tuple[str, ...]', is_clear: 'bool', selected_for_score: 'bool') -> None` | Point-level exterior-clearance geometry collected in DEBUG mode. |
| `DEFAULT_VALID_ZONES` | constant/type alias | `mappingproxy instance` | Documented in the corresponding feature/shared section. |
| `EXTERIOR_CLEARANCE_KEY` | constant/type alias | `'exterior_clearance'` | Documented in the corresponding feature/shared section. |
| `EvaluationStatus` | enum | `COMPLETED='completed'; NOT_APPLICABLE='not_applicable'; SKIPPED='skipped'; ERROR='error'` | Execution state of one evaluator. |
| `EvaluatorCategory` | enum | `CRITICAL='critical'; QUALITY='quality'` | Determines how an evaluator participates in the scoring pipeline. |
| `EvaluatorExecutionResult` | dataclass/contract | `(evaluator_key: 'EvaluatorKey', category: 'EvaluatorCategory', status: 'EvaluationStatus', raw_score: 'float \| None', configured_weight: 'float', normalized_weight: 'float', contribution: 'float', threshold: 'float \| None' = None, passed_threshold: 'bool \| None' = None, findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'Mapping[str, float]' = <factory>, details: 'object \| None' = None) -> None` | Manager-owned view of one evaluator's execution and contribution. |
| `EvaluatorKey` | constant/type alias | `NewType instance` | NewType creates simple unique types with almost zero runtime overhead. |
| `EvaluatorRegistry` | class/interface/registry | `(evaluators: 'Iterable[CandidateEvaluator]' = ()) -> 'None'` | Maps stable evaluator keys to evaluator implementations. |
| `EvaluatorResult` | dataclass/contract | `(evaluator_key: 'EvaluatorKey', status: 'EvaluationStatus', score: 'float \| None', findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'Mapping[str, float]' = <factory>, details: 'object \| None' = None) -> None` | Standard result returned by every concrete evaluator. |
| `EvaluatorRule` | dataclass/contract | `(key: 'EvaluatorKey', category: 'EvaluatorCategory', enabled: 'bool' = True, order: 'int' = 0, weight: 'float' = 1.0, minimum_score: 'float \| None' = None, settings: 'Mapping[str, Any]' = <factory>) -> None` | Manager-owned configuration for one registered evaluator. |
| `ExteriorClearanceDetails` | dataclass/contract | `(floor_width: 'float', floor_length: 'float', rule_evaluations: 'tuple[ExteriorClearanceRuleEvaluation, ...]', corridors: 'tuple[ClearanceCorridorDebug, ...]') -> None` | Exterior-clearance scoring and R&D data collected in DEBUG mode. |
| `ExteriorClearanceEvaluator` | class/interface/registry | `()` | Scores directional no-hint-point corridors from hints to the boundary. |
| `ExteriorClearanceRoomEvaluation` | dataclass/contract | `(source_room_id: 'str', room_name: 'str', room_type: 'RoomType', point_ids: 'tuple[str, ...]', clear_point_ids: 'tuple[str, ...]', qualifies: 'bool', selected_for_score: 'bool') -> None` | Room-level result after combining all hints for one source room. |
| `ExteriorClearanceRule` | dataclass/contract | `(room_types: 'tuple[RoomType, ...]', required_clear_room_count: 'int', clearance_width: 'float', direction: 'LandSide') -> None` | One global-direction clearance requirement for selected room types. |
| `ExteriorClearanceRuleEvaluation` | dataclass/contract | `(rule_index: 'int', room_types: 'tuple[RoomType, ...]', required_clear_room_count: 'int', clearance_width: 'float', direction: 'LandSide', applicable: 'bool', eligible_room_count: 'int', clear_room_count: 'int', score: 'float \| None', room_evaluations: 'tuple[ExteriorClearanceRoomEvaluation, ...]') -> None` | Detailed score calculation for one configured clearance rule. |
| `FindingSeverity` | enum | `INFO='info'; WARNING='warning'; ERROR='error'` | Documented in the corresponding feature/shared section. |
| `RELATIONSHIP_QUALITY_KEY` | constant/type alias | `'relationship_quality'` | Documented in the corresponding feature/shared section. |
| `RelationshipPathDetails` | dataclass/contract | `(rule_id: 'int', rule_name: 'str', traffic_class: 'CirculationTrafficClass', destination_selection: 'DestinationSelection', source_point_id: 'str', source_room_id: 'str', source_room_type: 'RoomType', destination_point_id: 'str', destination_room_id: 'str', destination_room_type: 'RoomType', nodes: 'tuple[CirculationGridNode, ...]', step_count: 'int', manhattan_step_count: 'int', detour_step_count: 'int', turn_count: 'int', manhattan_reference_cost: 'float', costs: 'RouteCostBreakdown', path_efficiency_score: 'float') -> None` | DEBUG-only information for one resolved relationship route. |
| `RelationshipQualityConfig` | dataclass/contract | `(costs: 'GridRoutingCostProfile', route_rules: 'tuple[CirculationRouteRule, ...]', always_traversable_room_types: 'tuple[RoomType, ...]' = (<RoomType.HALLWAY: 'hallway'>,)) -> None` | Typed single-pass routing configuration for relationship scoring. |
| `RelationshipQualityDetails` | dataclass/contract | `(floor_width: 'float', floor_length: 'float', grid_node_count: 'int', path_efficiency_score: 'float', paths: 'tuple[RelationshipPathDetails, ...]', route_failures: 'tuple[RelationshipRouteFailureDetails, ...]') -> None` | Single-pass relationship routing data collected in DEBUG mode. |
| `RelationshipQualityEvaluator` | class/interface/registry | `()` | Scores one-pass grid-route efficiency between configured room types. |
| `RelationshipRouteFailureDetails` | dataclass/contract | `(rule_id: 'int', rule_name: 'str', traffic_class: 'CirculationTrafficClass', source_point_id: 'str', source_room_id: 'str', destination_point_id: 'str \| None', destination_room_id: 'str \| None', message: 'str') -> None` | DEBUG-only information for one relationship route that could not resolve. |
| `SPATIAL_DISTRIBUTION_KEY` | constant/type alias | `'spatial_distribution'` | Documented in the corresponding feature/shared section. |
| `ScoreFinding` | dataclass/contract | `(code: 'str', message: 'str', severity: 'FindingSeverity' = <FindingSeverity.INFO: 'info'>, subject_ids: 'tuple[str, ...]' = ()) -> None` | Structured explanation emitted by an evaluator or the manager. |
| `ScoringConfig` | dataclass/contract | `(evaluator_rules: 'tuple[EvaluatorRule, ...]', fail_fast_on_critical_failure: 'bool' = True, not_applicable_quality_contributes: 'bool' = False, raise_on_evaluator_error: 'bool' = False) -> None` | Configuration for the complete evaluator pipeline. |
| `ScoringContext` | dataclass/contract | `(scoring_input: 'CandidateScoringInput', derived: 'Mapping[str, Any]' = <factory>, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> None` | Read-only data shared with evaluators. |
| `ScoringContextFactory` | class/interface/registry | `()` | Single extension point for preparing shared evaluator data. |
| `ScoringResult` | dataclass/contract | `(total_score: 'float', passed_critical_checks: 'bool', stopped_early: 'bool', stop_reason: 'str \| None', evaluator_results: 'tuple[EvaluatorExecutionResult, ...]', findings: 'tuple[ScoreFinding, ...]' = ()) -> None` | Complete score-manager output for one candidate. |
| `SpatialDistributionDetails` | dataclass/contract | `(floor_width: 'float', floor_length: 'float', points: 'tuple[SpatialDistributionPointDetails, ...]', sample_count_per_axis: 'int', nearest_distances: 'tuple[tuple[float, ...], ...]', ideal_point_distance: 'float', theoretical_coverage_gap: 'float', gap_zero_score_ratio: 'float') -> None` | Spatial-distribution scoring and R&D data collected in DEBUG mode. |
| `SpatialDistributionEvaluator` | class/interface/registry | `()` | Scores anti-clumping and whole-floor point coverage. |
| `SpatialDistributionPointDetails` | dataclass/contract | `(point_id: 'str', source_room_id: 'str', room_name: 'str', room_type: 'RoomType', hint_index: 'int', x: 'float', y: 'float') -> None` | DEBUG-only candidate point used by spatial-distribution scoring. |
| `ZONE_SUITABILITY_KEY` | constant/type alias | `'zone_suitability'` | Documented in the corresponding feature/shared section. |
| `ZoneSuitabilityConfig` | dataclass/contract | `(zone_count_per_axis: 'int' = 3, falloff_multiplier: 'float' = 1.5, valid_zones: 'Mapping[RoomType, tuple[tuple[int, int], ...]]' = <factory>) -> None` | Typed caller configuration for zone-suitability scoring. |
| `ZoneSuitabilityDetails` | dataclass/contract | `(floor_width: 'float', floor_length: 'float', zone_count_per_axis: 'int', falloff_multiplier: 'float', rules: 'tuple[ZoneSuitabilityRuleDetails, ...]', points: 'tuple[ZoneSuitabilityPointDetails, ...]') -> None` | Zone-suitability scoring and R&D data collected in DEBUG mode. |
| `ZoneSuitabilityEvaluator` | class/interface/registry | `()` | Scores whether selected room types occupy preferred floor regions. |
| `ZoneSuitabilityPointDetails` | dataclass/contract | `(point_id: 'str', source_room_id: 'str', room_name: 'str', room_type: 'RoomType', hint_index: 'int', x: 'float', y: 'float', preferred_cells: 'tuple[tuple[int, int], ...]', distance_to_zone: 'float', score: 'float', inside_preferred_zone: 'bool') -> None` | DEBUG-only score calculation for one zone-scored candidate point. |
| `ZoneSuitabilityRuleDetails` | dataclass/contract | `(room_type: 'RoomType', preferred_cells: 'tuple[tuple[int, int], ...]') -> None` | DEBUG-only normalized preferred cells for one room type. |
| `create_default_config` | function | `create_default_config(*, zone_suitability_config: 'ZoneSuitabilityConfig \| None' = None) -> 'ScoringConfig'` | Create baseline scoring rules with optional caller-defined zone rules. |
| `create_default_registry` | function | `create_default_registry() -> 'EvaluatorRegistry'` | Documented in the corresponding feature/shared section. |
| `evaluate_candidate` | function | `evaluate_candidate(scoring_input: 'CandidateScoringInput', *, registry: 'EvaluatorRegistry', config: 'ScoringConfig', context_factory: 'ScoringContextFactory \| None' = None, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'ScoringResult'` | Public one-shot API for candidate scoring. |

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
