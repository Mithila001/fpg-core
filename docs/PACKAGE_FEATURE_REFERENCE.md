# fpg-core consumer feature reference

This reference describes the supported, installed-package surface of the current
`fpg-core` source tree. Feature-root imports such as `fpg_core.floor_plan_solver` are the preferred
imports. Shared geometry, floor-plan, candidate, and generation-specification
contracts are exported by `fpg_core.domain`.

Unless a project defines a conversion externally, lengths are expressed in the
consumer's project units, areas in square project units, and coordinates in the same
coordinate system as the supplied boundary. `ExecutionMode.PRODUCTION` is the
default for features returning `FeatureExecution`; `DEBUG` adds details but does not
change the result contract.

## Buildable Land

### Purpose

Validates and normalizes one convex parcel with one entry-road attachment, classifies
its sides relative to that road, applies a setback profile, and returns the remaining
convex buildable polygon. Use it when a consumer already has parcel coordinates and
setback reference data and needs the legal/build-policy envelope.

### Public API

```python
from fpg_core.buildable_land import (
    BuildableLandError,
    calculate_buildable_land,
    normalize_land_request,
)

normalize_land_request(
    request: BuildableSpaceRequestData,
    reference_data: BuildableSpaceConfig,
) -> NormalizedLand

calculate_buildable_land(
    land: NormalizedLand,
    profile: SetbackProfile,
) -> BuildableLand
```

The input and output contracts are imported from `fpg_core.domain`;
`BuildableSpaceConfig` is imported from `fpg_core`.

### Inputs

- `BuildableSpaceRequestData.land_boundary: Polygon` is an ordered boundary of
  `Point(x, y)` values. A repeated closing point is accepted and removed. Effective
  point count must fall within `ValidationLimits`; points must be unique, finite,
  within `maximum_absolute_coordinate`, non-collinear at every intermediate vertex,
  non-self-intersecting, positive-area, and convex. Clockwise input is accepted.
- `roads: tuple[RoadAttachment, ...]` must contain exactly one item. Its
  `boundary_edge_index` refers to the original boundary edge; its `road_type` must
  exist in the active profile's adjustments. Current `RoadRole` supports
  `MAIN_ENTRY`.
- `BuildableSpaceConfig` contains `active_profile: SetbackProfile`,
  `usable_land_constraints` (unused by these two calls), and `validation_limits`.
- `SetbackProfile` contains `name`, `status`, `description`, calculation mode,
  `base_setbacks: Mapping[LandSide, int]`, and nested road adjustments. Current
  calculation mode is `BASE_PLUS_ROAD_ADJUSTMENT`. Setbacks are lengths in project
  units.

### Configuration

- `ValidationLimits.minimum_vertex_count`, `maximum_vertex_count`, and
  `maximum_absolute_coordinate` control accepted parcel complexity and coordinate
  bounds.
- `base_setbacks` sets the inward distance for front/back/left/right edges.
- `road_adjustments[road_type][side]` is added only on the attached road edge.

### Recommended values

The implementation provides no universal setback or validation profile. Use values
from the consumer's jurisdiction/reference dataset; all four `LandSide` values and
each accepted `RoadType` need mapping entries.

### Outputs

`NormalizedLand` contains a counter-clockwise boundary, normalized `LandEdge`s that
retain `source_edge_index`, and `main_entry_road`. `BuildableLand` contains
`boundary: Polygon`, `area: float`, and one `EdgeSetback` per source edge with side,
base, road adjustment, final setback, and optional road type.

### Errors / failure conditions

Both calls raise `BuildableLandError`; inspect `.code: BuildableSpaceErrorCode` and
`.message`. Codes cover invalid/non-convex/self-intersecting boundaries, bad or
unsupported road attachments, setbacks that eliminate the parcel, and final geometry
failure. A negative road edge index is not explicitly rejected by normalization;
consumers should supply indexes in `0..vertex_count-1`.

### Usage example

```python
from fpg_core import BuildableSpaceConfig
from fpg_core.buildable_land import calculate_buildable_land, normalize_land_request
from fpg_core.domain import (
    BuildableSpaceRequestData, LandSide, Point, Polygon, RoadAttachment,
    RoadRole, RoadType, SetbackCalculationMode, SetbackProfile,
    UsableLandConstraints, ValidationLimits,
)

profile = SetbackProfile(
    name="residential", status="active", description="Local residential rules",
    calculation_mode=SetbackCalculationMode.BASE_PLUS_ROAD_ADJUSTMENT,
    base_setbacks={side: 5 for side in LandSide},
    road_adjustments={RoadType.MAIN_ROAD: {side: 0 for side in LandSide}},
)
config = BuildableSpaceConfig(
    active_profile=profile,
    usable_land_constraints=UsableLandConstraints(20, 20, 1, 1000),
    validation_limits=ValidationLimits(4, 12, 100_000),
)
request = BuildableSpaceRequestData(
    land_boundary=Polygon((Point(0, 0), Point(100, 0), Point(100, 80), Point(0, 80))),
    roads=(RoadAttachment(0, RoadRole.MAIN_ENTRY, RoadType.MAIN_ROAD),),
)
land = normalize_land_request(request, config)
result = calculate_buildable_land(land, profile)
```

### Important behavioral notes

Inputs are not mutated. Boundary orientation may change during normalization while
source edge identity is preserved. Side meaning is road-relative, not a global
compass direction.

## Usable Land

### Purpose

Finds the highest-ranked integer-coordinate, road-aligned rectangle inside a
`BuildableLand` polygon that satisfies floor minimum dimensions. Use it when a
consumer needs a simple rectangular floor envelope from an already calculated
buildable polygon.

### Public API

```python
from fpg_core.usable_land import UsableLandError, find_usable_land

find_usable_land(
    buildable_land: BuildableLand,
    land: NormalizedLand,
    constraints: UsableLandConstraints,
) -> UsableLand
```

### Inputs

- `buildable_land` supplies the polygon to search.
- `land` supplies the normalized main-road edge and its orientation.
- `UsableLandConstraints(minimum_width, minimum_length, search_resolution,
  maximum_sweep_lines)` uses positive integer project units/counts. Width is defined
  relative to the selected road alignment; both parallel and perpendicular
  alignments are considered.

### Configuration

- Minimum width/length reject smaller rectangles.
- `search_resolution` is the vertical search step in road-aligned coordinates;
  smaller values inspect more positions and may find a larger rectangle.
- `maximum_sweep_lines` caps synchronous search work; exceeding it is a returned
  error rather than partial output.

### Recommended values

No universal dimensions are built in. Use project minimum floor dimensions. Use the
coarsest resolution acceptable for the project's coordinate precision and size
`maximum_sweep_lines` above the expected road-aligned height divided by resolution.

### Outputs

`UsableLand` contains world-coordinate `boundary: Polygon`, integer `width`, `length`,
and `area`, `floor_width_alignment` (`PARALLEL_TO_ENTRY_ROAD` or
`PERPENDICULAR_TO_ENTRY_ROAD`), and the original `entry_road_edge_index`.

### Errors / failure conditions

`UsableLandError` exposes `.code`, `.message`, and `.details`. Handle
`NO_USABLE_LAND_FOUND`, `SEARCH_LIMIT_EXCEEDED`, and
`USABLE_LAND_CALCULATION_FAILED`. Non-positive configuration is rejected by
package-wide configuration validation but the standalone function expects a valid
contract.

### Usage example

```python
from fpg_core.domain import UsableLandConstraints
from fpg_core.usable_land import find_usable_land

usable = find_usable_land(
    buildable_land=buildable_land,
    land=normalized_land,
    constraints=UsableLandConstraints(30, 40, 1, 1000),
)
```

### Important behavioral notes

The call is deterministic and non-mutating. Ranking favors area, then the smaller
dimension, then parallel-to-road alignment, followed by stable coordinate tie-breaks.

## Floor Plan Preprocessing

### Purpose

Converts client room choices and reference rules into a validated
`FloorPlanGenerationSpec`, exact centered candidate grid, and allowed hallway-room
count. Use it to turn permissive client-facing values into canonical typed generation
inputs.

### Public API

```python
from fpg_core.floor_plan_preprocessing import prepare_generation_input

prepare_generation_input(
    input: PreprocessingInput,
    *, mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> PreprocessingExecution
```

The feature root also exports all request/config/result dataclasses, enums,
`canonical_aspect_ratio(value, rules, *, tolerance=1e-6) -> float | None`, the base
`FloorPlanPreprocessingError`, stage-specific subclasses, and error/stage enums.
`PreprocessingPolicy` and `PreprocessingReferenceData` are compatibility aliases for
`PreprocessingConfig`; `CandidateSearchSpaceSelection` aliases
`CandidateGridSelection`.

### Inputs

- `PreprocessingInput(request, config)` is required.
- `PreprocessingRequest(FloorLimits(max_width, max_length), aspect_ratio, rooms)`.
  Limits and ratios must be positive finite numbers. `aspect_ratio` accepts a finite
  number, numeric string, configured label such as `"4:5"`, or ratio text.
- Each `RequestedRoom(room_type, id=None, name=None, requested_size=None)` requires a
  `RoomType`. Missing IDs/names/sizes are normalized from configuration. IDs must end
  unique after normalization.
- `PreprocessingConfig` required fields are room-count rules, supported ratios, room
  sizes, room relations, mandatory room types, floor/hallway area buffers,
  `max_hallway_room_count`, hallway minimum width, even candidate grid spacing,
  default size, and maximum aspect residual. Optional defaults are
  `min_aspect_ratio=0.5`, `max_aspect_ratio=2.0`, majority size selection, hallway
  exclusion from size normalization, and attached-bathroom policy `REJECT`.

### Configuration

- `RoomCountRule`: minimum/maximum count and whether clients may request the type.
- `AspectRatioRule`: accepted label and canonical width/length value.
- `RoomSizeReference`: per-type/size width and area limits.
- `RoomRelationReference`: type-level targets, `AND`/`OR`, `HARD`/`SOFT`, and whether
  missing targets invalidate preparation.
- `mandatory_room_types` inserts/validates required types.
- `floor_area_buffer` and `hallway_area_buffer` add square project units to sizing.
- `max_hallway_room_count` creates that many potential hallway specs; minimum is
  always one. `hallway_min_width` sets their width constraint.
- `candidate_search_grid_spacing` sets the uniform candidate grid interval; it must
  be an even integer at least 1 and fit at least two intervals on both floor axes.
- `max_aspect_residual_units` limits floor dimension residual from the requested
  aspect; `min_aspect_ratio`/`max_aspect_ratio` bound accepted ratios.
- `excess_attached_bathrooms` either rejects or removes bathrooms beyond bedroom
  count. Only `MAJORITY` is currently supported for `room_size_strategy`.

### Recommended values

Use the package defaults for optional policy fields unless product rules require a
change. Room sizes, buffers, count rules, grid spacing, and supported ratios are
project reference data; the code provides no universal values. Choose spacing that
is even and leaves enough interior nodes for every possible room.

### Outputs

`PreprocessingExecution` is
`FeatureExecution[PreparedGenerationInput, PreprocessingReport]`. The result contains
`generation_spec`, `candidate_grid`, and `hallway_room_count_range`. Its
`generation_spec_for_candidate(candidate)` validates grid/room identity and returns a
spec containing exactly the selected hallway rooms. In DEBUG, `details` records
normalizations, room/relation decisions, size choice, floor/grid selection, hallway
range, defaults, and warnings. Metadata contains mode and duration.

### Errors / failure conditions

Expected failures raise `FloorPlanPreprocessingError` subclasses. Inspect `.stage`,
`.code`, `.message`, and immutable `.details`. Failures include invalid input/reference
data, forbidden/count-invalid rooms, duplicate IDs, excess attached bathrooms,
missing sizes/relations, insufficient floor limits, excessive aspect residual, or an
invalid output grid. A non-`ExecutionMode` mode raises `TypeError`.

### Usage example

```python
from fpg_core.domain import ExecutionMode, RoomType
from fpg_core.floor_plan_preprocessing import (
    FloorLimits, PreprocessingInput, PreprocessingRequest, RequestedRoom,
    prepare_generation_input,
)

execution = prepare_generation_input(
    PreprocessingInput(
        request=PreprocessingRequest(
            floor_limits=FloorLimits(120, 90),
            aspect_ratio="4:5",
            rooms=(RequestedRoom(RoomType.LIVING_ROOM, requested_size="medium"),),
        ),
        config=preprocessing_config,
    ),
    mode=ExecutionMode.DEBUG,
)
prepared = execution.result
```

### Important behavioral notes

The result template contains every possible hallway room, not a selected subset.
Compatibility `candidate_search_space` properties are derived views; the exact
`ResolvedCandidateGrid` is authoritative. The operation does not invoke search or a
solver.

## Candidate Search

### Purpose

Uses Optuna to sample non-overlapping, non-edge grid points for every active room and
returns the candidate with the highest consumer-supplied score. Use it when room
placement hints need exploration on a prepared discrete grid.

### Public API

```python
build_candidate_grid(*, grid: ResolvedCandidateGrid,
                     max_grid_node_count: int) -> ResolvedCandidateGrid
build_candidate_search_targets(specification: FloorPlanGenerationSpec
                              ) -> tuple[CandidateSearchTarget, ...]
search_candidates(search_input: CandidateSearchInput, *,
                  mode: ExecutionMode = ExecutionMode.PRODUCTION
                 ) -> FeatureExecution[CandidateSearchResult, CandidateSearchDetails]
CandidateSearchSession(search_input: CandidateSearchInput)
```

All are exported from `fpg_core.candidate_search`. The session exposes
`has_remaining_trials`, `ask_next_trial()`, `record_score(suggestion, score)`, and
`best_result()` for consumer-controlled incremental evaluation.

### Inputs

- `CandidateSearchInput(targets, settings, evaluator)` requires unique targets and a
  callable `CandidateMap -> float` returning a finite score.
- `CandidateSearchTarget(room_id, room_type=None)` uses a non-empty string ID.
- `CandidateSearchSettings(grid, hallway_room_count_range, max_grid_node_count,
  trial_count, random_seed=None)`: counts are positive integers; max nodes is at least
  9; the prepared node count may not exceed it; at least one interior node is needed.
- Exactly `hallway_room_count_range.maximum` targets must be hallways, and the grid
  must have enough interior nodes for all non-hallways plus that maximum. The shared
  range always has `minimum=1`.

### Configuration

`trial_count` controls completed evaluations; larger values increase exploration and
runtime. `random_seed` makes Optuna sampling repeatable for a fixed environment.
`max_grid_node_count` is a safety cap, not a grid generator. `build_candidate_grid`
only validates and returns the supplied resolved grid.

### Recommended values

Use `build_candidate_search_targets(spec)` to avoid identity mistakes. Set a seed in
tests. No universal trial count exists; increase it only after measuring evaluator
cost and search quality. The only implementation-backed grid-node minimum is 9.

### Outputs

The production result has `candidate`, finite `score`, `completed_trials`, plus
convenience `points`, `grid`, and `hallway_room_count`. DEBUG details add the grid,
Optuna trial count, and completed count. Incremental calls return
`CandidateSuggestion` and `CandidateTrialResult` with trial number/candidate/score.

### Errors / failure conditions

Constructors raise `TypeError`/`ValueError` for bad types, duplicate targets,
impossible capacity, edge/misaligned points, or non-finite scores. Session misuse
(asking with a pending trial, recording the wrong/already recorded suggestion, or
requesting a best result too early) raises `CandidateSearchStateError`. Evaluator
exceptions propagate.

### Usage example

```python
from fpg_core.candidate_search import (
    CandidateSearchInput, CandidateSearchSettings,
    build_candidate_search_targets, search_candidates,
)

execution = search_candidates(CandidateSearchInput(
    targets=build_candidate_search_targets(specification),
    settings=CandidateSearchSettings(
        grid=resolved_grid,
        hallway_room_count_range=hallway_range,
        max_grid_node_count=250_000,
        trial_count=100,
        random_seed=42,
    ),
    evaluator=lambda candidate: -sum(point.x + point.y for point in candidate.points),
))
best_candidate = execution.result.candidate
```

### Important behavioral notes

One point represents one room, including hallways. Points are sampled without
replacement and never use the outer grid rows. Higher evaluator scores win. Only one
incremental suggestion may be pending.

## Candidate Circulation

### Purpose

Checks configured room-type routes over a candidate's exact grid, classifies hallway
traffic, and removes unused hallway points. Use it to assess and clean circulation
hint geometry without generating rooms or walls.

### Public API

```python
refine_candidate_circulation(
    circulation_input: CandidateCirculationInput,
    *, mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]
```

The feature root exports input/config/cost/rule contracts, route/hallway enums,
production result, DEBUG detail contracts, and
`CandidateCirculationError` subclasses.

### Inputs

- `CandidateCirculationInput(candidate: CandidateMap, config)`.
- `RoutingCostProfile(empty_node_cost, traversable_hint_node_cost, turn_cost,
  perimeter_bias_max_cost, traffic_conflict_cost)`. Movement costs are per entered
  node; positive costs must be finite and at most `1e12`; turn/perimeter costs may be
  zero; conflict cost must be positive.
- Each `CirculationRouteRule(id, name, source_room_type, destination_room_type,
  destination_selection, traffic_class, allowed_transit_room_types,
  importance_weight)` needs a unique non-negative integer ID, different source and
  destination types, unique transit types, and positive finite importance.
- `CandidateCirculationConfig` requires at least one route, unique IDs, unique
  always-traversable types, and `max_routing_passes=3` by default (allowed 2..10).

### Configuration

`ALL_MATCHING` routes every source to every matching destination;
`LOWEST_COST_MATCH` selects one lowest-cost match. Public/private traffic affects
hallway classification and conflict penalties. Lower routing costs make a node/path
property more attractive. `traffic_conflict_cost` discourages traffic-class conflicts
between passes. `importance_weight` weights route efficiency. Increasing passes can
allow classifications to stabilize, with a maximum of 10.

### Recommended values

The code recommends `max_routing_passes=3` through its default. Cost values are
relative and require project calibration; keep all movement/conflict costs positive.

### Outputs

Production `result.candidate` preserves the original grid but excludes unused hallway
points. `hallway_classifications` identifies retained hallway room/hint pairs as
public/private/mixed/unclassified. DEBUG details contain a 0..100 circulation
efficiency score, pass and grid counts, per-pass paths/cost breakdowns, final hallway
traffic, and removed points.

### Errors / failure conditions

Bad input/config raises `TypeError`, `ValueError`, or
`CandidateCirculationInputError`. All candidate points must be unique interior nodes
on a uniform grid of at most 250,000 nodes. Every route's source and destination type
must be present. Unresolvable configured routes raise
`CirculationPathNotFoundError`; coordinate mismatch raises `GridAlignmentError`.

### Usage example

```python
from fpg_core.candidate_circulation import (
    CandidateCirculationConfig, CandidateCirculationInput, RoutingCostProfile,
    refine_candidate_circulation,
)

config = CandidateCirculationConfig(
    costs=RoutingCostProfile(2.0, 0.75, 0.35, 1.5, 8.0),
    route_rules=(living_to_kitchen_rule,),
    always_traversable_room_types=(RoomType.HALLWAY,),
)
execution = refine_candidate_circulation(
    CandidateCirculationInput(candidate, config)
)
cleaned = execution.result.candidate
```

### Important behavioral notes

Routing is orthogonal between adjacent grid indexes. It does not create a separate
grid or mutate the input `CandidateMap`. Removed hallway identities must also be
removed from any room specification used later by the consumer.

## Candidate Scoring

### Purpose

Scores a candidate hint map on a 0..100 scale using independently configurable
critical and quality evaluators. Built-ins cover relative zone suitability, exterior
clearance, route relationship quality, and spatial distribution. Use it to rank
candidate points before room geometry exists.

### Public API

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

### Inputs

`CandidateScoringInput(specification, candidate, hallway_classifications=())` requires
typed matching contracts and unique hallway classification identities. Each
`EvaluatorRule(key, category, enabled=True, order=0, weight=1.0,
minimum_score=None, settings={})` selects a registered evaluator.

### Configuration

- `ScoringConfig.evaluator_rules` must be non-empty and unique. Enabled quality rules
  need positive weights; critical rules need a 0..100 `minimum_score`.
- `fail_fast_on_critical_failure=True` skips later evaluation after a failed critical
  threshold. `not_applicable_quality_contributes=False` excludes N/A weight rather
  than treating it as full credit. `raise_on_evaluator_error=False` converts
  unexpected evaluator failures to structured error results; `True` propagates them.
- `ZoneSuitabilityConfig(zone_count_per_axis=3, falloff_multiplier=1.5,
  valid_zones=DEFAULT_VALID_ZONES)` uses 1-based cells; a larger falloff multiplier
  penalizes distance from preferred cells faster.
- `ExteriorClearanceRule` chooses room types, required qualifying room count,
  positive corridor width, and front/back/left/right direction.
- `RelationshipQualityConfig` uses shared routing costs/rules and defaults hallways as
  always traversable.
- Spatial-distribution settings are passed in the evaluator rule mapping. Defaults are
  `nnd_weight=0.4`, `coverage_weight=0.6`, `nnd_cv_sensitivity=8`,
  `sample_count_per_axis=20`, and `gap_zero_score_ratio=1.5`; both weights must be
  non-negative with a positive sum, sensitivities positive, and samples at least 2.

### Recommended values

Start with `create_default_config()` and `create_default_registry()`. It uses weights
20/20/25 for zone/clearance/distribution and 20-unit clearance rules; these are
package baselines, not universal architectural standards. Use DEBUG metrics to
calibrate project-specific zones and weights.

### Outputs

`ScoringResult` contains `total_score` (0..100), `passed_critical_checks`,
`stopped_early`, optional `stop_reason`, evaluator executions, and findings. Each
execution reports raw score, configured/normalized weight, contribution, optional
threshold result, and status. DEBUG mode includes evaluator metrics/details;
PRODUCTION deliberately removes them.

### Errors / failure conditions

Handle the exception classes importable from
`fpg_core.candidate_scoring.exceptions` for invalid input/configuration,
registration, and evaluator contract violations. Missing evaluator keys, duplicate
rules, bad weights/thresholds/settings, non-finite/out-of-range scores, or DEBUG data
returned in PRODUCTION are invalid. Individual evaluators may be `NOT_APPLICABLE`.

### Usage example

```python
from fpg_core.candidate_scoring import (
    CandidateScoringInput, create_default_config, create_default_registry,
    evaluate_candidate,
)

result = evaluate_candidate(
    CandidateScoringInput(specification, candidate),
    registry=create_default_registry(),
    config=create_default_config(),
)
if result.passed_critical_checks:
    ranking_score = result.total_score
```

### Important behavioral notes

The default config does not enable relationship quality, although its evaluator is in
the default registry. Candidate scoring returns `ScoringResult` directly, not a
`FeatureExecution`. Zone and distribution grids are scoring overlays; relationship
routing alone uses `candidate.grid`.

## Floor Plan Solver

### Purpose

Generates non-overlapping rectangular room geometry that satisfies a canonical
generation specification and a selected generation profile. Optional candidate hints
guide initial generation; existing floor-plan geometry seeds refinement profiles.

### Public API

```python
generate_floor_plan(
    request: FloorPlanSolveRequest,
    *, registry: ConstraintRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanSolveExecution

FloorPlanSolver(registry: ConstraintRegistry | None = None)
FloorPlanSolver.solve(request, *, mode=ExecutionMode.PRODUCTION)
```

Preferred imports are from `fpg_core.floor_plan_solver`. It exports request/result and
diagnostic contracts; `GenerationProfile`, `HardConstraintUse`, `SoftConstraintUse`;
`SolverConfig`, `PreparationConfig`; built-ins `INITIAL_GENERATION_PROFILE`,
`REFINEMENT_A_PROFILE`, `REFINEMENT_B_PROFILE`, `DEFAULT_PROFILES`; and
`build_default_profiles()`. Custom-registry consumers may import `ConstraintRegistry`
from the public `fpg_core.floor_plan_solver.api` module. Advanced profile construction
also exposes `SeedPolicy`/`SeedSource` from `fpg_core.floor_plan_solver.config` and
`DefaultProfileSettings`/`ProfileCatalog` from
`fpg_core.floor_plan_solver.profiles`.

### Inputs

- `FloorPlanSolveRequest(specification, profile, candidate_hints=(),
  existing_floor_plan=None)`.
- The specification requires a positive finite floor; unique non-empty room IDs;
  `RoomType` values; positive compatible width/area ranges; and relations referencing
  known rooms with supported match policy/strength.
- `RoomPlacementHint(room_id, x, y, width=None, length=None)` uses project units;
  optional sizes must be positive. Unknown/duplicate hint room IDs are invalid.
  Out-of-bound hint values and sizes are clamped to feasible room/floor bounds.
- Existing-plan seed rooms with IDs absent from the specification are ignored.

### Configuration

- `SolverConfig(max_time_seconds=30, num_search_workers=0, random_seed=None,
  log_search_progress=False, relative_gap_limit=None, cp_model_presolve=True)`.
  Worker count 0 lets OR-Tools choose; gap is non-negative; times are seconds.
- `PreparationConfig(coordinate_scale=10)` controls integer precision. A scale of 10
  represents tenths of one project unit and increases model size.
- `GenerationProfile` names unique hard/soft constraint uses. Soft weights are
  positive integers. `without_constraints`, `with_hard_constraints`, and
  `with_soft_constraints` return modified immutable profiles.
- `SeedPolicy(source=NONE, require_source=False, apply_hints=True,
  position_tolerance=None, size_tolerance=None)` selects no seed, candidate hints, or
  an existing plan. `None` tolerance leaves that dimension unbounded, zero fixes it,
  and positive values bound movement/size in project units.
- Built-in profiles share hard rules for aspect ratios, hard relations, attached
  bathrooms, 60% coverage, hallway connectivity/8..10 width, front anchoring, back
  exposure, garage placement, and veranda front boundary. The initial profile uses
  optional candidate hints and a 5-second limit. Refinement A/B require existing-plan
  seeds, use 2-second limits and progressively tighter seed stability.

### Recommended values

The built-in profile catalog is the supported starter configuration. Its coordinate
scale is 1 for performance, minimum coverage is 0.6, adjacency/shared-wall baseline
is 10 units, and refinement tolerances start at 10 units (B halves them). Use
`build_default_profiles()` and calibrate only against domain/test evidence. For
repeatable tests set `random_seed` and `num_search_workers=1` on a copied profile.

### Outputs

`FloorPlanSolveExecution` is
`FeatureExecution[FloorPlanSolveResult, SolverDiagnostics]`. Result status is
`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID`, or `UNKNOWN`; `.solved` is true
only when a successful status also has a `FloorPlan`. The result also provides
`profile_name` and message. DEBUG diagnostics contain raw status, solver wall time,
objective/bound, conflicts, branches, applied constraints, and penalty terms.

### Errors / failure conditions

Invalid specification/profile/constraint IDs or a required missing seed raise
`FloorPlanSolverError` subclasses before solving. The base is exported at the feature
root; specific classes are importable from `fpg_core.floor_plan_solver.exceptions`.
Infeasibility, model invalidity,
and timeout/unknown outcomes are returned statuses and normally do not raise. Always
check `execution.result.solved` before reading the plan.

### Usage example

```python
from fpg_core.domain import ExecutionMode, RoomId
from fpg_core.floor_plan_solver import (
    INITIAL_GENERATION_PROFILE, FloorPlanSolveRequest, RoomPlacementHint,
    generate_floor_plan,
)

execution = generate_floor_plan(
    FloorPlanSolveRequest(
        specification=specification,
        profile=INITIAL_GENERATION_PROFILE,
        candidate_hints=(RoomPlacementHint(RoomId("living"), 20, 10),),
    ),
    mode=ExecutionMode.DEBUG,
)
if not execution.result.solved:
    raise RuntimeError(execution.result.message)
floor_plan = execution.result.floor_plan
```

### Important behavioral notes

Hints guide a solve; unless profile tolerances fix/bound them, they are not guaranteed
positions. `PRODUCTION` has `details=None`. Reuse `FloorPlanSolver` only when a custom
constraint registry is needed; it does not retain a solved-plan session.

## Floor Plan Post-Processing

### Purpose

Applies an ordered profile of geometry transformations to one solved floor plan, with
validation and rollback around every processor. Use it when a consumer needs the
built-in initial-generation cleanup or an explicitly registered custom processor
profile.

### Public API

```python
post_process_floor_plan(
    request: PostProcessingRequest,
    *, registry: ProcessorRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> PostProcessingExecution
```

The feature root exports the request/profile/result/execution/detail contracts,
processor extension contracts and registry, statuses, `NumericPolicy`,
`INITIAL_GENERATION_PROFILE`, and `create_default_registry()`.
Configuration classes for the built-in processors are importable from
`fpg_core.floor_plan_post_processing.config`.

### Inputs

`PostProcessingRequest(floor_plan, profile, specification=None)`. The plan boundary
and room polygons must be canonical, rooms must have unique IDs and names, standard
rooms may not overlap or leave the floor, parent/redirect/opening references must be
valid, and identity redirects must be acyclic. The specification is optional context
for processors.

### Configuration

- `PostProcessingProfile(name, processors, numeric=NumericPolicy(),
  reject_existing_openings=True)`.
- `NumericPolicy(tolerance=1e-6, grid_size=1.0)` requires positive values. Tolerance
  controls geometric comparisons/validation; grid size is the default snap interval.
- Each `ProcessorUse(processor_id, config, required=False,
  validate_after=False)` must resolve in the registry, use the processor's exact
  config type, appear once, and follow prerequisites. A required failure terminates
  the profile; `validate_after` checks the mutated plan immediately.
- The built-in profile orders veranda adjustment, wall extension, placeholder
  removal, hallway merge, grid snap, and rectilinear simplification. It rejects plans
  that already contain openings; placeholder removal and grid snap are required and
  validated.
- `VerandaAdjustmentConfig(transformation_version='veranda_adjustment:v1')` and
  `PlaceholderRemovalConfig`/`RectilinearSimplificationConfig` have no tuning beyond
  identity/version behavior.
- `HallwayMergeConfig(minimum_shared_wall=10)` sets the minimum shared project-unit
  wall for merging hallway rooms. `GridSnapConfig(grid_size=None)` uses the profile's
  numeric grid when `None`, otherwise a positive per-processor grid size.
- `WallExtensionConfig(rules=..., transformation_version='wall_extension:v1')` uses
  `WallExtensionRule(room_type, min_wall_length, max_wall_length, max_rooms,
  max_selections, expansion_percentage, max_distance)`. Defaults cover veranda,
  living room, kitchen, hallway, and bedroom with positive values; room types must be
  unique and minimum wall length may not exceed maximum.

### Recommended values

Use `INITIAL_GENERATION_PROFILE` for the solver's initial output. Its numeric defaults
(`1e-6`, `1.0`) are the implementation-backed baseline. Custom processor tuning is
extension-specific; do not alter ordering without satisfying declared prerequisites.

### Outputs

`PostProcessingExecution` is
`FeatureExecution[PostProcessingResult, PostProcessingDetails]`. Result has
`SUCCESS`/`FAILED`, the current/restored `floor_plan`, and optional
`ProcessingFailure(code, message, processor_id)`. DEBUG details contain ordered
`ProcessorExecution`s with status, duration milliseconds, rollback flag, outcome,
affected IDs, redirects, metrics, or failure.

### Errors / failure conditions

Expected request, configuration, validation, and processor failures are normally
captured in a `FAILED` result. Required failures stop; optional failures are rolled
back and later independent processors may run. A failed prerequisite causes a skip.
Severe rollback failure also returns failure. A non-`ExecutionMode` mode raises
`TypeError`. Exception classes used by custom processors are importable from
`fpg_core.floor_plan_post_processing.exceptions`.

### Usage example

```python
from fpg_core.floor_plan_post_processing import (
    INITIAL_GENERATION_PROFILE, PipelineStatus, PostProcessingRequest,
    post_process_floor_plan,
)

execution = post_process_floor_plan(PostProcessingRequest(
    floor_plan=solved_plan,
    profile=INITIAL_GENERATION_PROFILE,
    specification=specification,
))
if execution.result.status is not PipelineStatus.SUCCESS:
    raise RuntimeError(execution.result.failure)
processed_plan = execution.result.floor_plan
```

### Important behavioral notes

The supplied `FloorPlan` is the mutable working object; successful changes are
observable through the original object. A failing processor restores its snapshot.
Run geometry-changing profiles before openings unless the profile explicitly permits
and preserves existing openings.

## Floor Plan Openings

### Purpose

Analyzes finalized rectilinear room walls and places interior doors, exterior doors,
and windows according to an opening profile. Use it to obtain a new completed
`FloorPlan` with typed opening segments and room connections.

### Public API

```python
generate_openings(
    request: OpeningGenerationRequest,
    *, registry: OpeningFeatureRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> OpeningGenerationExecution
```

The feature root exports profile/config contracts, request/result/diagnostics/status,
`DEFAULT_OPENING_PROFILE`, registry creation/extension contracts, and base
`OpeningGenerationError`.

### Inputs

`OpeningGenerationRequest(floor_plan, profile)` requires finite canonical rectilinear
floor/room polygons; positive area; unique room IDs; standard rooms inside the floor
without area overlap; and no existing openings. Adjacent/shared and
exterior walls must be long enough for configured openings and clearances.

### Configuration

- `OpeningGenerationProfile(name, enabled_features=('interior_doors',
  'exterior_doors', 'windows'), enabled_constraints=('shared_placement',
  'room_door_limits'), geometry=..., dimensions=..., policy=..., objective=...,
  solver=...)`. IDs must be unique; `shared_placement` is mandatory.
- `GeometryConfig(coordinate_scale=10, tolerance=1e-6, corner_clearance=0,
  window_spacing=5)`: integer precision, geometry tolerance, distance from wall
  corners, and minimum gap involving windows.
- `DimensionConfig(door_width=8, window_width=16,
  minimum_shared_wall=10)` uses positive project-unit lengths.
- `FeaturePolicy` controls allowed interior room-type pairs, positive per-type door
  caps, secondary entrance preference, window-eligible types, and complete cardinal
  side priorities. Each priority must contain south/east/north/west exactly once.
- `ObjectiveConfig.tier_order` sets unique lexicographic preference tiers.
- Opening `SolverConfig(max_time_seconds=10, num_search_workers=1, random_seed=0,
  cp_model_presolve=True, log_search_progress=False)`.

### Recommended values

Start with `DEFAULT_OPENING_PROFILE`; all numeric defaults above are package-backed
starter values. Preserve one worker and seed 0 for deterministic tests. Widths and
room-pair policies require project/domain calibration if the default units or access
rules do not fit the consumer.

### Outputs

`OpeningGenerationExecution` is
`FeatureExecution[OpeningGenerationResult, OpeningDiagnostics]`. Status includes
`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID`, `UNKNOWN`, and `INVALID_INPUT`;
`.solved` additionally requires a plan. The returned plan contains
`FloorPlanOpening(id, opening_type, purpose, start, end, connected_room_ids)`.
DEBUG diagnostics include solver statistics, analyzed wall/demand/candidate/selection
counts, applied constraints/objective terms, and structured issues.

### Errors / failure conditions

Invalid floor geometry is returned as `INVALID_INPUT` with no plan and, in DEBUG, an
`invalid_input` issue. Infeasibility/model/timeout are statuses. Invalid profiles,
unknown registry IDs, and extraction invariants raise `OpeningGenerationError`
subclasses (specific classes are importable from
`fpg_core.floor_plan_openings.exceptions`). Always check `.solved`.

### Usage example

```python
from fpg_core.floor_plan_openings import (
    DEFAULT_OPENING_PROFILE, OpeningGenerationRequest, generate_openings,
)

execution = generate_openings(OpeningGenerationRequest(
    floor_plan=finalized_plan,
    profile=DEFAULT_OPENING_PROFILE,
))
if not execution.result.solved:
    raise RuntimeError(execution.result.message)
plan_with_openings = execution.result.floor_plan
```

### Important behavioral notes

The source plan is never mutated. Opening IDs and selected placements are generated
for the returned copy. `PRODUCTION` omits diagnostics. Side priorities use global
south/east/north/west coordinates.

## Floor Plan Scoring

### Purpose

Scores completed room geometry against its generation specification. Built-ins check
critical geometry integrity, required adjacency, enclosed voids, and inward recesses,
then functional living-room balance, bedroom area/consistency, and kitchen-dining
proximity. Use it for a final 0..100 quality assessment and structured findings.

### Public API

```python
score_floor_plan(
    scoring_input: FloorPlanScoringInput,
    *, registry: EvaluatorRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanScoringExecution

create_default_profile() -> ScoringProfile
create_default_registry() -> EvaluatorRegistry
```

The feature root exports group/evaluator keys, rule/profile contracts, evaluator and
settings classes, registry/context extension contracts, result/detail/finding/metric
contracts, statuses, default profile, and all scoring exception classes.

### Inputs

`FloorPlanScoringInput(floor_plan, specification, profile)` requires a typed plan and
the specification that defines room IDs, size ranges, and relations. Plan rooms need
valid finite polygon geometry and IDs consistent with specification or valid identity
redirects.

### Configuration

- `ScoringProfile(groups, evaluators)` requires at least one group, unique keys,
  finite positive weights, and exactly one enabled `critical` gate that executes no
  later than other groups. Every enabled group needs an enabled evaluator.
- `ScoringGroupRule(key, enabled=True, order=0, weight=1)` controls execution order and
  allocation of the 100-point total.
- `EvaluatorRule(key, group_key, settings, enabled=True, order=0, weight=1,
  minimum_score=None)`: critical rules require a 0..100 minimum; non-critical rules
  forbid it. Settings must exactly match the evaluator's settings class.
- Default settings: geometry tolerance `1e-6`; required shared boundary `10`;
  enclosed-void area tolerance `1e-6`; maximum inward recess `20`; living-room
  maximum excess ratio `2`; bedroom area/consistency weights `3/1`, full-spread ratio
  `0.5`, max penalty `40`; kitchen-dining shared boundary `10`, maximum centroid
  distance `2000`, tolerance `1e-6`.

### Recommended values

Use `create_default_profile()`/`DEFAULT_SCORING_PROFILE` as the implementation-backed
baseline. All four critical checks require 100 by default. The critical and functional
groups each receive equal weight; applicable evaluator weights within a group are
normalized. Calibrate length thresholds if project units differ from those assumed by
the supplied defaults.

### Outputs

`FloorPlanScoringExecution` is
`FeatureExecution[FloorPlanScoringResult, FloorPlanScoringDetails]`. Result contains
`total_score` (0..100), `passed_critical`, and optional `critical_failure`. DEBUG
details contain group statuses/raw scores/contributions, evaluator status/raw score/
normalized weight/contribution/threshold, findings, metrics with units, and optional
visualization payloads.

### Errors / failure conditions

`FloorPlanScoringError` subclasses cover structurally broken input, inconsistent
profiles, registry errors, evaluator contract violations, and unexpected evaluator
execution. A critical score below threshold is a normal result: `passed_critical` is
false, later groups are `SKIPPED`, and total contains only earned critical
contribution. `NOT_APPLICABLE` evaluators redistribute weight among applicable ones;
if no critical evaluator applies, scoring raises `EvaluatorExecutionError`.

### Usage example

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_scoring import (
    FloorPlanScoringInput, create_default_profile, score_floor_plan,
)

execution = score_floor_plan(
    FloorPlanScoringInput(
        floor_plan=completed_plan,
        specification=specification,
        profile=create_default_profile(),
    ),
    mode=ExecutionMode.DEBUG,
)
score = execution.result.total_score
```

### Important behavioral notes

Scoring never mutates the plan. Openings do not affect the current built-in scores.
In PRODUCTION, result findings remain consumer-safe while evaluator metrics and
visualization payloads are omitted with `details=None`.
