# fpg-core Consumer Package Reference

This reference describes the supported, installed-package surface of the current
`fpg-core` source tree. Feature-root imports such as `fpg_core.floor_plan_solver` are the preferred
imports. Shared geometry, floor-plan, candidate, and generation-specification
contracts are exported by `fpg_core.domain`.

Unless a project defines a conversion externally, lengths are expressed in the
consumer's project units, areas in square project units, and coordinates in the same
coordinate system as the supplied boundary. `ExecutionMode.PRODUCTION` is the
default for features returning `FeatureExecution`; `DEBUG` adds details but does not
change the result contract.

## Package Overview

`fpg-core` 0.1.0 is a synchronous Python library of typed domain contracts and
computational features for residential floor-plan generation. The supported
dependency direction is `consumer application -> fpg-core`. Consumers provide
configuration and request data and own orchestration, HTTP/API transport, persistence,
databases, jobs, cancellation, retries, logging, artifacts, UI, and deployment. The
package performs no hidden file, network, environment, or application-state I/O.

The package exposes independent features for buildable and usable land, input
preparation, candidate search/circulation/scoring, CP-SAT floor-plan solving,
post-processing, opening generation, and final-plan scoring. It does not expose a
mandatory end-to-end pipeline, server, CLI, storage layer, or configuration loader.

## Installation and Compatibility

### Python and distribution metadata

- Distribution name/version: `fpg-core` `0.1.0` from `pyproject.toml`.
- Python requirement: `>=3.11`; classifiers explicitly list Python 3.11 and 3.12.
- Package layout: `src/fpg_core`; build backend: `setuptools.build_meta`.
- The repository does not establish a public package-index URL. From a checkout,
  install with `python -m pip install -e .`; use `python -m pip install -e ".[dev]"`
  only when development tools are wanted.
- `src/fpg_core/py.typed` is packaged, so type checkers may treat the distribution as
  typed.

| Runtime dependency | Constraint | Consumer-visible role |
|---|---:|---|
| `optuna` | `>=3.6` | candidate-search optimization and seeded trials |
| `ortools` | `>=9.10` | CP-SAT floor-plan and opening solvers |
| `shapely` | `>=2.0` | geometry validation, transformation, and scoring |

The package version fallback in an uninstalled source checkout is `0.2.0`; installed
distributions report their metadata version. Consumers should use distribution
metadata as authoritative and should not infer compatibility from the fallback.

## Public Import Conventions

Use `fpg_core.<feature>` for feature operations and feature-owned contracts. Use
`fpg_core.domain` for canonical shared geometry, land, grid, generation-specification,
floor-plan, execution, ID, and enum contracts. The package root intentionally exports
only version/configuration conveniences. Implementation submodules are not preferred
consumer imports unless a feature section explicitly identifies a compatibility
surface.

### Package-wide aggregate configuration

`FpgCoreConfig` is an optional immutable aggregation boundary; individual operations
still receive only their feature config. It has no defaults:

```python
FpgCoreConfig(
    schema_version: int,
    project_units_per_meter: int,
    buildable_space: BuildableSpaceConfig,
    preprocessing: PreprocessingConfig,
    candidate_search: CandidateSearchConfig,
    candidate_scoring: candidate_scoring.ScoringConfig,
    floor_plan_solver: floor_plan_solver.ProfileCatalog,
    post_processing: floor_plan_post_processing.PostProcessingProfile,
    openings: floor_plan_openings.OpeningGenerationProfile,
    floor_plan_scoring: floor_plan_scoring.FloorPlanScoringConfig,
)
```

`validate_fpg_core_config(config) -> None` accepts only `FpgCoreConfig`, requires
`schema_version == 2` and positive `project_units_per_meter`, then validates all
cross-feature registries and policies. It requires usable-land values greater than
zero; buildable vertex limits of at least four with a positive coordinate cap;
candidate grids capped at no fewer than nine nodes; unique/consistent preprocessing
rules, ratios, and size ranges; known solver constraints; valid ordered processors;
known opening features/constraints; and known floor-plan scoring groups/evaluators.
It returns `None` on success and raises `FpgCoreConfigError` (a `ValueError`) on
failure. It does not load configuration from disk or the environment.

`BuildableSpaceConfig(active_profile, usable_land_constraints, validation_limits)`
collects the three shared buildable/usable-land policies. The package-root
`CandidateSearchConfig` and `PreprocessingConfig` are the same canonical classes
exported by their feature roots. `canonical_aspect_ratio` is also re-exported as a
convenience.

## Global Units and Geometry Conventions

- The package does not impose metres, feet, or another physical unit. All coordinates,
  lengths, widths, tolerances, and distances for a request use the same project unit;
  areas use square project units. `project_units_per_meter` is consumer-supplied
  reference metadata and must be a positive integer.
- Points use Cartesian `(x, y)` coordinates. `Polygon.points` is the ordered boundary;
  feature validators state when closure, orientation, convexity, rectilinearity, or
  grid alignment is required.
- Solver `coordinate_scale` values convert project coordinates into integer CP-SAT
  units. Larger scales preserve more fractional precision and increase model size.
- `RoomId`, `OpeningId`, `EvaluatorKey`, and `GroupKey` are `NewType` string identities:
  construct them from strings; runtime values remain strings.
- Frozen dataclasses are immutable shallow contracts. `FloorPlan` and its `rooms`,
  `openings`, `identity_redirects`, and `applied_transformations` collections are
  intentionally mutable and use per-instance factories.

## Execution Modes and Common Return Envelopes

`ExecutionMode` has exactly `PRODUCTION = "production"` and `DEBUG = "debug"`.
Features returning `FeatureExecution[TResult, TDetails]` always return
`result`, `details`, and `metadata`. `metadata` is
`ExecutionMetadata(mode: ExecutionMode, duration_seconds: float)`. PRODUCTION returns
the same result type with `details=None`; DEBUG returns the documented detail type.
Candidate scoring is the sole feature here that returns its `ScoringResult` directly
and accepts the mode only for evaluator context/debug payload policy.

| Mode | Main result | `details` | Metadata |
|---|---|---|---|
| `PRODUCTION` | always the feature result contract | `None` | mode and total duration |
| `DEBUG` | identical result contract | feature-specific details | mode and total duration |

Returned failure statuses are normal results and are distinct from raised validation,
configuration, registry, and processing exceptions. Each feature section identifies
which mechanism it uses.

## Feature Index

| Feature | Preferred operation | Input/config boundary | Return |
|---|---|---|---|
| Buildable Land | `calculate_buildable_land` | `BuildableLandInput(request, config)` | `FeatureExecution[BuildableLandResult, BuildableLandDetails]` |
| Usable Land | `find_usable_land` | `UsableLandInput(buildable_land, land, config)` | `FeatureExecution[UsableLand, UsableLandDetails]` |
| Floor Plan Preprocessing | `prepare_generation_input` | `PreprocessingInput(request, config)` | `PreprocessingExecution` |
| Candidate Search | `search_candidates` | `CandidateSearchInput(targets, grid, hallway_room_count_range, evaluator, config)` | `FeatureExecution[CandidateSearchResult, CandidateSearchDetails]` |
| Candidate Circulation | `refine_candidate_circulation` | `CandidateCirculationInput(candidate, config)` | `FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]` |
| Candidate Scoring | `evaluate_candidate` | request plus keyword `registry`/`config` | `ScoringResult` |
| Floor Plan Solver | `generate_floor_plan` | `FloorPlanSolveRequest(specification, config, candidate_hints=(), existing_floor_plan=None)` | `FloorPlanSolveExecution` |
| Floor Plan Post-Processing | `post_process_floor_plan` | `PostProcessingRequest(floor_plan, config, specification=None)` | `PostProcessingExecution` |
| Floor Plan Openings | `generate_openings` | `OpeningGenerationRequest(floor_plan, config)` | `OpeningGenerationExecution` |
| Floor Plan Scoring | `score_floor_plan` | `FloorPlanScoringInput(floor_plan, specification, config)` | `FloorPlanScoringExecution` |

### Complete reusable example objects

Several feature examples below reuse these fully constructed public contracts. Copy
this block first when running an example that names an `example_*` value.

```python
from fpg_core.domain import (
    CandidateMap, CandidatePoint, CirculationRouteRule,
    CirculationTrafficClass, DestinationSelection, FloorPlan,
    FloorPlanGenerationSpec, FloorPlanRoom, FloorSpec, HallwayRoomCountRange,
    Point, Polygon, ResolvedCandidateGrid, RoomId, RoomSizeSpec, RoomSpec,
    RoomType,
)

def rectangle(x1: float, y1: float, x2: float, y2: float) -> Polygon:
    return Polygon((Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)))

example_specification = FloorPlanGenerationSpec(
    floor=FloorSpec(width=40, length=20),
    rooms=(
        RoomSpec(RoomId("living"), RoomType.LIVING_ROOM, "Living",
                 RoomSizeSpec(5, 20, 40, 400)),
        RoomSpec(RoomId("kitchen"), RoomType.KITCHEN, "Kitchen",
                 RoomSizeSpec(5, 15, 40, 200)),
        RoomSpec(RoomId("hallway"), RoomType.HALLWAY, "Hallway",
                 RoomSizeSpec(5, 10, 20, 200)),
    ),
    room_relations=(),
)
example_grid = ResolvedCandidateGrid(
    x_positions=(0, 5, 10, 15, 20, 25, 30, 35, 40),
    y_positions=(0, 5, 10, 15, 20),
)
example_hallway_range = HallwayRoomCountRange(maximum=1, minimum=1)
example_candidate = CandidateMap(
    grid=example_grid,
    points=(
        CandidatePoint(RoomId("living"), 5, 5, RoomType.LIVING_ROOM),
        CandidatePoint(RoomId("kitchen"), 25, 5, RoomType.KITCHEN),
        CandidatePoint(RoomId("hallway"), 35, 5, RoomType.HALLWAY),
    ),
)
example_floor_plan = FloorPlan(
    boundary=rectangle(0, 0, 40, 20),
    rooms=[
        FloorPlanRoom(RoomId("living"), RoomType.LIVING_ROOM, "Living",
                      rectangle(0, 0, 20, 20)),
        FloorPlanRoom(RoomId("kitchen"), RoomType.KITCHEN, "Kitchen",
                      rectangle(20, 0, 30, 20)),
        FloorPlanRoom(RoomId("hallway"), RoomType.HALLWAY, "Hallway",
                      rectangle(30, 0, 40, 20)),
    ],
)
example_route_rule = CirculationRouteRule(
    id=1,
    name="living-to-kitchen",
    source_room_type=RoomType.LIVING_ROOM,
    destination_room_type=RoomType.KITCHEN,
    destination_selection=DestinationSelection.ALL_MATCHING,
    traffic_class=CirculationTrafficClass.PUBLIC,
    allowed_transit_room_types=(RoomType.HALLWAY,),
    importance_weight=1.0,
)
```

## Buildable Land

### Purpose

Validates and normalizes one convex parcel with one entry-road attachment, classifies
its sides relative to that road, applies setbacks, and returns the legal/build-policy
envelope. Processing data and reusable policy are separated in `BuildableLandInput`.

### Public API

```python
calculate_buildable_land(
    buildable_input: BuildableLandInput,
    *, mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[BuildableLandResult, BuildableLandDetails]
```

Import `BuildableLandInput`, `BuildableLandConfig`, result/detail contracts,
`BuildableLandError`, and the operation from `fpg_core.buildable_land`. Shared land
contracts and `ExecutionMode` come from `fpg_core.domain`.

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
- `BuildableLandInput(request, config)` requires exact
  `BuildableSpaceRequestData` and `BuildableLandConfig` instances.
- `SetbackProfile` contains `name`, `status`, `description`, calculation mode,
  `base_setbacks: Mapping[LandSide, int]`, and nested road adjustments. Current
  calculation mode is `BASE_PLUS_ROAD_ADJUSTMENT`. Setbacks are lengths in project
  units.

### Configuration

- `BuildableLandConfig(setback_profile, validation_limits)` contains only reusable
  behavior controls. `ValidationLimits.minimum_vertex_count`, `maximum_vertex_count`, and
  `maximum_absolute_coordinate` control accepted parcel complexity and coordinate
  bounds.
- `base_setbacks` sets the inward distance for front/back/left/right edges.
- `road_adjustments[road_type][side]` is added only on the attached road edge.

### Recommended values

The implementation provides no universal setback or validation profile. Use values
from the consumer's jurisdiction/reference dataset; all four `LandSide` values and
each accepted `RoadType` need mapping entries.

### Outputs

The return envelope always contains `BuildableLandResult(buildable_land,
normalized_land)`. `NormalizedLand` has a counter-clockwise boundary, normalized
`LandEdge`s retaining `source_edge_index`, and `main_entry_road`. `BuildableLand`
has `boundary`, `area`, and one `EdgeSetback` per source edge. DEBUG adds
`BuildableLandDetails(edge_classifications)`; PRODUCTION sets `details=None`.

### Errors / failure conditions

Invalid contract types raise `TypeError`/`ValueError`. Geometry/domain failures raise
`BuildableLandError`; inspect `.code: BuildableSpaceErrorCode` and
`.message`. Codes cover invalid/non-convex/self-intersecting boundaries, bad or
unsupported road attachments, setbacks that eliminate the parcel, and final geometry
failure. Road edge indexes must be in `0..vertex_count-1`.

### Usage example

```python
from fpg_core.buildable_land import (
    BuildableLandConfig, BuildableLandInput, calculate_buildable_land,
)
from fpg_core.domain import (
    BuildableSpaceRequestData, ExecutionMode, LandSide, Point, Polygon, RoadAttachment,
    RoadRole, RoadType, SetbackCalculationMode, SetbackProfile,
    ValidationLimits,
)

profile = SetbackProfile(
    name="residential", status="active", description="Local residential rules",
    calculation_mode=SetbackCalculationMode.BASE_PLUS_ROAD_ADJUSTMENT,
    base_setbacks={side: 5 for side in LandSide},
    road_adjustments={RoadType.MAIN_ROAD: {side: 0 for side in LandSide}},
)
config = BuildableLandConfig(
    setback_profile=profile,
    validation_limits=ValidationLimits(4, 12, 100_000),
)
request = BuildableSpaceRequestData(
    land_boundary=Polygon((Point(0, 0), Point(100, 0), Point(100, 80), Point(0, 80))),
    roads=(RoadAttachment(0, RoadRole.MAIN_ENTRY, RoadType.MAIN_ROAD),),
)
execution = calculate_buildable_land(
    BuildableLandInput(request=request, config=config),
    mode=ExecutionMode.DEBUG,
)
buildable_land = execution.result.buildable_land
normalized_land = execution.result.normalized_land
```

### Important behavioral notes

Inputs are not mutated. The normalized boundary may reverse orientation while source
edge identity remains stable. Side meaning is road-relative, not a global compass
direction. The operation is deterministic for fixed input/configuration.

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
    usable_input: UsableLandInput,
    *, mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[UsableLand, UsableLandDetails]
```

### Inputs

- `UsableLandInput(buildable_land, land, config)` requires a `BuildableLand`, its
  corresponding `NormalizedLand`, and `UsableLandConfig`.
- `UsableLandConfig(minimum_width, minimum_length, search_resolution,
  maximum_sweep_lines)` requires positive integers. Distances use project units.
  `UsableLandConfig.from_constraints(UsableLandConstraints(minimum_width,
  minimum_length, search_resolution, maximum_sweep_lines))` is the supported
  compatibility conversion. Width is defined
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

The result is `UsableLand` with world-coordinate `boundary`, integer `width`,
`length`, and `area`, alignment (`PARALLEL_TO_ENTRY_ROAD` or
`PERPENDICULAR_TO_ENTRY_ROAD`), and original `entry_road_edge_index`. DEBUG adds
`UsableLandDetails`: evaluated pair count, local buildable/selected boundaries, and
the road-aligned transform origin and axes. PRODUCTION sets `details=None`.

### Errors / failure conditions

Invalid input/config types raise `TypeError`/`ValueError`. `UsableLandError` exposes
`.code`, `.message`, and `.details`. Handle
`NO_USABLE_LAND_FOUND`, `SEARCH_LIMIT_EXCEEDED`, and
`USABLE_LAND_CALCULATION_FAILED`.

### Usage example

```python
from fpg_core.domain import ExecutionMode
from fpg_core.usable_land import UsableLandConfig, UsableLandInput, find_usable_land

execution = find_usable_land(UsableLandInput(
    buildable_land=buildable_land,
    land=normalized_land,
    config=UsableLandConfig(30, 40, 1, 1000),
), mode=ExecutionMode.DEBUG)
usable = execution.result
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
    AspectRatioRule, FloorLimits, PreprocessingConfig, PreprocessingInput,
    PreprocessingRequest, RequestedRoom, RoomCountRule, RoomSizeReference,
    prepare_generation_input,
)

preprocessing_config = PreprocessingConfig(
    room_count_rules=(RoomCountRule(RoomType.LIVING_ROOM, 1, 1),),
    supported_aspect_ratios=(AspectRatioRule("4:5", 0.8),),
    room_sizes=(RoomSizeReference(
        RoomType.LIVING_ROOM, "medium", 10, 30, 100, 500,
    ),),
    room_relations=(),
    mandatory_room_types=(RoomType.LIVING_ROOM,),
    floor_area_buffer=1,
    hallway_area_buffer=1,
    max_hallway_room_count=1,
    hallway_min_width=8,
    candidate_search_grid_spacing=2,
    default_room_size="medium",
    max_aspect_residual_units=10,
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
`has_remaining_trials: bool`, `has_pending_trial: bool`, `remaining_trials: int`,
`completed_trials: int`, `optuna_trial_count: int`, `grid`, and `search_input`
properties, plus `ask_next_trial() -> CandidateSuggestion`,
`record_score(suggestion: CandidateSuggestion, score: float) -> CandidateTrialResult`,
`run_next_trial() -> CandidateTrialResult`, `fail_pending_trial() -> None`,
`best_result() -> CandidateSearchResult`, and
`debug_details() -> CandidateSearchDetails` for incremental evaluation.

### Inputs

- `CandidateSearchInput(targets, grid, hallway_room_count_range, evaluator, config)`
  requires unique targets and a callable `CandidateMap -> float` returning a finite
  score. The grid and hallway range are processing input; `config` controls search.
- `CandidateSearchTarget(room_id, room_type=None)` uses a non-empty string ID.
- `CandidateSearchConfig(trial_count=500, max_grid_node_count=250_000,
  random_seed=None)`: counts are positive integers; max nodes is at least 9; the
  prepared node count may not exceed it; at least one interior node is needed.
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
    CandidateSearchConfig, CandidateSearchInput,
    build_candidate_search_targets, search_candidates,
)

execution = search_candidates(CandidateSearchInput(
    targets=build_candidate_search_targets(example_specification),
    grid=example_grid,
    hallway_room_count_range=example_hallway_range,
    config=CandidateSearchConfig(
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

Checks configured room-type routes over the exact `CandidateMap.grid`, classifies
hallway traffic, removes unused hallway hints, and can conservatively consolidate
nearby retained hallway hints. It does not generate a second grid and does not mutate
the supplied `CandidateMap`.

### Public API

```python
refine_candidate_circulation(
    circulation_input: CandidateCirculationInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]
```

Preferred imports are from `fpg_core.candidate_circulation`. The feature root exports
the input/config/result contracts, routing cost and route-rule contracts, traffic
enums, hallway cleanup configuration and DEBUG contracts, compatibility aliases
`TrafficClass` and `GridNode`, and the documented exception family.

### Inputs

```python
CandidateCirculationInput(
    candidate: CandidateMap,
    config: CandidateCirculationConfig,
)
```

`candidate.grid` is the exact routing grid. Candidate points must be unique, aligned
to that grid, and located on valid interior nodes. The feature supports at most
250,000 grid nodes. Route source and destination room types referenced by configured
rules must exist in the candidate.

### Configuration

```python
RoutingCostProfile(
    empty_node_cost: float,
    traversable_hint_node_cost: float,
    turn_cost: float,
    perimeter_bias_max_cost: float,
    traffic_conflict_cost: float,
)

CirculationRouteRule(
    id: int,
    name: str,
    source_room_type: RoomType,
    destination_room_type: RoomType,
    destination_selection: DestinationSelection,
    traffic_class: CirculationTrafficClass,
    allowed_transit_room_types: tuple[RoomType, ...],
    importance_weight: float,
    required_transit_room_types: tuple[RoomType, ...] = (),
)

HallwayConsolidationConfig(
    enabled: bool = True,
    minimum_separation_grid_steps: float = 2.0,
    max_route_cost_increase_ratio: float = 0.15,
)

CandidateCirculationConfig(
    costs: RoutingCostProfile,
    route_rules: tuple[CirculationRouteRule, ...],
    always_traversable_room_types: tuple[RoomType, ...],
    max_routing_passes: int = 3,
    hallway_consolidation: HallwayConsolidationConfig = HallwayConsolidationConfig(),
)
```

Validation and meaning:

- `RoutingCostProfile.empty_node_cost` and `traversable_hint_node_cost` must be
  positive finite values. `turn_cost` and `perimeter_bias_max_cost` must be finite and
  non-negative. `traffic_conflict_cost` must be positive and finite. Routing cost
  values are capped by the implementation's numerical safety limit of `1e12`.
- `CirculationRouteRule.id` must be a unique non-negative integer in the config;
  `name` must be non-empty; source and destination room types must be different;
  `importance_weight` must be positive and finite.
- `allowed_transit_room_types` and `required_transit_room_types` must each contain
  unique `RoomType` values. A required-transit type cannot be the route's source or
  destination type.
- `DestinationSelection.ALL_MATCHING` resolves one route from each source to every
  matching destination. `LOWEST_COST_MATCH` selects one lowest-cost reachable
  destination per source.
- `CirculationTrafficClass` values are `PUBLIC='public'` and `PRIVATE='private'`.
- `always_traversable_room_types` must contain unique `RoomType` members.
- `max_routing_passes` defaults to `3` and must be between `2` and `10` inclusive.

#### Required transit / “must cross”

When `required_transit_room_types` is non-empty, a resolved route must cross at least
one intermediate candidate point whose room type is one of those configured types
before reaching the destination. This is an **any-of** requirement: a tuple containing
multiple room types does not require the path to cross every listed type.

Required-transit types are automatically traversable for that route; consumers do not
also need to repeat them in `allowed_transit_room_types` or
`always_traversable_room_types`.

Example:

```python
CirculationRouteRule(
    id=7,
    name="living-to-bathroom-via-hallway",
    source_room_type=RoomType.LIVING_ROOM,
    destination_room_type=RoomType.BATHROOM,
    destination_selection=DestinationSelection.LOWEST_COST_MATCH,
    traffic_class=CirculationTrafficClass.PUBLIC,
    allowed_transit_room_types=(),
    importance_weight=1.0,
    required_transit_room_types=(RoomType.HALLWAY,),
)
```

#### Hallway consolidation

Unused hallway hints are removed first. If `hallway_consolidation.enabled=True`, the
feature then evaluates retained hallway hints that are close to another hallway hint.
A hallway is removed only after rerouting confirms that configured route coverage is
preserved and route cost degradation stays within the configured limit.

`minimum_separation_grid_steps` is measured as Euclidean distance in grid-index space,
not project-unit distance. A candidate is considered “nearby” when its distance is
strictly less than the configured value. With the default `2.0`, orthogonally adjacent
and diagonally adjacent hallway hints are eligible; points exactly two grid steps
apart are not.

`max_route_cost_increase_ratio` is the maximum allowed relative increase in route cost
compared with the baseline after unused hallway removal. It must be finite and in
`0.0..1.0`; the default `0.15` allows at most a 15% increase. Setting
`HallwayConsolidationConfig(enabled=False)` preserves the previous unused-only cleanup
behavior.

The consolidation decision values exposed in DEBUG are:

- `HallwayConsolidationDecision.REMOVED = 'removed'`
- `HallwayConsolidationDecision.KEPT_ROUTE_UNAVAILABLE = 'kept_route_unavailable'`
- `HallwayConsolidationDecision.KEPT_ROUTE_COVERAGE_CHANGED = 'kept_route_coverage_changed'`
- `HallwayConsolidationDecision.KEPT_ROUTE_COST_INCREASE = 'kept_route_cost_increase'`

Removal reasons are:

- `HallwayRemovalReason.UNUSED = 'unused'`
- `HallwayRemovalReason.CONSOLIDATED = 'consolidated'`

### Recommended values

**Package defaults:** `max_routing_passes=3`, hallway consolidation enabled,
`minimum_separation_grid_steps=2.0`, and `max_route_cost_increase_ratio=0.15`.
Routing costs are relative and need project calibration. If preserving every retained
hallway hint is more important than compactness, disable consolidation rather than
raising the route-cost tolerance arbitrarily.

### Outputs

Production result:

```python
CandidateCirculationResult(
    candidate: CandidateMap,
    hallway_classifications: tuple[HallwayClassification, ...] = (),
)
```

`result.candidate` preserves the original `ResolvedCandidateGrid` and removes hallway
points classified as unused or safely consolidated. `hallway_classifications`
contains the classifications for hallway hints retained in the production candidate.

In `ExecutionMode.PRODUCTION`, `execution.details is None`.

In `ExecutionMode.DEBUG`, details are:

```python
CandidateCirculationDetails(
    circulation_efficiency_score: float,
    routing_pass_count: int,
    grid_node_count: int,
    passes: tuple[RoutingPassDetails, ...],
    final_hallway_traffic: tuple[HallwayTrafficDetails, ...],
    removed_hallway_points: tuple[RemovedHallwayPointDetails, ...],
    hallway_consolidation_attempts: tuple[HallwayConsolidationAttemptDetails, ...],
)
```

Each `CirculationPathDetails` includes all previous path/cost fields plus:

```python
required_transit_room_types: tuple[RoomType, ...]
required_transit_point_keys: tuple[str, ...]
```

Each `HallwayTrafficDetails` now also contains:

```python
removal_reason: HallwayRemovalReason | None
```

Each removed point is reported as:

```python
RemovedHallwayPointDetails(
    point_key: str,
    room_id: str,
    hint_index: int,
    x: float,
    y: float,
    reason: HallwayRemovalReason,
)
```

Each consolidation attempt is reported as:

```python
HallwayConsolidationAttemptDetails(
    point_key: str,
    nearby_point_keys: tuple[str, ...],
    decision: HallwayConsolidationDecision,
    max_route_cost_increase_ratio: float | None,
)
```

### Errors / failure conditions

Bad input/configuration can raise `TypeError`, `ValueError`, or
`CandidateCirculationInputError`. Off-grid or grid-consistency problems raise
`GridAlignmentError`. A configured route that cannot satisfy reachability, including
a required-transit rule, raises `CirculationPathNotFoundError`.

A rejected consolidation attempt is not a feature failure; the hallway is simply kept
and the reason is available in DEBUG details.

### Usage example

```python
from fpg_core.candidate_circulation import (
    CandidateCirculationConfig,
    CandidateCirculationInput,
    HallwayConsolidationConfig,
    RoutingCostProfile,
    refine_candidate_circulation,
)

config = CandidateCirculationConfig(
    costs=RoutingCostProfile(2.0, 0.75, 0.35, 1.5, 8.0),
    route_rules=(example_route_rule,),
    always_traversable_room_types=(RoomType.HALLWAY,),
    hallway_consolidation=HallwayConsolidationConfig(
        enabled=True,
        minimum_separation_grid_steps=2.0,
        max_route_cost_increase_ratio=0.15,
    ),
)
execution = refine_candidate_circulation(
    CandidateCirculationInput(example_candidate, config)
)
cleaned = execution.result.candidate
```

### Important behavioral notes

Routing moves orthogonally between adjacent grid indexes. Required transit is checked
against intermediate **candidate points**, not arbitrary empty grid cells. The input
candidate is not mutated. If hallway hints are removed, the consumer must keep later
room specifications/solver inputs consistent with the returned candidate identities.

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

`CandidateScoreManager(registry, config, context_factory=None)` is the reusable
object form; its operation is `score(scoring_input, *,
mode=ExecutionMode.PRODUCTION) -> ScoringResult`.
`ScoringContextFactory.build(scoring_input) -> ScoringContext` constructs
the normalized evaluator context. Registry method signatures are in the extension
section.

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
    CandidateScoringInput(example_specification, example_candidate),
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

Builds and solves a CP-SAT floor-plan model from request-specific generation data and
an explicit reusable solver configuration. Every room supplied by the generation
specification remains mandatory; the solver may move/resize a hallway but does not
remove a hallway room that upstream stages supplied.

### Public API

```python
generate_floor_plan(
    request: FloorPlanSolveRequest,
    *,
    registry: ConstraintRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanSolveExecution

FloorPlanSolver(registry: ConstraintRegistry | None = None)
FloorPlanSolver.solve(
    request: FloorPlanSolveRequest,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanSolveExecution
```

Preferred imports are from `fpg_core.floor_plan_solver`. `GenerationProfile` remains
a compatibility alias of `FloorPlanSolverConfig`.

### Inputs

```python
FloorPlanSolveRequest(
    specification: FloorPlanGenerationSpec,
    config: FloorPlanSolverConfig,
    candidate_hints: tuple[RoomPlacementHint, ...] = (),
    existing_floor_plan: FloorPlan | None = None,
)

RoomPlacementHint(
    room_id: RoomId,
    x: float,
    y: float,
    width: float | None = None,
    length: float | None = None,
)
```

`specification` defines the floor and every room that must be placed. Candidate hints
are optional seed geometry. `existing_floor_plan` is optional unless the selected seed
policy requires it. Unknown/duplicate hint room IDs are invalid; hint sizes, when
provided, must be positive. Prepared hints are clamped to feasible floor/room bounds.
Existing-plan rooms absent from the specification are ignored as seed inputs.

### Structural rules that are always active

These are solver-model invariants rather than selectable registry constraints:

- every `FloorPlanGenerationSpec.rooms` entry is present in the result;
- every room stays inside the floor boundary;
- every room satisfies its prepared dimension and area bounds;
- rooms do not overlap.

Therefore hallway-count/removal decisions belong upstream. The solver cannot label a
supplied hallway “unnecessary” and delete it.

### Configuration

```python
HardConstraintUse(
    key: str,
    settings: Mapping[str, Any] = {},
)

SoftConstraintUse(
    key: str,
    weight: int,
    settings: Mapping[str, Any] = {},
)

SolverConfig(
    max_time_seconds: float = 30.0,
    num_search_workers: int = 0,
    random_seed: int | None = None,
    log_search_progress: bool = False,
    relative_gap_limit: float | None = None,
    cp_model_presolve: bool = True,
)

PreparationConfig(
    coordinate_scale: int = 10,
)

SeedPolicy(
    source: SeedSource = SeedSource.NONE,
    require_source: bool = False,
    apply_hints: bool = True,
    position_tolerance: float | None = None,
    size_tolerance: float | None = None,
)

FloorPlanSolverConfig(
    name: str,
    hard_constraints: tuple[HardConstraintUse, ...],
    soft_constraints: tuple[SoftConstraintUse, ...],
    solver: SolverConfig = SolverConfig(),
    preparation: PreparationConfig = PreparationConfig(),
    seed: SeedPolicy = SeedPolicy(),
)
```

`SeedSource` values are `NONE='none'`, `CANDIDATE_HINTS='candidate_hints'`, and
`EXISTING_FLOOR_PLAN='existing_floor_plan'`. Seed tolerances use project units;
`None` leaves that dimension unbounded and uses hints only, `0` fixes the seeded
value, and positive values bound movement or size.

`FloorPlanSolverConfig` requires a non-empty name and unique hard/soft constraint keys.
`SoftConstraintUse.weight` must be positive. `SolverConfig.max_time_seconds` must be
positive; workers, random seed, and relative gap cannot be negative.
`PreparationConfig.coordinate_scale` must be at least `1`.

Immutable helper methods return modified configs:

```python
config.without_constraints(*keys)
config.with_hard_constraints(*uses)
config.with_soft_constraints(*uses)
```

### Built-in hard constraints

The shipped default profiles enable:

| Key | Exact built-in settings / behavior |
|---|---|
| `aspect_ratio` | min `0.60`, max `1.80`; hallways excluded from this rule; garage override `0.45..0.70`; veranda override `1.20..3.50` |
| `room_relations` | enforces `HARD` specification relations; `minimum_overlap=10` |
| `attached_bathroom_pairing` | minimum shared wall `10`; attached-bathroom type paired with bedroom type |
| `minimum_coverage` | `ratio=0.6` |
| `hallway_connectivity` | `minimum_overlap=10`; hallway type must touch an anchor type and a non-hallway/non-anchor destination; default anchor is living room |
| `hallway_dimensions` | hallway corridor width is constrained to `8..10`; the other dimension may extend as needed |
| `front_anchor` | veranda, living room, bedroom, garage |
| `back_exposure` | hallway and kitchen; minimum exposure `10.0` |
| `garage_placement` | garage type |
| `boundary_placement` | veranda on `front` with offset `0.0` |

`room_size_hierarchy` is registered for custom configurations but is not enabled by
the built-in profiles.

### Built-in soft constraints

The default registry provides:

- `room_relations`
- `floor_cluster_position`
- `dead_space`
- `hallway_efficiency`
- `bathroom_depth`
- `kitchen_back_exposure`
- `seed_stability`

The solver minimizes the weighted sum of enabled soft-constraint penalties. Hard
constraints always determine feasibility.

#### Hallway efficiency

`hallway_efficiency` treats all configured hallway rooms as one circulation-geometry
cost. It does not decide whether an individual hallway is semantically necessary.

The objective components are:

```text
hallway efficiency cost =
    total hallway area * area_penalty_multiplier
  + total excess hallway length * excess_length_penalty_multiplier
```

The complete penalty is then multiplied by the ordinary `SoftConstraintUse.weight`.

For each hallway:

```text
longest_side = max(width, length)
excess_length = max(0, longest_side - preferred_max_length)
```

`preferred_max_length` is a soft threshold, not a hard maximum. A longer hallway is
still legal when hard constraints require it; it simply contributes more objective
cost. Penalizing total hallway area also encourages the solver to shrink hallway
geometry toward the smallest dimensions compatible with hard constraints and the
other objective terms. It never removes the hallway room.

Supported settings:

| Setting | Type | Default | Validation / meaning |
|---|---|---:|---|
| `hallway_room_types` | iterable of `RoomType` | `(RoomType.HALLWAY,)` | room types included in the hallway-efficiency objective |
| `area_penalty_multiplier` | `int` | `1` | must be `>= 0`; `0` disables the area component |
| `preferred_max_length` | `float | None` | `40.0` | positive finite project-unit length; `None` disables excess-length threshold calculation |
| `excess_length_penalty_multiplier` | `int` | `5` | must be `>= 0`; `0` disables the excess-length component |
| `SoftConstraintUse.weight` | `int` | profile-defined | must be `> 0`; weights the whole hallway-efficiency penalty |

With the project convention `10` units = `1 m`, the built-in
`preferred_max_length=40.0` corresponds to `4 m`.

To disable hallway efficiency completely:

```python
config = INITIAL_GENERATION_PROFILE.without_constraints("hallway_efficiency")
```

### Built-in profile construction

```python
DefaultProfileSettings(
    coordinate_scale: int = 1,
    minimum_coverage_ratio: float = 0.6,
    minimum_adjacency_overlap: float = 10,
    attached_bathroom_minimum_shared_wall: float = 10.0,
    initial_max_time_seconds: float = 5.0,
    refinement_max_time_seconds: float = 2.0,
    refinement_position_tolerance: float = 10,
    refinement_size_tolerance: float = 10,
    hallway_efficiency_weight: int = 1,
    hallway_area_penalty_multiplier: int = 1,
    hallway_preferred_max_length: float | None = 40.0,
    hallway_excess_length_penalty_multiplier: int = 5,
)

build_default_profiles(
    settings: DefaultProfileSettings | None = None,
) -> ProfileCatalog
```

The returned `ProfileCatalog` contains `initial`, `refinement_a`, and `refinement_b`.
The public constants `DEFAULT_PROFILES`, `INITIAL_GENERATION_PROFILE`,
`REFINEMENT_A_PROFILE`, and `REFINEMENT_B_PROFILE` are created from the default
settings above.

Exact built-in soft uses:

| Profile | Exact soft uses (`key: weight`; important settings) | Runtime / seed |
|---|---|---|
| `initial_generation` | `room_relations:40` (overlap 10), `floor_cluster_position:1` (horizontal 1/front 2), `dead_space:3`, `hallway_efficiency:1` (area 1, preferred max length 40, excess multiplier 5), `bathroom_depth:2`, `kitchen_back_exposure:10` (exposure 10) | 5 s; candidate hints optional; coordinate scale 1 |
| `refinement_a` | `room_relations:50`, `seed_stability:20` (position 2/size 1), `floor_cluster_position:1` (horizontal 1/front 2), `dead_space:4`, `hallway_efficiency:1` (area 1, preferred max length 40, excess multiplier 5), `bathroom_depth:3`, `kitchen_back_exposure:10` | 2 s; existing plan required; position/size tolerance 10; coordinate scale 1 |
| `refinement_b` | `room_relations:60`, `seed_stability:35` (position 2/size 2), `dead_space:6`, `hallway_efficiency:1` (area 1, preferred max length 40, excess multiplier 5), `bathroom_depth:4`, `kitchen_back_exposure:10` | 2 s; existing plan required; position/size tolerance 5; coordinate scale 1 |

### Recommended values

**Built-in profile values** are starter settings, not universal architectural
standards. For hallway efficiency, begin with the shipped weight/multipliers and tune
them against actual generated plans rather than adding a hallway-count penalty. For
repeatable solver tests, set a fixed `random_seed` and use
`num_search_workers=1`.

### Outputs

```python
FloorPlanSolveResult(
    status: SolverStatus,
    floor_plan: FloorPlan | None,
    profile_name: str,
    message: str,
)
```

`SolverStatus` values are `OPTIMAL='optimal'`, `FEASIBLE='feasible'`,
`INFEASIBLE='infeasible'`, `MODEL_INVALID='model_invalid'`, and
`UNKNOWN='unknown'`. `.solved` is true only when the status has a solution and
`floor_plan` is not `None`.

`FloorPlanSolveExecution` is
`FeatureExecution[FloorPlanSolveResult, SolverDiagnostics]`. In PRODUCTION,
`details=None`. DEBUG diagnostics are:

```python
SolverDiagnostics(
    raw_status: str,
    wall_time_seconds: float,
    objective_value: float | None,
    best_objective_bound: float | None,
    conflicts: int,
    branches: int,
    applied_hard_constraints: tuple[str, ...],
    applied_soft_constraints: tuple[str, ...],
    penalty_terms: tuple[str, ...],
)
```

With hallway efficiency enabled, `penalty_terms` can contain
`'hallway_efficiency:total_area'` and `'hallway_efficiency:excess_length'`.
`FloorPlanSolveResult.profile_name` is retained for serialized/public compatibility
even though the request field is named `config`.

### Errors / failure conditions

Invalid specifications, configs, constraint IDs, or required seed data raise the
`FloorPlanSolverError` family before or during model construction. Specific subclasses
remain available from `fpg_core.floor_plan_solver.exceptions`.
`INFEASIBLE`, `MODEL_INVALID`, and `UNKNOWN` are normal result statuses, not
exceptions merely because solving did not produce a plan.

### Usage example

```python
from fpg_core.domain import ExecutionMode, RoomId
from fpg_core.floor_plan_solver import (
    INITIAL_GENERATION_PROFILE,
    FloorPlanSolveRequest,
    RoomPlacementHint,
    generate_floor_plan,
)

execution = generate_floor_plan(
    FloorPlanSolveRequest(
        specification=example_specification,
        config=INITIAL_GENERATION_PROFILE,
        candidate_hints=(RoomPlacementHint(RoomId("living"), 20, 10),),
    ),
    mode=ExecutionMode.DEBUG,
)
if not execution.result.solved:
    raise RuntimeError(execution.result.message)
floor_plan = execution.result.floor_plan
```

### Important behavioral notes

Upstream search/circulation decides which hallway rooms reach the solver. The solver
keeps every supplied hallway and can make its geometry smaller through the soft
hallway-efficiency objective while still satisfying hard width/connectivity rules.
Connected hallways may later be merged by `floor_plan_post_processing`; that is a
separate responsibility from solver-side compaction.

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

The feature root exports the request/config/result/execution/detail contracts,
processor extension contracts and registry, statuses, `NumericPolicy`,
`INITIAL_GENERATION_PROFILE`, and `create_default_registry()`.
It also exports every built-in processor configuration class.

### Inputs

`PostProcessingRequest(floor_plan, config, specification=None)`. The plan boundary
and room polygons must be canonical, rooms must have unique IDs and names, standard
rooms may not overlap or leave the floor, parent/redirect/opening references must be
valid, and identity redirects must be acyclic. The specification is optional context
for processors.

### Configuration

- `FloorPlanPostProcessingConfig(name, processors, numeric=NumericPolicy(),
  reject_existing_openings=True)`. `PostProcessingProfile` is a compatibility alias.
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
- `WallExtensionConfig(rules, transformation_version='wall_extension:v1')` uses the
  five-rule default tuple printed in the public API inventory when `rules` is omitted.
  Each rule is
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
    floor_plan=example_floor_plan,
    config=INITIAL_GENERATION_PROFILE,
    specification=example_specification,
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

Analyzes a finalized floor plan and uses CP-SAT to place interior doors, exterior
doors, and windows without mutating the source plan. Interior room-type compatibility,
required door-network access, and door placement priorities are consumer-configurable.

### Public API

```python
generate_openings(
    request: OpeningGenerationRequest,
    *,
    registry: OpeningFeatureRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> OpeningGenerationExecution
```

Preferred imports are from `fpg_core.floor_plan_openings` or its public `api` module.
`OpeningGenerationProfile` and `DEFAULT_OPENING_PROFILE` remain compatibility names
for `FloorPlanOpeningsConfig` and `DEFAULT_OPENING_CONFIG`.

### Inputs

```python
OpeningGenerationRequest(
    floor_plan: FloorPlan,
    config: FloorPlanOpeningsConfig,
)
```

The source plan must have valid finite rectilinear floor/room geometry, positive room
area, unique room IDs, standard rooms inside the floor without area overlap, and **no
existing openings**. The source plan is never mutated.

### Configuration

```python
GeometryConfig(
    coordinate_scale: int = 10,
    tolerance: float = 1e-6,
    corner_clearance: float = 0.0,
    window_spacing: float = 5.0,
)

DimensionConfig(
    door_width: float = 8.0,
    window_width: float = 16.0,
    minimum_shared_wall: float = 10.0,
)

SolverConfig(
    max_time_seconds: float = 10.0,
    num_search_workers: int = 1,
    random_seed: int = 0,
    cp_model_presolve: bool = True,
    log_search_progress: bool = False,
)
```

`coordinate_scale` must be at least `1`; geometry tolerance and dimensions must be
positive; corner/window clearances cannot be negative. Solver time and workers must
be positive and the random seed cannot be negative.

#### FeaturePolicy

```python
FeaturePolicy(
    allowed_room_pairs: tuple[tuple[RoomType, RoomType], ...] = DEFAULT_PAIRS,
    room_door_caps: tuple[tuple[RoomType, int], ...] = DEFAULT_CAPS,
    secondary_room_priority: tuple[RoomType, ...] = (
        RoomType.KITCHEN,
        RoomType.HALLWAY,
    ),
    window_room_types: tuple[RoomType, ...] = (
        RoomType.BEDROOM,
        RoomType.LIVING_ROOM,
        RoomType.KITCHEN,
        RoomType.DINING_ROOM,
    ),
    main_side_priority: tuple[str, ...] = ("south", "east", "north", "west"),
    secondary_side_priority: tuple[str, ...] = ("north", "west", "east", "south"),
    window_side_priority: tuple[str, ...] = ("east", "north", "south", "west"),
    required_access_room_types: tuple[RoomType, ...] = DEFAULT_REQUIRED_ACCESS,
    door_placement_priority: tuple[tuple[RoomType, int], ...] = DEFAULT_DOOR_PRIORITY,
)
```

Exact default `allowed_room_pairs`:

```python
(
    (RoomType.BEDROOM, RoomType.LIVING_ROOM),
    (RoomType.KITCHEN, RoomType.LIVING_ROOM),
    (RoomType.BATHROOM, RoomType.LIVING_ROOM),
    (RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM),
    (RoomType.VERANDA, RoomType.LIVING_ROOM),
    (RoomType.GARAGE, RoomType.LIVING_ROOM),
    (RoomType.DINING_ROOM, RoomType.LIVING_ROOM),
    (RoomType.BEDROOM, RoomType.HALLWAY),
    (RoomType.BATHROOM, RoomType.HALLWAY),
    (RoomType.LIVING_ROOM, RoomType.HALLWAY),
    (RoomType.KITCHEN, RoomType.HALLWAY),
    (RoomType.DINING_ROOM, RoomType.HALLWAY),
    (RoomType.VERANDA, RoomType.HALLWAY),
    (RoomType.GARAGE, RoomType.HALLWAY),
    (RoomType.HALLWAY, RoomType.HALLWAY),
)
```

This tuple is authoritative. Pair order does not matter, duplicate logical pairs are
rejected, and the implementation no longer silently adds hallway connections or a
special attached-bathroom pairing rule. If a consumer wants
`ATTACHED_BATHROOM <-> HALLWAY`, it must explicitly add that pair.

Exact default door caps:

```python
(
    (RoomType.BEDROOM, 2),
    (RoomType.BATHROOM, 1),
    (RoomType.LIVING_ROOM, 10),
    (RoomType.HALLWAY, 10),
    (RoomType.KITCHEN, 1),
    (RoomType.ATTACHED_BATHROOM, 1),
    (RoomType.VERANDA, 1),
    (RoomType.GARAGE, 1),
    (RoomType.DINING_ROOM, 2),
)
```

Caps must be positive and each room type may appear only once. The same cap mechanism
is applied uniformly; there is no Bedroom/Attached-Bathroom-specific cap behavior.

Exact default required-access room types:

```python
(
    RoomType.BEDROOM,
    RoomType.BATHROOM,
    RoomType.ATTACHED_BATHROOM,
    RoomType.LIVING_ROOM,
    RoomType.KITCHEN,
    RoomType.DINING_ROOM,
    RoomType.HALLWAY,
    RoomType.VERANDA,
    RoomType.GARAGE,
)
```

The tuple must contain unique room types.

Exact default door-placement priorities:

```python
(
    (RoomType.BEDROOM, 100),
    (RoomType.BATHROOM, 100),
    (RoomType.ATTACHED_BATHROOM, 100),
    (RoomType.KITCHEN, 80),
    (RoomType.DINING_ROOM, 60),
    (RoomType.GARAGE, 60),
    (RoomType.VERANDA, 40),
    (RoomType.LIVING_ROOM, 20),
    (RoomType.HALLWAY, 10),
)
```

Priorities must be non-negative and each room type may appear only once. Higher values
mean that room's nearest usable corner/wall end dominates the choice of which end of a
shared wall the door should favor. If the higher-priority room is tied, the other room
acts as the tie-breaker. The selected door is then optimized as close as possible to
that preferred end while still satisfying corner clearance, width, wall bounds,
non-overlap, window spacing, and other hard constraints. This applies to **doors**;
windows retain center-oriented placement behavior.

Every side-priority tuple must contain exactly `south`, `east`, `north`, and `west`
once each.

#### FloorPlanOpeningsConfig

```python
FloorPlanOpeningsConfig(
    name: str,
    enabled_features: tuple[str, ...] = (
        "interior_doors",
        "exterior_doors",
        "windows",
    ),
    enabled_constraints: tuple[str, ...] = (
        "shared_placement",
        "room_door_limits",
        "required_room_access",
    ),
    geometry: GeometryConfig = GeometryConfig(),
    dimensions: DimensionConfig = DimensionConfig(),
    policy: FeaturePolicy = FeaturePolicy(),
    objective: ObjectiveConfig = ObjectiveConfig(),
    solver: SolverConfig = SolverConfig(),
)
```

The config name must be non-empty; feature and constraint IDs must be unique.
`shared_placement` **and** `required_room_access` are structural constraints and cannot
be disabled. `room_door_limits` remains selectable.

`ObjectiveConfig.tier_order` defaults to:

```python
(
    "window",
    "secondary_entrance",
    "other_interior",
    "preferred_hallway",
    "bathroom_hallway",
    "attached_bathroom",
    "main_entrance",
)
```

Tier IDs must be unique.

### Required room access behavior

For a non-empty floor plan, `required_room_access` enforces exactly one selected main
entrance. Every room whose type is in `required_access_room_types` must be reachable
from that entrance through selected doors. A local isolated pair of rooms does not
satisfy this rule merely because those two rooms have a door between them.

This is a **hard feasibility condition**, not an objective preference. If the
combination of `allowed_room_pairs`, door caps, room geometry, available walls, or
other hard constraints cannot produce a connected required-access network, the solve
returns `INFEASIBLE`.

Windows and other non-required optional opening demands may still remain unselected.

### Recommended values

Start with `DEFAULT_OPENING_CONFIG` unless the project's access policy requires
different room pairs/caps. Keep the built-in `required_room_access` constraint enabled.
For reproducible tests, the shipped opening solver already uses one worker and seed
`0`.

### Outputs

```python
OpeningGenerationResult(
    status: OpeningGenerationStatus,
    floor_plan: FloorPlan | None,
    profile_name: str,
    message: str,
)
```

Status values are:

- `OPTIMAL='optimal'`
- `FEASIBLE='feasible'`
- `INFEASIBLE='infeasible'`
- `MODEL_INVALID='model_invalid'`
- `UNKNOWN='unknown'`
- `INVALID_INPUT='invalid_input'`

`.solved` requires a solution status and a non-`None` floor plan.

`OpeningGenerationExecution` is
`FeatureExecution[OpeningGenerationResult, OpeningDiagnostics]`. `details=None` in
PRODUCTION. DEBUG diagnostics include raw solver status/timing/objective statistics,
wall count, demand/candidate/selected counts, applied constraint IDs, objective terms,
and structured `OpeningIssue` values.

DEBUG issues can identify conditions such as no main-entrance candidate, a
required-access room with no door candidate, an optional demand with no candidate, an
unselected optional demand, or an undersized exterior door.

The solved result contains a **copy** of the source floor plan with generated
`FloorPlanOpening` objects.

### Errors / failure conditions

Invalid source floor geometry is returned as `INVALID_INPUT`, with no plan and, in
DEBUG, an `invalid_input` issue. Infeasibility/model/unknown outcomes are returned
statuses. Invalid configurations, duplicate/unknown feature registrations, unknown
constraint IDs, and other generation contract failures raise the
`OpeningGenerationError` family. `OpeningConfigurationError` is exported directly.

### Usage example

```python
from fpg_core.floor_plan_openings import (
    DEFAULT_OPENING_CONFIG,
    OpeningGenerationRequest,
    generate_openings,
)

execution = generate_openings(
    OpeningGenerationRequest(
        floor_plan=example_floor_plan,
        config=DEFAULT_OPENING_CONFIG,
    )
)
if not execution.result.solved:
    raise RuntimeError(execution.result.message)
plan_with_openings = execution.result.floor_plan
```

### Important behavioral notes

The source plan is never mutated. `allowed_room_pairs` fully owns interior connection
compatibility. Required door access is now mandatory in valid configurations. Door
placement is corner/wall-end oriented using room-type priority; windows remain
center-oriented. Run opening generation after geometry-changing post-processing if the
openings must remain aligned with the final room boundaries.

## Floor Plan Scoring

### Purpose

Scores completed room geometry against its generation specification and returns a
0..100 quality score plus structured findings. Critical geometry checks remain hard
gates. The default functional scoring now uses the generic `room_size_consistency`
evaluator instead of the former default `living_room_balance` and `bedroom_quality`
evaluators.

### Public API

```python
score_floor_plan(
    scoring_input: FloorPlanScoringInput,
    *,
    registry: EvaluatorRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanScoringExecution

create_default_config() -> FloorPlanScoringConfig
create_default_registry() -> EvaluatorRegistry

# Compatibility names:
create_default_profile() -> ScoringProfile
```

`ScoringProfile` is an alias of `FloorPlanScoringConfig`.
`DEFAULT_SCORING_PROFILE` is the same object as
`DEFAULT_FLOOR_PLAN_SCORING_CONFIG`.

### Inputs

```python
FloorPlanScoringInput(
    floor_plan: FloorPlan,
    specification: FloorPlanGenerationSpec,
    config: FloorPlanScoringConfig,
)
```

The specification is required because evaluators use room IDs, relations, and room
size ranges. The room-size-consistency feasibility adjustment reads `RoomSizeSpec.min_area`
and `max_area` directly from this specification; consumers do not supply a second copy
of those ranges.

### Configuration

```python
ScoringGroupRule(
    key: GroupKey,
    enabled: bool = True,
    order: int = 0,
    weight: float = 1.0,
)

EvaluatorRule(
    key: EvaluatorKey,
    group_key: GroupKey,
    settings: object,
    enabled: bool = True,
    order: int = 0,
    weight: float = 1.0,
    minimum_score: float | None = None,
)

FloorPlanScoringConfig(
    groups: tuple[ScoringGroupRule, ...],
    evaluators: tuple[EvaluatorRule, ...],
)
```

An enabled critical evaluator requires a `minimum_score` in `0..100`; non-critical
evaluators must not define one. Enabled group/evaluator weights must be finite and
positive. Keys must be unique, each enabled group must have an enabled evaluator, and
one enabled `critical` group acts as the gate before later groups.

Built-in group keys are `critical`, `functional`, `aesthetic`, and `extra`.

### Room-size consistency

The public evaluator key is:

```python
ROOM_SIZE_CONSISTENCY_KEY = EvaluatorKey("room_size_consistency")
```

Public aggregation values:

```python
RoomAreaAggregation.MIN      # "min"
RoomAreaAggregation.AVERAGE  # "average"
RoomAreaAggregation.MAX      # "max"
RoomAreaAggregation.TOTAL    # "total"
```

Cross-type relation rule:

```python
RoomSizeRelationRule(
    reference_type: RoomType,
    compared_type: RoomType,
    min_ratio: float | None = None,
    max_ratio: float | None = None,
    reference_aggregation: RoomAreaAggregation = RoomAreaAggregation.MAX,
    compared_aggregation: RoomAreaAggregation = RoomAreaAggregation.MAX,
    weight: float = 1.0,
    full_penalty_ratio_delta: float | None = None,
)
```

The evaluated ratio is:

```text
compared area / reference area
```

`reference_type` and `compared_type` must differ. At least one of `min_ratio` or
`max_ratio` is required. Configured ratios and rule weight must be positive; when both
bounds are present, `min_ratio <= max_ratio`. A rule-specific
`full_penalty_ratio_delta`, when supplied, must be positive.

Same-type consistency rule:

```python
RoomTypeConsistencyRule(
    room_type: RoomType,
    maximum_spread_ratio: float,
    weight: float = 1.0,
    full_penalty_ratio_delta: float | None = None,
)
```

`maximum_spread_ratio` is:

```text
largest room area / smallest room area - 1
```

It must be non-negative. Weight and any rule-specific full-penalty delta must be
positive.

Evaluator settings:

```python
RoomSizeConsistencySettings(
    relation_rules: tuple[RoomSizeRelationRule, ...] = (),
    consistency_rules: tuple[RoomTypeConsistencyRule, ...] = (),
    default_full_penalty_ratio_delta: float = 0.5,
)
```

At least one relation or consistency rule is required. Relation `(reference_type,
compared_type)` pairs must be unique; same-type consistency rules may define each room
type only once. `default_full_penalty_ratio_delta` must be positive.

#### Feasibility adjustment

The evaluator does not penalize a configured ratio that the generation specification
makes impossible. It derives a feasible ratio range from the matching room specs'
`min_area` and `max_area` values and relaxes an impossible configured bound to the
nearest feasible threshold for that project.

Example:

```text
Living:  200..250
Kitchen: 220..260
Configured kitchen/living max ratio: 0.80
Best feasible ratio: 220 / 250 = 0.88
Effective max ratio: 0.88
```

The configured preference remains unchanged in the config; only scoring uses the
effective threshold. The same principle applies to a same-type spread rule when the
room-size ranges themselves force a minimum spread.

#### Penalty behavior

Violations are gradual. Once the violation exceeds the effective boundary,
`full_penalty_ratio_delta` controls how much further ratio deviation produces a zero
rule score. If the individual rule leaves it `None`,
`default_full_penalty_ratio_delta` is used. Applicable rules are combined by their
individual `weight` values.

#### Exact default room-size rules

The default config uses `RoomSizeConsistencySettings` with:

```python
relation_rules=(
    RoomSizeRelationRule(
        reference_type=RoomType.LIVING_ROOM,
        compared_type=RoomType.KITCHEN,
        max_ratio=0.80,
        reference_aggregation=RoomAreaAggregation.MAX,
        compared_aggregation=RoomAreaAggregation.MAX,
    ),
    RoomSizeRelationRule(
        reference_type=RoomType.KITCHEN,
        compared_type=RoomType.DINING_ROOM,
        max_ratio=1.00,
        reference_aggregation=RoomAreaAggregation.MAX,
        compared_aggregation=RoomAreaAggregation.MAX,
    ),
    RoomSizeRelationRule(
        reference_type=RoomType.LIVING_ROOM,
        compared_type=RoomType.BEDROOM,
        max_ratio=0.90,
        reference_aggregation=RoomAreaAggregation.MAX,
        compared_aggregation=RoomAreaAggregation.MAX,
    ),
)
consistency_rules=(
    RoomTypeConsistencyRule(
        room_type=RoomType.BEDROOM,
        maximum_spread_ratio=0.25,
    ),
)
default_full_penalty_ratio_delta=0.50
```

These are **scoring preferences**, not solver constraints.

### Exact default scoring config

`DEFAULT_FLOOR_PLAN_SCORING_CONFIG` / `create_default_config()` contains two groups:

```text
critical   order=10, weight=1.0
functional order=20, weight=1.0
```

Critical evaluators, all requiring score `100`:

| Evaluator | Order | Exact settings |
|---|---:|---|
| `geometry_integrity` | 10 | tolerance `1e-6` |
| `required_adjacency` | 20 | minimum shared boundary `10.0`, tolerance `1e-6` |
| `enclosed_voids` | 30 | area tolerance `1e-6` |
| `inward_recess` | 40 | maximum length `20.0`, tolerance `1e-6` |

Functional evaluators:

| Evaluator | Order | Weight | Exact settings |
|---|---:|---:|---|
| `room_size_consistency` | 10 | `2.0` | exact rules listed above |
| `kitchen_dining` | 20 | `1.0` | minimum shared boundary `10.0`, maximum distance `2000.0`, tolerance `1e-6` |

`LivingRoomBalanceEvaluator` and `BedroomQualityEvaluator` remain exported and are
still registered by `create_default_registry()` for compatibility with custom
configs. They are **not enabled by the default scoring config**.

### Recommended values

Use `create_default_config()` as the canonical baseline. The four critical checks are
strict 100-point gates. The default functional allocation gives
`room_size_consistency` twice the configured weight of `kitchen_dining` before
normalization. Treat the built-in room-size ratios as package preferences that can be
replaced by project-specific values.

### Outputs

```python
FloorPlanScoringResult(
    total_score: float,
    passed_critical: bool,
    critical_failure: ScoreFinding | None,
)

FloorPlanScoringDetails(
    group_results: tuple[ScoringGroupResult, ...],
    evaluator_results: tuple[EvaluatorExecutionResult, ...],
    findings: tuple[ScoreFinding, ...] = (),
)
```

`FloorPlanScoringExecution` is
`FeatureExecution[FloorPlanScoringResult, FloorPlanScoringDetails]`.
`details=None` in PRODUCTION. DEBUG details include group results, evaluator raw and
normalized contributions, thresholds, findings, metrics, and optional visualization
payloads.

For `room_size_consistency`, DEBUG metrics/findings expose configured, feasible,
effective, actual, and violation ratios/spreads where applicable.

### Errors / failure conditions

`FloorPlanScoringError` subclasses cover invalid input, inconsistent scoring config,
registry errors, evaluator contract violations, and unexpected evaluator execution.
A critical score below threshold is a normal scoring result: `passed_critical=False`,
later groups are skipped, and no exception is required solely for failing the gate.
If no critical evaluator is applicable, the manager raises `EvaluatorExecutionError`.

### Usage example

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_scoring import (
    FloorPlanScoringInput,
    create_default_config,
    score_floor_plan,
)

execution = score_floor_plan(
    FloorPlanScoringInput(
        floor_plan=example_floor_plan,
        specification=example_specification,
        config=create_default_config(),
    ),
    mode=ExecutionMode.DEBUG,
)
score = execution.result.total_score
```

### Important behavioral notes

Scoring does not mutate the plan or generation specification. Openings do not affect
the current built-in scoring results. The old `FloorPlanScoringInput(..., profile=...)`
constructor form is no longer valid; use `config=`. Compatibility profile helper names
remain available only as aliases for the configuration object/helper.

## Shared Domain Contract Reference

All contracts in this section are public from `fpg_core.domain`. `RoomId`,
`OpeningId`, `EvaluatorKey`, and `GroupKey`-style identifiers are string-based typed
aliases; construct them from non-empty strings where the owning feature requires it.

### Execution contracts

```python
ExecutionMode.PRODUCTION  # "production"
ExecutionMode.DEBUG       # "debug"

ExecutionMetadata(mode: ExecutionMode, duration_seconds: float)
FeatureExecution[TResult, TDetails](
    result: TResult,
    details: TDetails | None,
    metadata: ExecutionMetadata,
)
```

Duration is finite, non-negative, and measured in seconds. Except for Candidate
Scoring's documented direct `ScoringResult`, feature operations in this reference
return this envelope. DEBUG changes only `details` collection; it does not change the
normal result type.

### Geometry contracts

```python
Point(x: float, y: float)
Segment(start: Point, end: Point)
Polygon(points: tuple[Point, ...])
```

Coordinates and lengths use consumer project units; areas use square project units.
`Polygon` stores an ordered boundary without an implied coordinate conversion.
Feature-specific validation determines whether closing duplicates, orientation,
convexity, or rectilinearity are accepted.

### Land contracts

```python
BuildableSpaceRequestData(
    land_boundary: Polygon,
    roads: tuple[RoadAttachment, ...],
)
RoadAttachment(
    boundary_edge_index: int,
    role: RoadRole,
    road_type: RoadType,
)
ValidationLimits(
    minimum_vertex_count: int,
    maximum_vertex_count: int,
    maximum_absolute_coordinate: int,
)
SetbackProfile(
    name: str,
    status: str,
    description: str,
    calculation_mode: SetbackCalculationMode,
    base_setbacks: Mapping[LandSide, int],
    road_adjustments: Mapping[RoadType, Mapping[LandSide, int]],
)
```

`LandSide` values are `front`, `back`, `left`, and `right`. Current setback
calculation uses `SetbackCalculationMode.BASE_PLUS_ROAD_ADJUSTMENT`. `NormalizedLand`
contains `boundary`, ordered `LandEdge(index, source_edge_index, segment)` values,
and `main_entry_road`. `BuildableLand(boundary, area, edge_setbacks)` stores
`EdgeSetback(edge_index, side, base_setback, road_adjustment, final_setback,
road_type=None)`. `UsableLand(boundary, width, length, area,
floor_width_alignment, entry_road_edge_index)` uses `FloorWidthAlignment` values
`parallel_to_entry_road` and `perpendicular_to_entry_road`.

`UsableLandConstraints(minimum_width, minimum_length, search_resolution,
maximum_sweep_lines)` remains a shared compatibility/reference-data contract;
standalone Usable Land execution uses `UsableLandConfig`.

### Candidate and grid contracts

```python
ResolvedCandidateGrid(
    x_positions: tuple[int | float, ...],
    y_positions: tuple[int | float, ...],
)
CandidatePoint(
    room_id: RoomId,
    x: float,
    y: float,
    room_type: RoomType | None = None,
    hint_index: int = 1,
)
CandidateMap(
    grid: ResolvedCandidateGrid,
    points: tuple[CandidatePoint, ...],
)
HallwayRoomCountRange(maximum: int, minimum: int = 1)
```

Grid positions must describe strictly increasing, uniformly spaced axes. Derived
properties provide spacing, dimensions, node counts, coordinate/index conversion,
and interior-node iteration. Candidate points must use unique `(room_id,
hint_index)` identities; individual features impose grid-alignment and capacity
rules. `CandidateSearchSpace(origin_x, origin_y, width, length, grid_spacing)` is a
legacy/derived grid description; use `ResolvedCandidateGrid` for exact execution.

Shared circulation contracts are
`CirculationRouteRule(id, name, source_room_type, destination_room_type,
destination_selection, traffic_class, allowed_transit_room_types,
importance_weight, required_transit_room_types=())`,
`GridRoutingCostProfile(empty_node_cost, traversable_hint_node_cost, turn_cost,
perimeter_bias_max_cost)`, and `HallwayClassification(room_id, hint_index,
traffic_class)`. Required transit is an any-of intermediate-room-type requirement and
the configured required types are traversable for that route. Destination selection
values are `all_matching` and `lowest_cost_match`; traffic classes are `public` and
`private`; hallway classifications add `mixed`, `unclassified`, and `unused`.

### Generation specification contracts

```python
FloorSpec(width: float, length: float)
RoomSizeSpec(
    min_width: float,
    max_width: float,
    min_area: float,
    max_area: float,
    width_axis: RoomWidthAxis = RoomWidthAxis.ANY,
)
RoomSpec(id: RoomId, room_type: RoomType, name: str, size: RoomSizeSpec)
RoomRelationSpec(
    source_room_id: RoomId,
    target_room_ids: tuple[RoomId, ...],
    match_policy: MatchPolicy,
    strength: ConstraintStrength,
)
FloorPlanGenerationSpec(
    floor: FloorSpec,
    rooms: tuple[RoomSpec, ...],
    room_relations: tuple[RoomRelationSpec, ...],
)
```

`MatchPolicy` values are `and` and `or`; `ConstraintStrength` values are `hard` and
`soft`; `RoomWidthAxis` values are `any`, `x`, and `y`. `RoomType` serialized values
include `bedroom`, `living_room`, `kitchen`, `bathroom`, `attached_bathroom`,
`hallway`, `veranda`, `garage`, and `dining_room`. Features validate positive finite
floor/room dimensions, unique IDs, relation references, and domain-specific count or
fit requirements.

### Floor-plan contracts

```python
FloorPlanRoom(
    id: RoomId,
    room_type: RoomType,
    name: str,
    boundary: Polygon,
    role: RoomRole = RoomRole.STANDARD,
    parent_room_id: RoomId | None = None,
    metadata: RoomMetadata = RoomMetadata(),
)
FloorPlanOpening(
    id: OpeningId,
    opening_type: OpeningType,
    purpose: OpeningPurpose,
    start: Point,
    end: Point,
    connected_room_ids: tuple[RoomId, ...] = (),
)
FloorPlan(
    boundary: Polygon,
    rooms: list[FloorPlanRoom],
    openings: list[FloorPlanOpening] = [],
    identity_redirects: dict[RoomId, RoomId] = {},
    applied_transformations: set[str] = set(),
)
```

The displayed mutable defaults are created per instance by factories. `RoomRole`
values are `standard` and `solver_placeholder`.
`RoomMetadata(source_room_ids=(), applied_transformations=())` records provenance.
Opening types are `door` and `window`; purposes are `room_connection`,
`main_entrance`, `secondary_entrance`, and `daylight`. Geometry-changing post-processing
mutates the supplied `FloorPlan`; opening generation and both scoring features do not.

## Cross-Feature Compatibility Reference

These are compatibility edges, not a package-mandated pipeline.

| Producer | Output | Consumer | Required compatibility |
|---|---|---|---|
| Buildable Land | `BuildableLandResult.buildable_land`, `.normalized_land` | Usable Land | pass both objects from the same buildable-land execution; normalized edge/source indexes identify the same parcel |
| Preprocessing | `PreparedGenerationInput.candidate_grid`, `.hallway_room_count_range`, `.generation_spec` | Candidate Search | targets must represent the same specification; hallway target count equals the prepared maximum; use the exact resolved grid |
| Candidate Search | `CandidateMap` | Candidate Circulation / Candidate Scoring | preserve the exact `ResolvedCandidateGrid`; room IDs/types and hallway hint identities must remain consistent |
| Candidate Circulation | refined `CandidateMap`, classifications | Floor Plan Solver hints / later scoring | unused and safely consolidated hallway points are absent from the returned map; required-transit routing is already enforced; consumers must keep room/spec identities consistent |
| Floor Plan Solver | `FloorPlan` | Post-Processing | use the same `FloorPlanGenerationSpec` where processors need specification identity |
| Post-Processing | mutable `FloorPlan` result | Openings / Floor Plan Scoring | consume the returned/mutated plan and its `identity_redirects`; do not retain stale pre-transformation room identities |
| Openings | copied `FloorPlan` with generated openings | Floor Plan Scoring | scoring accepts openings but does not mutate them; run openings after geometry-changing post-processing if openings are to remain aligned |

No automatic adapter converts `CandidatePoint` values into `RoomPlacementHint`; the
consumer maps shared room IDs and coordinates explicitly. Candidate scoring and final
floor-plan scoring are different contracts and their scores are not interchangeable.

## Extension and Registry APIs

Registry instances are mutable runtime dependencies. Registration keys/IDs must be
unique; a configured key must resolve before execution.

| Feature | Interface contract | Registry operations | Duplicate/unknown behavior |
|---|---|---|---|
| Candidate Scoring | `CandidateEvaluator.key -> EvaluatorKey`; `evaluate(context: ScoringContext, settings: Mapping[str, Any]) -> EvaluatorResult` | `EvaluatorRegistry(evaluators=())`, `.register(evaluator)`, `.get(key)`, `.contains(key)` | `EvaluatorRegistrationError` |
| Floor Plan Solver | hard: `key: str`, `apply(context, settings) -> None`; soft: `key: str`, `build_penalties(context, settings) -> tuple[PenaltyTerm, ...]` | `ConstraintRegistry()`, `.register_hard`, `.register_soft`, `.get_hard`, `.get_soft`, `.validate_config`; `.validate_profile` is a compatibility alias | `InvalidProfileError` for duplicate; `UnknownConstraintError` for lookup |
| Post-Processing | `FloorPlanProcessor` declares `processor_id`, `description`, `config_type`, optional `prerequisites`; `.is_applicable(floor_plan, context, config) -> tuple[bool, str]`; `.process(floor_plan, context, config) -> ProcessorOutcome` | `ProcessorRegistry(processors=())`, `.register`, `.resolve`, `.processor_ids` | `ConfigurationError` |
| Openings | feature declares `feature_id: str`; `build_demands(prepared, config) -> tuple[OpeningDemand, ...]` | `OpeningFeatureRegistry()`, `.register`, `.resolve` | `OpeningConfigurationError` |
| Floor Plan Scoring | `FloorPlanEvaluator.key`, `.settings_type`, `.evaluate(context, settings) -> EvaluatorResult` | `EvaluatorRegistry(evaluators=())`, `.register`, `.get`, `.contains` | `EvaluatorRegistrationError` |

Use each feature's `create_default_registry()` when retaining shipped behavior and add
custom entries before passing the registry to the operation. Candidate scoring makes
`registry` and `config` required keyword arguments; other registry-enabled operations
accept `None` and build the shipped registry. Extension implementations must return
the exact documented result contract and respect the mode's visualization/debug policy.

## Public Exception and Status Reference

| Feature | Raised public family | Returned status values |
|---|---|---|
| Buildable Land | `BuildableLandError(code, message, details=None)`, plus early `TypeError`/`ValueError` | none; success returns a result |
| Usable Land | `UsableLandError(code, message, details=None)`, plus early `TypeError`/`ValueError` | none; failure to find land raises |
| Preprocessing | `FloorPlanPreprocessingError(message, code=None, details=None)` and exported stage subclasses | none; validation/preparation failures raise |
| Candidate Search | `CandidateSearchError`; `CandidateSearchStateError` for invalid ask/tell/session state | none; no valid completed trial raises |
| Candidate Circulation | `CandidateCirculationError` and exported input/grid/path subclasses | none; route/input failures raise |
| Candidate Scoring | scoring/input/configuration/registration/execution/contract errors described in its section | `EvaluationStatus`: `completed`, `not_applicable`, `skipped` |
| Floor Plan Solver | `FloorPlanSolverError` family | `optimal`, `feasible`, `infeasible`, `model_invalid`, `unknown` |
| Post-Processing | `PostProcessingError` family for configuration/validation/processor/rollback faults | pipeline `success`/`failed`; processor `changed`, `no_change`, `not_applicable`, `failed`, `skipped` |
| Openings | `OpeningGenerationError`; `OpeningConfigurationError` | `optimal`, `feasible`, `infeasible`, `model_invalid`, `unknown`, `invalid_input` |
| Floor Plan Scoring | `FloorPlanScoringError` and exported input/configuration/registry/execution/contract subclasses | evaluator `completed`/`not_applicable`/`skipped`; group `completed`/`failed`/`not_applicable`/`skipped` |

Returned solver/pipeline/opening failures do not raise merely because the status is not
successful. Check the result status and optional payload before access. Exception
families used internally but not feature-root-exported are not preferred import
surfaces; consumers may catch the documented feature-root base class.

## Built-in Defaults and Profiles Reference

| Feature | Public default/profile | Exact role and important values |
|---|---|---|
| Candidate Scoring | `create_default_config()` | enables zone suitability (weight 20/order 10), exterior clearance (20/20), spatial distribution (25/40); relationship quality is registered but not enabled |
| Floor Plan Solver | `DEFAULT_PROFILES`; three named constants | `initial_generation`: 5 s, optional candidate hints; `refinement_a`: 2 s, required existing plan, position/size tolerance 10; `refinement_b`: 2 s, required existing plan, tolerances 5. All use coordinate scale 1 and enable `hallway_efficiency` with weight 1, area multiplier 1, preferred max length 40, excess-length multiplier 5 |
| Post-Processing | `INITIAL_GENERATION_PROFILE` | order: veranda adjustment, wall extension, required placeholder removal+validation, hallway merge, required grid snap+validation, rectilinear simplification; tolerance `1e-6`, grid 1, rejects existing openings |
| Openings | `DEFAULT_OPENING_CONFIG` / `DEFAULT_OPENING_PROFILE` | name `default_openings`; features `interior_doors`, `exterior_doors`, `windows`; constraints `shared_placement`, `room_door_limits`, `required_room_access`; explicit allowed-room pairs; all built-in room types required for access; corner-oriented door priorities; 10 s, one worker, seed 0 |
| Floor Plan Scoring | `DEFAULT_FLOOR_PLAN_SCORING_CONFIG` / `DEFAULT_SCORING_PROFILE` | critical group: geometry integrity, required adjacency, enclosed voids, inward recess, each threshold 100; functional group: `room_size_consistency` weight 2 and `kitchen_dining` weight 1. Legacy living/bedroom evaluators remain registered but are not enabled by default |

Buildable Land, Usable Land, Preprocessing, Candidate Search, and Candidate
Circulation intentionally ship no universal jurisdiction/project profile. Their
consumer supplies domain policy. Defaults shown in individual constructors are
package defaults, not building-code recommendations.

## Compatibility Aliases and Legacy Surfaces

| Compatibility name | Canonical surface | Behavioral difference / migration |
|---|---|---|
| `PreprocessingPolicy`, `PreprocessingReferenceData` | `PreprocessingConfig` | identical runtime class; use `PreprocessingConfig` in new code |
| `CandidateSearchSpaceSelection` | `CandidateGridSelection` | identical runtime class; search-space properties are derived views |
| `CandidateSearchSpace` | `ResolvedCandidateGrid` | legacy origin/size/spacing description; execution requires the resolved grid |
| circulation `TrafficClass` | `CirculationTrafficClass` | identical enum object |
| circulation `GridNode` | `CirculationGridNode` | identical dataclass object |
| `GenerationProfile` | `FloorPlanSolverConfig` | identical runtime class; request field is `config`, not the removed `profile` keyword |
| `ConstraintRegistry.validate_profile()` | `.validate_config()` | same validation; retained for source compatibility |
| `PostProcessingProfile` | `FloorPlanPostProcessingConfig` | identical runtime class |
| `OpeningGenerationProfile` | `FloorPlanOpeningsConfig` | identical type alias |
| `DEFAULT_OPENING_PROFILE` | `DEFAULT_OPENING_CONFIG` | same object |
| `ScoringProfile` | `FloorPlanScoringConfig` | identical runtime class |
| `DEFAULT_SCORING_PROFILE` | `DEFAULT_FLOOR_PLAN_SCORING_CONFIG` | same object |
| `create_default_profile()` | `create_default_config()` | returns the same floor-plan scoring config |

These names are active compatibility exports; source does not mark them deprecated.
The current migration-relevant breaking change is the floor-plan solver request field
rename from `profile=` to `config=`. The serialized/result field
`FloorPlanSolveResult.profile_name` remains unchanged.

## Consumer Migration Notes — 2026-08-15

The current source contains these migration-relevant behavior/contract changes from
the previously documented version:

| Area | Previous documented behavior | Current behavior / consumer action |
|---|---|---|
| Candidate Circulation | route rules had no required-transit field; cleanup removed only unused hallways | `CirculationRouteRule.required_transit_room_types=()` is available; default circulation config now also performs conservative hallway consolidation. Set `HallwayConsolidationConfig(enabled=False)` to retain unused-only cleanup. |
| Floor Plan Scoring | default functional scoring used `living_room_balance` and `bedroom_quality` | default functional scoring now uses `room_size_consistency` plus `kitchen_dining`. Custom configs may still use the legacy evaluator classes/keys. `FloorPlanScoringInput` uses `config=`, not the removed `profile=` field. |
| Floor Plan Openings | hallway/attached-bathroom compatibility included hidden implementation behavior; room access was not a mandatory graph constraint; door placement was center-oriented | `FeaturePolicy.allowed_room_pairs` is authoritative; `required_room_access` is structurally mandatory; required room types must connect to exactly one main entrance; doors prefer wall ends according to `door_placement_priority`. Consumers constructing custom `enabled_constraints` or `FeaturePolicy` must update them. |
| Floor Plan Solver | supplied hallways had hard dimensions/connectivity but no dedicated compactness objective | all built-in profiles enable `hallway_efficiency`, which penalizes total hallway area and excessive length. The solver still cannot remove supplied hallway rooms. Tune via `DefaultProfileSettings` or replace/remove the soft constraint. |

## Consumer Integration Checklist

- [ ] Install on Python 3.11 or newer and import through feature roots/domain.
- [ ] Construct the exact request and config type; do not interchange package-root
  aggregate config sections with feature-local config wrappers unless documented.
- [ ] Keep one project unit/coordinate system throughout a related request.
- [ ] Preserve room IDs, candidate grids, source-edge indexes, and identity redirects
  across compatible features.
- [ ] Handle every returned status separately from raised exceptions.
- [ ] Do not assume DEBUG details exist in PRODUCTION.
- [ ] Respect mutation behavior: post-processing mutates its `FloorPlan`; opening
  generation returns a copy; scoring/search inputs are not mutated.
- [ ] Set solver/search seeds and a single solver worker where repeatable tests matter.
- [ ] Calibrate jurisdiction/domain parameters; package defaults are not regulations.

## Public API Coverage Audit

The following inventory is generated from the active package and feature-root
`__all__` values. A signature is the complete constructor/call contract; enum rows
list every member/value. Type-alias rows resolve to their runtime canonical object.
+
### `fpg_core` exports (8)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `__version__` | constant/type alias | `'0.1.0'` | Documented in the corresponding feature/shared section. |
| `BuildableSpaceConfig` | dataclass/contract | `(active_profile: 'SetbackProfile', usable_land_constraints: 'UsableLandConstraints', validation_limits: 'ValidationLimits') -> None` | BuildableSpaceConfig(active_profile: 'SetbackProfile', usable_land_constraints: 'UsableLandConstraints', validation_limits: 'ValidationLimits') |
| `CandidateSearchConfig` | dataclass/contract | `(trial_count: 'int' = 500, max_grid_node_count: 'int' = 250000, random_seed: 'int \| None' = None) -> None` | Reusable controls for how Candidate Search performs a search. |
| `FpgCoreConfig` | dataclass/contract | `(schema_version: 'int', project_units_per_meter: 'int', buildable_space: 'BuildableSpaceConfig', preprocessing: 'PreprocessingConfig', candidate_search: 'CandidateSearchConfig', candidate_scoring: 'CandidateScoringConfig', floor_plan_solver: 'ProfileCatalog', post_processing: 'PostProcessingProfile', openings: 'OpeningGenerationProfile', floor_plan_scoring: 'FloorPlanScoringConfig') -> None` | FpgCoreConfig(schema_version: 'int', project_units_per_meter: 'int', buildable_space: 'BuildableSpaceConfig', preprocessing: 'PreprocessingConfig', candidate_search: 'CandidateSearchConfig', candidate_scoring: 'CandidateScoringConfig', floor_plan_solver: 'ProfileCatalog', post_processing: 'PostProcessingProfile', openings: 'OpeningGenerationProfile', floor_plan_scoring: 'FloorPlanScoringConfig') |
| `FpgCoreConfigError` | exception | `constructor has no separately inspectable signature` | Documented in the corresponding feature/shared section. |
| `PreprocessingConfig` | dataclass/contract | `(room_count_rules: 'tuple[RoomCountRule, ...]', supported_aspect_ratios: 'tuple[AspectRatioRule, ...]', room_sizes: 'tuple[RoomSizeReference, ...]', room_relations: 'tuple[RoomRelationReference, ...]', mandatory_room_types: 'tuple[RoomType, ...]', floor_area_buffer: 'float', hallway_area_buffer: 'float', max_hallway_room_count: 'int', hallway_min_width: 'float', candidate_search_grid_spacing: 'int', default_room_size: 'str', max_aspect_residual_units: 'float', min_aspect_ratio: 'float' = 0.5, max_aspect_ratio: 'float' = 2.0, room_size_strategy: 'RoomSizeSelectionStrategy' = <RoomSizeSelectionStrategy.MAJORITY: 'majority'>, size_normalization_exclusions: 'tuple[RoomType, ...]' = (<RoomType.HALLWAY: 'hallway'>,), excess_attached_bathrooms: 'ExcessAttachedBathroomPolicy' = <ExcessAttachedBathroomPolicy.REJECT: 'reject'>) -> None` | PreprocessingConfig(room_count_rules: 'tuple[RoomCountRule, ...]', supported_aspect_ratios: 'tuple[AspectRatioRule, ...]', room_sizes: 'tuple[RoomSizeReference, ...]', room_relations: 'tuple[RoomRelationReference, ...]', mandatory_room_types: 'tuple[RoomType, ...]', floor_area_buffer: 'float', hallway_area_buffer: 'float', max_hallway_room_count: 'int', hallway_min_width: 'float', candidate_search_grid_spacing: 'int', default_room_size: 'str', max_aspect_residual_units: 'float', min_aspect_ratio: 'float' = 0.5, max_aspect_ratio: 'float' = 2.0, room_size_strategy: 'RoomSizeSelectionStrategy' = <RoomSizeSelectionStrategy.MAJORITY: 'majority'>, size_normalization_exclusions: 'tuple[RoomType, ...]' = (<RoomType.HALLWAY: 'hallway'>,), excess_attached_bathrooms: 'ExcessAttachedBathroomPolicy' = <ExcessAttachedBathroomPolicy.REJECT: 'reject'>) |
| `validate_fpg_core_config` | function | `validate_fpg_core_config(config: 'FpgCoreConfig') -> 'None'` | Documented in the corresponding feature/shared section. |
| `canonical_aspect_ratio` | function | `canonical_aspect_ratio(value: 'float', rules: 'tuple[AspectRatioRule, ...]', *, tolerance: 'float' = 1e-06) -> 'float \| None'` | Documented in the corresponding feature/shared section. |

### `fpg_core.domain` exports (58)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `BuildableLand` | dataclass/contract | `(boundary: 'Polygon', area: 'float', edge_setbacks: 'tuple[EdgeSetback, ...]') -> None` | BuildableLand(boundary: 'Polygon', area: 'float', edge_setbacks: 'tuple[EdgeSetback, ...]') |
| `BuildableSpaceErrorCode` | enum | `INVALID_REQUEST='invalid_request'; INVALID_LAND_BOUNDARY='invalid_land_boundary'; NON_CONVEX_LAND='non_convex_land'; SELF_INTERSECTING_LAND='self_intersecting_land'; INVALID_ROAD_ATTACHMENT='invalid_road_attachment'; MULTIPLE_MAIN_ENTRY_ROADS='multiple_main_entry_roads'; UNSUPPORTED_ROAD_TYPE='unsupported_road_type'; REFERENCE_DATA_ERROR='reference_data_error'; SETBACK_ELIMINATES_BUILDABLE_LAND='setback_eliminates_buildable_land'; BUILDABLE_LAND_CALCULATION_FAILED='buildable_land_calculation_failed'; NO_USABLE_LAND_FOUND='no_usable_land_found'; SEARCH_LIMIT_EXCEEDED='search_limit_exceeded'; USABLE_LAND_CALCULATION_FAILED='usable_land_calculation_failed'; UNEXPECTED_BUILDABLE_SPACE_ERROR='unexpected_buildable_space_error'` | Documented in the corresponding feature/shared section. |
| `BuildableSpaceReferenceData` | dataclass/contract | `(schema_version: 'int', project_units_per_meter: 'int', active_profile: 'SetbackProfile', usable_land_constraints: 'UsableLandConstraints', validation_limits: 'ValidationLimits') -> None` | BuildableSpaceReferenceData(schema_version: 'int', project_units_per_meter: 'int', active_profile: 'SetbackProfile', usable_land_constraints: 'UsableLandConstraints', validation_limits: 'ValidationLimits') |
| `BuildableSpaceRequestData` | dataclass/contract | `(land_boundary: 'Polygon', roads: 'tuple[RoadAttachment, ...]') -> None` | BuildableSpaceRequestData(land_boundary: 'Polygon', roads: 'tuple[RoadAttachment, ...]') |
| `BuildableSpaceResult` | dataclass/contract | `(original_land_area: 'float', buildable_land: 'BuildableLand', usable_land: 'UsableLand', reference_profile: 'str', project_units_per_meter: 'int') -> None` | BuildableSpaceResult(original_land_area: 'float', buildable_land: 'BuildableLand', usable_land: 'UsableLand', reference_profile: 'str', project_units_per_meter: 'int') |
| `BuildableSpaceStage` | enum | `REQUEST_VALIDATION='request_validation'; REFERENCE_DATA='reference_data'; BUILDABLE_LAND='buildable_land'; USABLE_LAND='usable_land'; RESPONSE='response'` | Documented in the corresponding feature/shared section. |
| `CandidateMap` | dataclass/contract | `(grid: 'ResolvedCandidateGrid', points: 'tuple[CandidatePoint, ...]') -> None` | A candidate hint map coupled to the exact grid that produced it. |
| `CandidatePoint` | dataclass/contract | `(room_id: 'RoomId', x: 'float', y: 'float', room_type: 'RoomType \| None' = None, hint_index: 'int' = 1) -> None` | A reusable room hint coordinate passed between generation features. |
| `CandidateSearchSpace` | dataclass/contract | `(origin_x: 'Coordinate', origin_y: 'Coordinate', width: 'int', length: 'int', grid_spacing: 'int') -> None` | Centered, divisible Candidate Search rectangle in floor coordinates. |
| `CirculationGrid` | dataclass/contract | `(width: 'float', length: 'float', scale: 'float', origin_x: 'float' = 0.0, origin_y: 'float' = 0.0) -> None` | Axis-aligned routing grid expressed in project units. |
| `CirculationGridNode` | dataclass/contract | `(x_index: 'int', y_index: 'int', x: 'float', y: 'float') -> None` | One grid node used by an orthogonal circulation path. |
| `CirculationRouteRule` | dataclass/contract | `(id: 'int', name: 'str', source_room_type: 'RoomType', destination_room_type: 'RoomType', destination_selection: 'DestinationSelection', traffic_class: 'CirculationTrafficClass', allowed_transit_room_types: 'tuple[RoomType, ...]', importance_weight: 'float', required_transit_room_types: 'tuple[RoomType, ...]' = ()) -> None` | Shared typed request for room-type circulation routing, including optional required intermediate room types. |
| `CirculationTrafficClass` | enum | `PUBLIC='public'; PRIVATE='private'` | Architectural traffic carried by a configured route. |
| `ConstraintStrength` | enum | `HARD='hard'; SOFT='soft'` | Documented in the corresponding feature/shared section. |
| `DestinationSelection` | enum | `ALL_MATCHING='all_matching'; LOWEST_COST_MATCH='lowest_cost_match'` | Determines which matching destinations a route rule selects. |
| `EdgeClassification` | dataclass/contract | `(edge_index: 'int', side: 'LandSide') -> None` | EdgeClassification(edge_index: 'int', side: 'LandSide') |
| `EdgeSetback` | dataclass/contract | `(edge_index: 'int', side: 'LandSide', base_setback: 'int', road_adjustment: 'int', final_setback: 'int', road_type: 'RoadType \| None' = None) -> None` | EdgeSetback(edge_index: 'int', side: 'LandSide', base_setback: 'int', road_adjustment: 'int', final_setback: 'int', road_type: 'RoadType \| None' = None) |
| `ExecutionMetadata` | dataclass/contract | `(mode: 'ExecutionMode', duration_seconds: 'float') -> None` | Small execution-wide metadata shared by all feature operations. |
| `ExecutionMode` | enum | `PRODUCTION='production'; DEBUG='debug'` | Controls how much non-result execution data a feature may collect. |
| `FeatureExecution` | dataclass/contract | `(result: 'TResult', details: 'TDetails \| None', metadata: 'ExecutionMetadata') -> None` | Standard envelope returned by completed FPG Core feature operations. |
| `FloorPlan` | dataclass/contract | `(boundary: fpg_core.domain.geometry.Polygon, rooms: list[fpg_core.domain.floor_plan.FloorPlanRoom], openings: list[fpg_core.domain.floor_plan.FloorPlanOpening] = <factory>, identity_redirects: dict[fpg_core.domain.floor_plan_spec.RoomId, fpg_core.domain.floor_plan_spec.RoomId] = <factory>, applied_transformations: set[str] = <factory>) -> None` | FloorPlan(boundary: fpg_core.domain.geometry.Polygon, rooms: list[fpg_core.domain.floor_plan.FloorPlanRoom], openings: list[fpg_core.domain.floor_plan.FloorPlanOpening] = <factory>, identity_redirects: dict[fpg_core.domain.floor_plan_spec.RoomId, fpg_core.domain.floor_plan_spec.RoomId] = <factory>, applied_transformations: set[str] = <factory>) |
| `FloorPlanGenerationSpec` | dataclass/contract | `(floor: fpg_core.domain.floor_plan_spec.FloorSpec, rooms: tuple[fpg_core.domain.floor_plan_spec.RoomSpec, ...], room_relations: tuple[fpg_core.domain.floor_plan_spec.RoomRelationSpec, ...]) -> None` | FloorPlanGenerationSpec(floor: fpg_core.domain.floor_plan_spec.FloorSpec, rooms: tuple[fpg_core.domain.floor_plan_spec.RoomSpec, ...], room_relations: tuple[fpg_core.domain.floor_plan_spec.RoomRelationSpec, ...]) |
| `FloorPlanOpening` | dataclass/contract | `(id: fpg_core.domain.floor_plan.OpeningId, opening_type: fpg_core.domain.floor_plan.OpeningType, purpose: fpg_core.domain.floor_plan.OpeningPurpose, start: fpg_core.domain.geometry.Point, end: fpg_core.domain.geometry.Point, connected_room_ids: tuple[fpg_core.domain.floor_plan_spec.RoomId, ...] = ()) -> None` | FloorPlanOpening(id: fpg_core.domain.floor_plan.OpeningId, opening_type: fpg_core.domain.floor_plan.OpeningType, purpose: fpg_core.domain.floor_plan.OpeningPurpose, start: fpg_core.domain.geometry.Point, end: fpg_core.domain.geometry.Point, connected_room_ids: tuple[fpg_core.domain.floor_plan_spec.RoomId, ...] = ()) |
| `FloorPlanRoom` | dataclass/contract | `(id: fpg_core.domain.floor_plan_spec.RoomId, room_type: fpg_core.domain.floor_plan_spec.RoomType, name: str, boundary: fpg_core.domain.geometry.Polygon, role: fpg_core.domain.floor_plan.RoomRole = <RoomRole.STANDARD: 'standard'>, parent_room_id: Optional[fpg_core.domain.floor_plan_spec.RoomId] = None, metadata: fpg_core.domain.floor_plan.RoomMetadata = <factory>) -> None` | FloorPlanRoom(id: fpg_core.domain.floor_plan_spec.RoomId, room_type: fpg_core.domain.floor_plan_spec.RoomType, name: str, boundary: fpg_core.domain.geometry.Polygon, role: fpg_core.domain.floor_plan.RoomRole = <RoomRole.STANDARD: 'standard'>, parent_room_id: Optional[fpg_core.domain.floor_plan_spec.RoomId] = None, metadata: fpg_core.domain.floor_plan.RoomMetadata = <factory>) |
| `FloorSpec` | dataclass/contract | `(width: float, length: float) -> None` | FloorSpec(width: float, length: float) |
| `FloorWidthAlignment` | enum | `PARALLEL_TO_ENTRY_ROAD='parallel_to_entry_road'; PERPENDICULAR_TO_ENTRY_ROAD='perpendicular_to_entry_road'` | Documented in the corresponding feature/shared section. |
| `GridRoutingCostProfile` | dataclass/contract | `(empty_node_cost: 'float', traversable_hint_node_cost: 'float', turn_cost: 'float', perimeter_bias_max_cost: 'float') -> None` | Costs shared by orthogonal grid-routing features. |
| `HallwayClassification` | dataclass/contract | `(room_id: 'RoomId', hint_index: 'int', traffic_class: 'HallwayTrafficClass') -> None` | Production-safe traffic classification for one hallway hint point. |
| `HallwayRoomCountRange` | dataclass/contract | `(maximum: 'int', minimum: 'int' = 1) -> None` | Allowed number of distinct hallway rooms in one candidate trial. |
| `HallwayTrafficClass` | enum | `PUBLIC='public'; PRIVATE='private'; MIXED='mixed'; UNCLASSIFIED='unclassified'; UNUSED='unused'` | Traffic role assigned to one hallway hint point. |
| `LandEdge` | dataclass/contract | `(index: 'int', source_edge_index: 'int', segment: 'Segment') -> None` | LandEdge(index: 'int', source_edge_index: 'int', segment: 'Segment') |
| `LandSide` | enum | `FRONT='front'; BACK='back'; LEFT='left'; RIGHT='right'` | Documented in the corresponding feature/shared section. |
| `MatchPolicy` | enum | `AND='and'; OR='or'` | Documented in the corresponding feature/shared section. |
| `NormalizedLand` | dataclass/contract | `(boundary: 'Polygon', edges: 'tuple[LandEdge, ...]', main_entry_road: 'RoadAttachment') -> None` | NormalizedLand(boundary: 'Polygon', edges: 'tuple[LandEdge, ...]', main_entry_road: 'RoadAttachment') |
| `OpeningId` | constant/type alias | `NewType instance` | NewType creates simple unique types with almost zero runtime overhead. |
| `OpeningPurpose` | enum | `ROOM_CONNECTION='room_connection'; MAIN_ENTRANCE='main_entrance'; SECONDARY_ENTRANCE='secondary_entrance'; DAYLIGHT='daylight'` | Documented in the corresponding feature/shared section. |
| `OpeningType` | enum | `DOOR='door'; WINDOW='window'` | Documented in the corresponding feature/shared section. |
| `Point` | dataclass/contract | `(x: 'float', y: 'float') -> None` | Point(x: 'float', y: 'float') |
| `Polygon` | dataclass/contract | `(points: 'tuple[Point, ...]') -> None` | Polygon(points: 'tuple[Point, ...]') |
| `RoadAttachment` | dataclass/contract | `(boundary_edge_index: 'int', role: 'RoadRole', road_type: 'RoadType') -> None` | RoadAttachment(boundary_edge_index: 'int', role: 'RoadRole', road_type: 'RoadType') |
| `RoadRole` | enum | `MAIN_ENTRY='main_entry'` | Documented in the corresponding feature/shared section. |
| `ResolvedCandidateGrid` | dataclass/contract | `(x_positions: 'tuple[Coordinate, ...]', y_positions: 'tuple[Coordinate, ...]') -> None` | Exact uniform candidate-location and orthogonal-routing grid. |
| `RoadType` | enum | `MAIN_ROAD='main_road'; PRIVATE_ROAD='private_road'` | Documented in the corresponding feature/shared section. |
| `RoomId` | constant/type alias | `NewType instance` | NewType creates simple unique types with almost zero runtime overhead. |
| `RoomMetadata` | dataclass/contract | `(source_room_ids: tuple[fpg_core.domain.floor_plan_spec.RoomId, ...] = (), applied_transformations: tuple[str, ...] = ()) -> None` | Typed post-solver provenance retained with a room. |
| `RoomRelationSpec` | dataclass/contract | `(source_room_id: fpg_core.domain.floor_plan_spec.RoomId, target_room_ids: tuple[fpg_core.domain.floor_plan_spec.RoomId, ...], match_policy: fpg_core.domain.floor_plan_spec.MatchPolicy, strength: fpg_core.domain.floor_plan_spec.ConstraintStrength) -> None` | RoomRelationSpec(source_room_id: fpg_core.domain.floor_plan_spec.RoomId, target_room_ids: tuple[fpg_core.domain.floor_plan_spec.RoomId, ...], match_policy: fpg_core.domain.floor_plan_spec.MatchPolicy, strength: fpg_core.domain.floor_plan_spec.ConstraintStrength) |
| `RoomRole` | enum | `STANDARD='standard'; SOLVER_PLACEHOLDER='solver_placeholder'` | Documented in the corresponding feature/shared section. |
| `RoomSizeSpec` | dataclass/contract | `(min_width: float, max_width: float, min_area: float, max_area: float, width_axis: fpg_core.domain.floor_plan_spec.RoomWidthAxis = <RoomWidthAxis.ANY: 'any'>) -> None` | RoomSizeSpec(min_width: float, max_width: float, min_area: float, max_area: float, width_axis: fpg_core.domain.floor_plan_spec.RoomWidthAxis = <RoomWidthAxis.ANY: 'any'>) |
| `RoomSpec` | dataclass/contract | `(id: fpg_core.domain.floor_plan_spec.RoomId, room_type: fpg_core.domain.floor_plan_spec.RoomType, name: str, size: fpg_core.domain.floor_plan_spec.RoomSizeSpec) -> None` | RoomSpec(id: fpg_core.domain.floor_plan_spec.RoomId, room_type: fpg_core.domain.floor_plan_spec.RoomType, name: str, size: fpg_core.domain.floor_plan_spec.RoomSizeSpec) |
| `RoomType` | enum | `BEDROOM='bedroom'; BATHROOM='bathroom'; ATTACHED_BATHROOM='attached_bathroom'; LIVING_ROOM='living_room'; KITCHEN='kitchen'; DINING_ROOM='dining_room'; HALLWAY='hallway'; VERANDA='veranda'; GARAGE='garage'` | Documented in the corresponding feature/shared section. |
| `RoomWidthAxis` | enum | `ANY='any'; X='x'; Y='y'` | Axis to which the room's width range applies. |
| `RouteCostBreakdown` | dataclass/contract | `(movement_cost: 'float', perimeter_bias_cost: 'float', turn_cost: 'float', traffic_conflict_cost: 'float', total_cost: 'float') -> None` | Cost components accumulated by one resolved circulation route. |
| `Segment` | dataclass/contract | `(start: 'Point', end: 'Point') -> None` | Segment(start: 'Point', end: 'Point') |
| `SetbackCalculationMode` | enum | `BASE_PLUS_ROAD_ADJUSTMENT='base_plus_road_adjustment'` | Documented in the corresponding feature/shared section. |
| `SetbackProfile` | dataclass/contract | `(name: 'str', status: 'str', description: 'str', calculation_mode: 'SetbackCalculationMode', base_setbacks: 'Mapping[LandSide, int]', road_adjustments: 'Mapping[RoadType, Mapping[LandSide, int]]') -> None` | SetbackProfile(name: 'str', status: 'str', description: 'str', calculation_mode: 'SetbackCalculationMode', base_setbacks: 'Mapping[LandSide, int]', road_adjustments: 'Mapping[RoadType, Mapping[LandSide, int]]') |
| `UsableLand` | dataclass/contract | `(boundary: 'Polygon', width: 'int', length: 'int', area: 'int', floor_width_alignment: 'FloorWidthAlignment', entry_road_edge_index: 'int') -> None` | UsableLand(boundary: 'Polygon', width: 'int', length: 'int', area: 'int', floor_width_alignment: 'FloorWidthAlignment', entry_road_edge_index: 'int') |
| `UsableLandConstraints` | dataclass/contract | `(minimum_width: 'int', minimum_length: 'int', search_resolution: 'int', maximum_sweep_lines: 'int') -> None` | UsableLandConstraints(minimum_width: 'int', minimum_length: 'int', search_resolution: 'int', maximum_sweep_lines: 'int') |
| `ValidationLimits` | dataclass/contract | `(minimum_vertex_count: 'int', maximum_vertex_count: 'int', maximum_absolute_coordinate: 'int') -> None` | ValidationLimits(minimum_vertex_count: 'int', maximum_vertex_count: 'int', maximum_absolute_coordinate: 'int') |

### `fpg_core.buildable_land` exports (6)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `BuildableLandConfig` | dataclass/contract | `(setback_profile: 'SetbackProfile', validation_limits: 'ValidationLimits') -> None` | Reusable validation and setback policy for buildable-land calculation. |
| `BuildableLandDetails` | dataclass/contract | `(edge_classifications: 'tuple[EdgeClassification, ...]') -> None` | DEBUG-only land-side classification information. |
| `BuildableLandError` | exception | `(code: 'BuildableSpaceErrorCode', message: 'str', *, details: 'dict[str, object] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `BuildableLandInput` | dataclass/contract | `(request: 'BuildableSpaceRequestData', config: 'BuildableLandConfig') -> None` | Request-specific land data plus reusable buildable-land configuration. |
| `BuildableLandResult` | dataclass/contract | `(buildable_land: 'BuildableLand', normalized_land: 'NormalizedLand') -> None` | Production output required by later land-processing stages. |
| `calculate_buildable_land` | function | `calculate_buildable_land(buildable_input: 'BuildableLandInput', *, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FeatureExecution[BuildableLandResult, BuildableLandDetails]'` | Validate a land request, apply setbacks, and calculate buildable land. |

### `fpg_core.usable_land` exports (5)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `UsableLandConfig` | dataclass/contract | `(minimum_width: 'int', minimum_length: 'int', search_resolution: 'int', maximum_sweep_lines: 'int') -> None` | Reusable search limits and dimensional requirements. |
| `UsableLandDetails` | dataclass/contract | `(evaluated_rectangle_pairs: 'int', local_buildable_boundary: 'Polygon', selected_local_boundary: 'Polygon', transform_origin: 'Point', transform_x_axis: 'tuple[float, float]', transform_y_axis: 'tuple[float, float]') -> None` | DEBUG-only search and road-aligned geometry information. |
| `UsableLandError` | exception | `(code: 'BuildableSpaceErrorCode', message: 'str', *, details: 'dict[str, object] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `UsableLandInput` | dataclass/contract | `(buildable_land: 'BuildableLand', land: 'NormalizedLand', config: 'UsableLandConfig') -> None` | Land geometry being processed plus reusable usable-land configuration. |
| `find_usable_land` | function | `find_usable_land(usable_input: 'UsableLandInput', *, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FeatureExecution[UsableLand, UsableLandDetails]'` | Find the best road-aligned rectangle inside buildable land. |

### `fpg_core.floor_plan_preprocessing` exports (36)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `AspectRatioRule` | dataclass/contract | `(label: 'str', canonical_value: 'float') -> None` | AspectRatioRule(label: 'str', canonical_value: 'float') |
| `BusinessRuleError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `CandidateGridSelection` | dataclass/contract | `(floor_width: 'int', floor_length: 'int', grid: 'ResolvedCandidateGrid') -> None` | DEBUG explanation of the grid prepared for downstream features. |
| `CandidateSearchSpaceSelection` | dataclass/contract | `(floor_width: 'int', floor_length: 'int', grid: 'ResolvedCandidateGrid') -> None` | DEBUG explanation of the grid prepared for downstream features. |
| `ContextValidationError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `ExcessAttachedBathroomPolicy` | enum | `REMOVE='remove'; REJECT='reject'` | Documented in the corresponding feature/shared section. |
| `FloorLimits` | dataclass/contract | `(max_width: 'float', max_length: 'float') -> None` | FloorLimits(max_width: 'float', max_length: 'float') |
| `FloorPlanPreprocessingError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Base class for expected preprocessing failures. |
| `FloorPreparationError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `FloorSelection` | dataclass/contract | `(requested_width: 'float', requested_length: 'float', normalized_max_width: 'int', normalized_max_length: 'int', selected_width: 'int', selected_length: 'int', requested_aspect_ratio: 'float', selected_aspect_ratio: 'float', aspect_residual_units: 'float', minimum_required_area: 'float', maximum_target_area: 'float', unused_limit_area: 'float') -> None` | FloorSelection(requested_width: 'float', requested_length: 'float', normalized_max_width: 'int', normalized_max_length: 'int', selected_width: 'int', selected_length: 'int', requested_aspect_ratio: 'float', selected_aspect_ratio: 'float', aspect_residual_units: 'float', minimum_required_area: 'float', maximum_target_area: 'float', unused_limit_area: 'float') |
| `InputValidationError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `NormalizationError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `NormalizationRecord` | dataclass/contract | `(field: 'str', original: 'str', normalized: 'str') -> None` | NormalizationRecord(field: 'str', original: 'str', normalized: 'str') |
| `OutputValidationError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `PreprocessingConfig` | dataclass/contract | `(room_count_rules: 'tuple[RoomCountRule, ...]', supported_aspect_ratios: 'tuple[AspectRatioRule, ...]', room_sizes: 'tuple[RoomSizeReference, ...]', room_relations: 'tuple[RoomRelationReference, ...]', mandatory_room_types: 'tuple[RoomType, ...]', floor_area_buffer: 'float', hallway_area_buffer: 'float', max_hallway_room_count: 'int', hallway_min_width: 'float', candidate_search_grid_spacing: 'int', default_room_size: 'str', max_aspect_residual_units: 'float', min_aspect_ratio: 'float' = 0.5, max_aspect_ratio: 'float' = 2.0, room_size_strategy: 'RoomSizeSelectionStrategy' = <RoomSizeSelectionStrategy.MAJORITY: 'majority'>, size_normalization_exclusions: 'tuple[RoomType, ...]' = (<RoomType.HALLWAY: 'hallway'>,), excess_attached_bathrooms: 'ExcessAttachedBathroomPolicy' = <ExcessAttachedBathroomPolicy.REJECT: 'reject'>) -> None` | PreprocessingConfig(room_count_rules: 'tuple[RoomCountRule, ...]', supported_aspect_ratios: 'tuple[AspectRatioRule, ...]', room_sizes: 'tuple[RoomSizeReference, ...]', room_relations: 'tuple[RoomRelationReference, ...]', mandatory_room_types: 'tuple[RoomType, ...]', floor_area_buffer: 'float', hallway_area_buffer: 'float', max_hallway_room_count: 'int', hallway_min_width: 'float', candidate_search_grid_spacing: 'int', default_room_size: 'str', max_aspect_residual_units: 'float', min_aspect_ratio: 'float' = 0.5, max_aspect_ratio: 'float' = 2.0, room_size_strategy: 'RoomSizeSelectionStrategy' = <RoomSizeSelectionStrategy.MAJORITY: 'majority'>, size_normalization_exclusions: 'tuple[RoomType, ...]' = (<RoomType.HALLWAY: 'hallway'>,), excess_attached_bathrooms: 'ExcessAttachedBathroomPolicy' = <ExcessAttachedBathroomPolicy.REJECT: 'reject'>) |
| `PreprocessingErrorCode` | enum | `INVALID_INPUT='invalid_input'; INVALID_ASPECT_RATIO='invalid_aspect_ratio'; INVALID_ROOM_COUNT='invalid_room_count'; FORBIDDEN_ROOM_TYPE='forbidden_room_type'; DUPLICATE_ROOM_ID='duplicate_room_id'; ATTACHED_BATHROOM_COUNT_EXCEEDS_BEDROOMS='attached_bathroom_count_exceeds_bedrooms'; NORMALIZATION_FAILED='normalization_failed'; INVALID_REFERENCE_DATA='invalid_reference_data'; MISSING_ROOM_REFERENCE='missing_room_reference'; INVALID_ROOM_RELATION='invalid_room_relation'; FLOOR_LIMITS_INSUFFICIENT='floor_limits_insufficient'; INVALID_PREPARED_CONTEXT='invalid_prepared_context'; INVALID_PREPROCESSING_OUTPUT='invalid_preprocessing_output'` | Documented in the corresponding feature/shared section. |
| `PreprocessingExecution` | constant/type alias | `_GenericAlias instance` | Documented in the corresponding feature/shared section. |
| `PreprocessingInput` | dataclass/contract | `(request: 'PreprocessingRequest', config: 'PreprocessingConfig') -> None` | PreprocessingInput(request: 'PreprocessingRequest', config: 'PreprocessingConfig') |
| `PreprocessingPolicy` | dataclass/contract | `(room_count_rules: 'tuple[RoomCountRule, ...]', supported_aspect_ratios: 'tuple[AspectRatioRule, ...]', room_sizes: 'tuple[RoomSizeReference, ...]', room_relations: 'tuple[RoomRelationReference, ...]', mandatory_room_types: 'tuple[RoomType, ...]', floor_area_buffer: 'float', hallway_area_buffer: 'float', max_hallway_room_count: 'int', hallway_min_width: 'float', candidate_search_grid_spacing: 'int', default_room_size: 'str', max_aspect_residual_units: 'float', min_aspect_ratio: 'float' = 0.5, max_aspect_ratio: 'float' = 2.0, room_size_strategy: 'RoomSizeSelectionStrategy' = <RoomSizeSelectionStrategy.MAJORITY: 'majority'>, size_normalization_exclusions: 'tuple[RoomType, ...]' = (<RoomType.HALLWAY: 'hallway'>,), excess_attached_bathrooms: 'ExcessAttachedBathroomPolicy' = <ExcessAttachedBathroomPolicy.REJECT: 'reject'>) -> None` | PreprocessingConfig(room_count_rules: 'tuple[RoomCountRule, ...]', supported_aspect_ratios: 'tuple[AspectRatioRule, ...]', room_sizes: 'tuple[RoomSizeReference, ...]', room_relations: 'tuple[RoomRelationReference, ...]', mandatory_room_types: 'tuple[RoomType, ...]', floor_area_buffer: 'float', hallway_area_buffer: 'float', max_hallway_room_count: 'int', hallway_min_width: 'float', candidate_search_grid_spacing: 'int', default_room_size: 'str', max_aspect_residual_units: 'float', min_aspect_ratio: 'float' = 0.5, max_aspect_ratio: 'float' = 2.0, room_size_strategy: 'RoomSizeSelectionStrategy' = <RoomSizeSelectionStrategy.MAJORITY: 'majority'>, size_normalization_exclusions: 'tuple[RoomType, ...]' = (<RoomType.HALLWAY: 'hallway'>,), excess_attached_bathrooms: 'ExcessAttachedBathroomPolicy' = <ExcessAttachedBathroomPolicy.REJECT: 'reject'>) |
| `PreprocessingReferenceData` | dataclass/contract | `(room_count_rules: 'tuple[RoomCountRule, ...]', supported_aspect_ratios: 'tuple[AspectRatioRule, ...]', room_sizes: 'tuple[RoomSizeReference, ...]', room_relations: 'tuple[RoomRelationReference, ...]', mandatory_room_types: 'tuple[RoomType, ...]', floor_area_buffer: 'float', hallway_area_buffer: 'float', max_hallway_room_count: 'int', hallway_min_width: 'float', candidate_search_grid_spacing: 'int', default_room_size: 'str', max_aspect_residual_units: 'float', min_aspect_ratio: 'float' = 0.5, max_aspect_ratio: 'float' = 2.0, room_size_strategy: 'RoomSizeSelectionStrategy' = <RoomSizeSelectionStrategy.MAJORITY: 'majority'>, size_normalization_exclusions: 'tuple[RoomType, ...]' = (<RoomType.HALLWAY: 'hallway'>,), excess_attached_bathrooms: 'ExcessAttachedBathroomPolicy' = <ExcessAttachedBathroomPolicy.REJECT: 'reject'>) -> None` | PreprocessingConfig(room_count_rules: 'tuple[RoomCountRule, ...]', supported_aspect_ratios: 'tuple[AspectRatioRule, ...]', room_sizes: 'tuple[RoomSizeReference, ...]', room_relations: 'tuple[RoomRelationReference, ...]', mandatory_room_types: 'tuple[RoomType, ...]', floor_area_buffer: 'float', hallway_area_buffer: 'float', max_hallway_room_count: 'int', hallway_min_width: 'float', candidate_search_grid_spacing: 'int', default_room_size: 'str', max_aspect_residual_units: 'float', min_aspect_ratio: 'float' = 0.5, max_aspect_ratio: 'float' = 2.0, room_size_strategy: 'RoomSizeSelectionStrategy' = <RoomSizeSelectionStrategy.MAJORITY: 'majority'>, size_normalization_exclusions: 'tuple[RoomType, ...]' = (<RoomType.HALLWAY: 'hallway'>,), excess_attached_bathrooms: 'ExcessAttachedBathroomPolicy' = <ExcessAttachedBathroomPolicy.REJECT: 'reject'>) |
| `PreprocessingReport` | dataclass/contract | `(normalizations: 'tuple[NormalizationRecord, ...]', room_decisions: 'tuple[RoomDecision, ...]', relation_decisions: 'tuple[RelationDecision, ...]', selected_room_size: 'str', floor_selection: 'FloorSelection', candidate_search_space_selection: 'CandidateGridSelection', hallway_room_count_range: 'HallwayRoomCountRange', applied_defaults: 'tuple[str, ...]' = (), warnings: 'tuple[str, ...]' = ()) -> None` | Debug-only preprocessing decisions and normalized input information. |
| `PreprocessingRequest` | dataclass/contract | `(floor_limits: 'FloorLimits', aspect_ratio: 'float \| str', rooms: 'tuple[RequestedRoom, ...]') -> None` | PreprocessingRequest(floor_limits: 'FloorLimits', aspect_ratio: 'float \| str', rooms: 'tuple[RequestedRoom, ...]') |
| `PreprocessingStage` | enum | `INPUT_VALIDATION='input_validation'; NORMALIZATION='normalization'; REFERENCE_DATA='reference_data'; BUSINESS_RULES='business_rules'; ROOM_PREPARATION='room_preparation'; RELATION_PREPARATION='relation_preparation'; FLOOR_PREPARATION='floor_preparation'; CONTEXT_VALIDATION='context_validation'; OUTPUT_VALIDATION='output_validation'` | Documented in the corresponding feature/shared section. |
| `PreparedGenerationInput` | dataclass/contract | `(generation_spec: 'FloorPlanGenerationSpec', candidate_grid: 'ResolvedCandidateGrid', hallway_room_count_range: 'HallwayRoomCountRange') -> None` | Production result shared with Candidate Search and later generation stages. |
| `ReferenceDataError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `RelationDecision` | dataclass/contract | `(source_room_type: 'RoomType', action: 'str', detail: 'str') -> None` | RelationDecision(source_room_type: 'RoomType', action: 'str', detail: 'str') |
| `RelationPreparationError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `RequestedRoom` | dataclass/contract | `(room_type: 'RoomType', id: 'str \| None' = None, name: 'str \| None' = None, requested_size: 'str \| None' = None) -> None` | RequestedRoom(room_type: 'RoomType', id: 'str \| None' = None, name: 'str \| None' = None, requested_size: 'str \| None' = None) |
| `RoomCountRule` | dataclass/contract | `(room_type: 'RoomType', minimum: 'int', maximum: 'int', client_selectable: 'bool' = True) -> None` | RoomCountRule(room_type: 'RoomType', minimum: 'int', maximum: 'int', client_selectable: 'bool' = True) |
| `RoomDecision` | dataclass/contract | `(room_id: 'str', room_type: 'RoomType', action: 'str', reason: 'str') -> None` | RoomDecision(room_id: 'str', room_type: 'RoomType', action: 'str', reason: 'str') |
| `RoomPreparationError` | exception | `(message: 'str', *, code: 'PreprocessingErrorCode \| None' = None, details: 'Mapping[str, Any] \| None' = None) -> 'None'` | Documented in the corresponding feature/shared section. |
| `RoomRelationReference` | dataclass/contract | `(source_room_type: 'RoomType', target_room_types: 'tuple[RoomType, ...]', match_policy: 'MatchPolicy \| str', strength: 'ConstraintStrength \| str', required: 'bool' = True) -> None` | RoomRelationReference(source_room_type: 'RoomType', target_room_types: 'tuple[RoomType, ...]', match_policy: 'MatchPolicy \| str', strength: 'ConstraintStrength \| str', required: 'bool' = True) |
| `RoomSizeReference` | dataclass/contract | `(room_type: 'RoomType', size: 'str', min_width: 'float', max_width: 'float', min_area: 'float', max_area: 'float') -> None` | RoomSizeReference(room_type: 'RoomType', size: 'str', min_width: 'float', max_width: 'float', min_area: 'float', max_area: 'float') |
| `RoomSizeSelectionStrategy` | enum | `MAJORITY='majority'` | Documented in the corresponding feature/shared section. |
| `canonical_aspect_ratio` | function | `canonical_aspect_ratio(value: 'float', rules: 'tuple[AspectRatioRule, ...]', *, tolerance: 'float' = 1e-06) -> 'float \| None'` | Documented in the corresponding feature/shared section. |
| `prepare_generation_input` | function | `prepare_generation_input(input: 'PreprocessingInput', *, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'PreprocessingExecution'` | Prepare one trusted generation specification without external side effects. |

### `fpg_core.candidate_search` exports (17)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `CandidateEvaluator` | constant/type alias | `_CallableGenericAlias instance` | Documented in the corresponding feature/shared section. |
| `CandidateSearchConfig` | dataclass/contract | `(trial_count: 'int' = 500, max_grid_node_count: 'int' = 250000, random_seed: 'int \| None' = None) -> None` | Reusable controls for how Candidate Search performs a search. |
| `CandidateSearchDetails` | dataclass/contract | `(grid: 'ResolvedCandidateGrid', optuna_trial_count: 'int', completed_trial_count: 'int') -> None` | DEBUG-only grid and Optuna trial information. |
| `CandidateSearchError` | exception | `constructor has no separately inspectable signature` | Base exception for candidate-search execution failures. |
| `CandidateSearchInput` | dataclass/contract | `(targets: 'tuple[CandidateSearchTarget, ...]', grid: 'ResolvedCandidateGrid', hallway_room_count_range: 'HallwayRoomCountRange', evaluator: 'CandidateEvaluator', config: 'CandidateSearchConfig') -> None` | Processing input and execution dependency for one Candidate Search. |
| `CandidateSearchResult` | dataclass/contract | `(candidate: 'CandidateMap', score: 'float', completed_trials: 'int') -> None` | Best candidate arrangement discovered by a completed search. |
| `CandidateSearchSession` | class/interface/registry | `(search_input: 'CandidateSearchInput') -> 'None'` | Incremental Optuna-backed uniform-grid candidate search. |
| `CandidateSearchSpace` | dataclass/contract | `(origin_x: 'Coordinate', origin_y: 'Coordinate', width: 'int', length: 'int', grid_spacing: 'int') -> None` | Centered, divisible Candidate Search rectangle in floor coordinates. |
| `CandidateSearchStateError` | exception | `constructor has no separately inspectable signature` | Raised when session methods are called in an invalid order or state. |
| `CandidateSearchTarget` | dataclass/contract | `(room_id: 'RoomId', room_type: 'RoomType \| None' = None) -> None` | Identifies one concrete room that may receive one candidate point. |
| `CandidateSuggestion` | dataclass/contract | `(trial_number: 'int', candidate: 'CandidateMap') -> None` | One valid, non-overlapping candidate produced by an Optuna trial. |
| `CandidateTrialResult` | dataclass/contract | `(trial_number: 'int', candidate: 'CandidateMap', score: 'float', completed_trials: 'int') -> None` | Candidate and score produced by one completed search trial. |
| `HallwayRoomCountRange` | dataclass/contract | `(maximum: 'int', minimum: 'int' = 1) -> None` | Allowed number of distinct hallway rooms in one candidate trial. |
| `ResolvedCandidateGrid` | dataclass/contract | `(x_positions: 'tuple[Coordinate, ...]', y_positions: 'tuple[Coordinate, ...]') -> None` | Exact uniform candidate-location and orthogonal-routing grid. |
| `build_candidate_grid` | function | `build_candidate_grid(*, grid: 'ResolvedCandidateGrid', max_grid_node_count: 'int') -> 'ResolvedCandidateGrid'` | Validate and return the exact grid prepared by preprocessing. |
| `build_candidate_search_targets` | function | `build_candidate_search_targets(specification: fpg_core.domain.floor_plan_spec.FloorPlanGenerationSpec) -> tuple[fpg_core.candidate_search.models.CandidateSearchTarget, ...]` | Create one concrete Candidate Search target for every prepared room. |
| `search_candidates` | function | `search_candidates(search_input: 'CandidateSearchInput', *, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FeatureExecution[CandidateSearchResult, CandidateSearchDetails]'` | Run the complete uniform-grid candidate search. |

### `fpg_core.candidate_circulation` exports (26)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `CandidateCirculationConfig` | dataclass/contract | `(costs: 'RoutingCostProfile', route_rules: 'tuple[CirculationRouteRule, ...]', always_traversable_room_types: 'tuple[RoomType, ...]', max_routing_passes: 'int' = 3, hallway_consolidation: 'HallwayConsolidationConfig' = <factory>) -> None` | Reusable routing policy; request-specific grid comes from `CandidateMap`. |
| `CandidateCirculationDetails` | dataclass/contract | `(circulation_efficiency_score: 'float', routing_pass_count: 'int', grid_node_count: 'int', passes: 'tuple[RoutingPassDetails, ...]', final_hallway_traffic: 'tuple[HallwayTrafficDetails, ...]', removed_hallway_points: 'tuple[RemovedHallwayPointDetails, ...]', hallway_consolidation_attempts: 'tuple[HallwayConsolidationAttemptDetails, ...]') -> None` | DEBUG-only route efficiency, hallway traffic, removals, and route-verified consolidation attempts. |
| `CandidateCirculationError` | exception | `constructor has no separately inspectable signature` | Base exception for candidate circulation failures. |
| `CandidateCirculationInput` | dataclass/contract | `(candidate: 'CandidateMap', config: 'CandidateCirculationConfig') -> None` | Candidate map and reusable circulation policy. |
| `CandidateCirculationInputError` | exception | `constructor has no separately inspectable signature` | Raised when the circulation input or configuration is invalid. |
| `CandidateCirculationResult` | dataclass/contract | `(candidate: 'CandidateMap', hallway_classifications: 'tuple[HallwayClassification, ...]' = ()) -> None` | Production result with cleaned candidate and retained hallway traffic tags. |
| `CirculationPathDetails` | dataclass/contract | `(rule_id: 'int', rule_name: 'str', traffic_class: 'CirculationTrafficClass', destination_selection: 'DestinationSelection', allowed_transit_room_types: 'tuple[RoomType, ...]', required_transit_room_types: 'tuple[RoomType, ...]', required_transit_point_keys: 'tuple[str, ...]', importance_weight: 'float', source_point_key: 'str', source_room_id: 'str', source_room_type: 'RoomType', destination_point_key: 'str', destination_room_id: 'str', destination_room_type: 'RoomType', nodes: 'tuple[CirculationGridNode, ...]', step_count: 'int', manhattan_step_count: 'int', detour_step_count: 'int', turn_count: 'int', manhattan_reference_cost: 'float', costs: 'RouteCostBreakdown', path_efficiency_score: 'float') -> None` | DEBUG data for one expanded and resolved route, including required-transit evidence. |
| `CirculationTrafficClass` | enum | `PUBLIC='public'; PRIVATE='private'` | Architectural traffic carried by a configured route. |
| `CirculationPathNotFoundError` | exception | `constructor has no separately inspectable signature` | Raised when a configured route cannot be resolved on the grid. |
| `CirculationRouteRule` | dataclass/contract | `(id: 'int', name: 'str', source_room_type: 'RoomType', destination_room_type: 'RoomType', destination_selection: 'DestinationSelection', traffic_class: 'CirculationTrafficClass', allowed_transit_room_types: 'tuple[RoomType, ...]', importance_weight: 'float', required_transit_room_types: 'tuple[RoomType, ...]' = ()) -> None` | Shared typed request for room-type circulation routing; required types constrain the intermediate path. |
| `DestinationSelection` | enum | `ALL_MATCHING='all_matching'; LOWEST_COST_MATCH='lowest_cost_match'` | Determines which matching destinations a route rule selects. |
| `GridAlignmentError` | exception | `constructor has no separately inspectable signature` | Raised when a hint point does not align with the configured grid. |
| `GridNode` | dataclass/contract | `(x_index: 'int', y_index: 'int', x: 'float', y: 'float') -> None` | One grid node used by an orthogonal circulation path. |
| `HallwayClassification` | dataclass/contract | `(room_id: 'RoomId', hint_index: 'int', traffic_class: 'HallwayTrafficClass') -> None` | Production-safe traffic classification for one retained hallway hint point. |
| `HallwayConsolidationAttemptDetails` | dataclass/contract | `(point_key: 'str', nearby_point_keys: 'tuple[str, ...]', decision: 'HallwayConsolidationDecision', max_route_cost_increase_ratio: 'float | None') -> None` | DEBUG record of one route-verified nearby-hallway removal attempt. |
| `HallwayConsolidationConfig` | dataclass/contract | `(enabled: 'bool' = True, minimum_separation_grid_steps: 'float' = 2.0, max_route_cost_increase_ratio: 'float' = 0.15) -> None` | Controls conservative removal of redundant nearby hallway hints. |
| `HallwayConsolidationDecision` | enum | `REMOVED='removed'; KEPT_ROUTE_UNAVAILABLE='kept_route_unavailable'; KEPT_ROUTE_COVERAGE_CHANGED='kept_route_coverage_changed'; KEPT_ROUTE_COST_INCREASE='kept_route_cost_increase'` | DEBUG outcome of testing one hallway for consolidation. |
| `HallwayRemovalReason` | enum | `UNUSED='unused'; CONSOLIDATED='consolidated'` | Why a hallway hint was removed from the production candidate. |
| `HallwayTrafficClass` | enum | `PUBLIC='public'; PRIVATE='private'; MIXED='mixed'; UNCLASSIFIED='unclassified'; UNUSED='unused'` | Traffic role assigned to one hallway hint point. |
| `HallwayTrafficDetails` | dataclass/contract | `(point_key: 'str', room_id: 'str', hint_index: 'int', x: 'float', y: 'float', public_route_count: 'int', private_route_count: 'int', public_importance_weight: 'float', private_importance_weight: 'float', traffic_class: 'HallwayTrafficClass', removed: 'bool', removal_reason: 'HallwayRemovalReason | None') -> None` | Traffic totals, final role, and optional removal reason for one hallway hint. |
| `RemovedHallwayPointDetails` | dataclass/contract | `(point_key: 'str', room_id: 'str', hint_index: 'int', x: 'float', y: 'float', reason: 'HallwayRemovalReason') -> None` | Identity, position, and removal reason for one removed hallway hint. |
| `RouteCostBreakdown` | dataclass/contract | `(movement_cost: 'float', perimeter_bias_cost: 'float', turn_cost: 'float', traffic_conflict_cost: 'float', total_cost: 'float') -> None` | Cost components accumulated by one resolved circulation route. |
| `RoutingCostProfile` | dataclass/contract | `(empty_node_cost: 'float', traversable_hint_node_cost: 'float', turn_cost: 'float', perimeter_bias_max_cost: 'float', traffic_conflict_cost: 'float') -> None` | Routing costs including the multi-pass hallway conflict penalty. |
| `RoutingPassDetails` | dataclass/contract | `(pass_number: 'int', classifications_changed_from_previous: 'bool', paths: 'tuple[CirculationPathDetails, ...]', hallway_traffic: 'tuple[HallwayTrafficDetails, ...]') -> None` | DEBUG snapshot of one routing and hallway-classification pass. |
| `TrafficClass` | enum | `PUBLIC='public'; PRIVATE='private'` | Backward-compatible feature-boundary alias of `CirculationTrafficClass`. |
| `refine_candidate_circulation` | function | `refine_candidate_circulation(circulation_input: 'CandidateCirculationInput', *, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]'` | Resolve routes, classify hallways, remove unused hallway hints, then optionally consolidate nearby redundant hallway hints. |

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

### `fpg_core.floor_plan_solver` exports (25)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `DEFAULT_PROFILES` | dataclass/contract | `constructor has no separately inspectable signature` | ProfileCatalog(initial: 'GenerationProfile', refinement_a: 'GenerationProfile', refinement_b: 'GenerationProfile') |
| `DefaultProfileSettings` | dataclass/contract | `(coordinate_scale: 'int' = 1, minimum_coverage_ratio: 'float' = 0.6, minimum_adjacency_overlap: 'float' = 10, attached_bathroom_minimum_shared_wall: 'float' = 10.0, initial_max_time_seconds: 'float' = 5.0, refinement_max_time_seconds: 'float' = 2.0, refinement_position_tolerance: 'float' = 10, refinement_size_tolerance: 'float' = 10, hallway_efficiency_weight: 'int' = 1, hallway_area_penalty_multiplier: 'int' = 1, hallway_preferred_max_length: 'float | None' = 40.0, hallway_excess_length_penalty_multiplier: 'int' = 5) -> None` | Central tuning values used to construct the built-in profiles, including hallway compactness weights. |
| `ConstraintRegistry` | dataclass/contract | `(hard: 'dict[str, HardConstraint]' = <factory>, soft: 'dict[str, SoftConstraint]' = <factory>) -> None` | Runtime collection of available hard and soft constraints. |
| `FloorPlanSolveExecution` | constant/type alias | `_GenericAlias instance` | Documented in the corresponding feature/shared section. |
| `FloorPlanSolveRequest` | dataclass/contract | `(specification: 'FloorPlanGenerationSpec', config: 'FloorPlanSolverConfig', candidate_hints: 'tuple[RoomPlacementHint, ...]' = (), existing_floor_plan: 'FloorPlan \| None' = None) -> None` | Processing input for one floor-plan solve. |
| `FloorPlanSolveResult` | dataclass/contract | `(status: 'SolverStatus', floor_plan: 'FloorPlan \| None', profile_name: 'str', message: 'str') -> None` | FloorPlanSolveResult(status: 'SolverStatus', floor_plan: 'FloorPlan \| None', profile_name: 'str', message: 'str') |
| `FloorPlanSolver` | class/interface/registry | `(registry: 'ConstraintRegistry \| None' = None) -> 'None'` | Small application service that owns one generic CP-SAT pipeline. |
| `FloorPlanSolverConfig` | dataclass/contract | `(name: 'str', hard_constraints: 'tuple[HardConstraintUse, ...]', soft_constraints: 'tuple[SoftConstraintUse, ...]', solver: 'SolverConfig' = <factory>, preparation: 'PreparationConfig' = <factory>, seed: 'SeedPolicy' = <factory>) -> None` | Complete reusable configuration for one CP-SAT generation stage. |
| `FloorPlanSolverError` | exception | `constructor has no separately inspectable signature` | Base exception for invalid solver input or configuration. |
| `GenerationProfile` | dataclass/contract | `(name: 'str', hard_constraints: 'tuple[HardConstraintUse, ...]', soft_constraints: 'tuple[SoftConstraintUse, ...]', solver: 'SolverConfig' = <factory>, preparation: 'PreparationConfig' = <factory>, seed: 'SeedPolicy' = <factory>) -> None` | Complete reusable configuration for one CP-SAT generation stage. |
| `HardConstraintUse` | dataclass/contract | `(key: 'str', settings: 'Mapping[str, Any]' = <factory>) -> None` | Configuration for one enabled hard constraint. |
| `INITIAL_GENERATION_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Complete reusable configuration for one CP-SAT generation stage. |
| `PreparationConfig` | dataclass/contract | `(coordinate_scale: 'int' = 10) -> None` | Conversion settings between project units and CP-SAT integer units. |
| `ProfileCatalog` | dataclass/contract | `(initial: 'GenerationProfile', refinement_a: 'GenerationProfile', refinement_b: 'GenerationProfile') -> None` | ProfileCatalog(initial: 'GenerationProfile', refinement_a: 'GenerationProfile', refinement_b: 'GenerationProfile') |
| `REFINEMENT_A_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Complete reusable configuration for one CP-SAT generation stage. |
| `REFINEMENT_B_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Complete reusable configuration for one CP-SAT generation stage. |
| `RoomPlacementHint` | dataclass/contract | `(room_id: 'RoomId', x: 'float', y: 'float', width: 'float \| None' = None, length: 'float \| None' = None) -> None` | Candidate-search hint for a room's lower-left position and optional size. |
| `SeedPolicy` | dataclass/contract | `(source: 'SeedSource' = <SeedSource.NONE: 'none'>, require_source: 'bool' = False, apply_hints: 'bool' = True, position_tolerance: 'float \| None' = None, size_tolerance: 'float \| None' = None) -> None` | Controls how candidate or existing-layout geometry is used as a seed. |
| `SeedSource` | enum | `NONE='none'; CANDIDATE_HINTS='candidate_hints'; EXISTING_FLOOR_PLAN='existing_floor_plan'` | Documented in the corresponding feature/shared section. |
| `SoftConstraintUse` | dataclass/contract | `(key: 'str', weight: 'int', settings: 'Mapping[str, Any]' = <factory>) -> None` | Configuration for one enabled soft constraint and its objective weight. |
| `SolverConfig` | dataclass/contract | `(max_time_seconds: 'float' = 30.0, num_search_workers: 'int' = 0, random_seed: 'int \| None' = None, log_search_progress: 'bool' = False, relative_gap_limit: 'float \| None' = None, cp_model_presolve: 'bool' = True) -> None` | OR-Tools runtime settings for one solve. |
| `SolverDiagnostics` | dataclass/contract | `(raw_status: 'str', wall_time_seconds: 'float', objective_value: 'float \| None', best_objective_bound: 'float \| None', conflicts: 'int', branches: 'int', applied_hard_constraints: 'tuple[str, ...]', applied_soft_constraints: 'tuple[str, ...]', penalty_terms: 'tuple[str, ...]') -> None` | SolverDiagnostics(raw_status: 'str', wall_time_seconds: 'float', objective_value: 'float \| None', best_objective_bound: 'float \| None', conflicts: 'int', branches: 'int', applied_hard_constraints: 'tuple[str, ...]', applied_soft_constraints: 'tuple[str, ...]', penalty_terms: 'tuple[str, ...]') |
| `SolverStatus` | enum | `OPTIMAL='optimal'; FEASIBLE='feasible'; INFEASIBLE='infeasible'; MODEL_INVALID='model_invalid'; UNKNOWN='unknown'` | Documented in the corresponding feature/shared section. |
| `build_default_profiles` | function | `build_default_profiles(settings: 'DefaultProfileSettings \| None' = None) -> 'ProfileCatalog'` | Documented in the corresponding feature/shared section. |
| `generate_floor_plan` | function | `generate_floor_plan(request: 'FloorPlanSolveRequest', *, registry: 'ConstraintRegistry \| None' = None, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FloorPlanSolveExecution'` | Documented in the corresponding feature/shared section. |

### `fpg_core.floor_plan_post_processing` exports (31)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `ConfigurationError` | exception | `constructor has no separately inspectable signature` | Documented in the corresponding feature/shared section. |
| `FloorPlanPostProcessingConfig` | dataclass/contract | `(name: 'str', processors: 'tuple[ProcessorUse, ...]', numeric: 'NumericPolicy' = <factory>, reject_existing_openings: 'bool' = True) -> None` | Complete reusable configuration for floor-plan post-processing. |
| `FloorPlanProcessor` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `GridSnapConfig` | dataclass/contract | `(grid_size: 'float \| None' = None) -> None` | GridSnapConfig(grid_size: 'float \| None' = None) |
| `HallwayMergeConfig` | dataclass/contract | `(minimum_shared_wall: 'float' = 10.0) -> None` | HallwayMergeConfig(minimum_shared_wall: 'float' = 10.0) |
| `INITIAL_GENERATION_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Complete reusable configuration for floor-plan post-processing. |
| `NumericPolicy` | dataclass/contract | `(tolerance: 'float' = 1e-06, grid_size: 'float' = 1.0) -> None` | Numerical tolerances and grid settings used by the pipeline. |
| `PipelineStatus` | enum | `SUCCESS='success'; FAILED='failed'` | Documented in the corresponding feature/shared section. |
| `PlaceholderRemovalConfig` | dataclass/contract | `() -> None` | PlaceholderRemovalConfig() |
| `PostProcessingContext` | dataclass/contract | `(mode: 'ExecutionMode', specification: 'FloorPlanGenerationSpec \| None', floor_boundary: 'Polygon', numeric: 'NumericPolicy', profile_name: 'str') -> None` | PostProcessingContext(mode: 'ExecutionMode', specification: 'FloorPlanGenerationSpec \| None', floor_boundary: 'Polygon', numeric: 'NumericPolicy', profile_name: 'str') |
| `PostProcessingDetails` | dataclass/contract | `(executions: 'tuple[ProcessorExecution, ...]') -> None` | PostProcessingDetails(executions: 'tuple[ProcessorExecution, ...]') |
| `PostProcessingError` | exception | `constructor has no separately inspectable signature` | Base error for the standalone post-processing component. |
| `PostProcessingExecution` | constant/type alias | `_GenericAlias instance` | Documented in the corresponding feature/shared section. |
| `PostProcessingProfile` | dataclass/contract | `(name: 'str', processors: 'tuple[ProcessorUse, ...]', numeric: 'NumericPolicy' = <factory>, reject_existing_openings: 'bool' = True) -> None` | Complete reusable configuration for floor-plan post-processing. |
| `PostProcessingRequest` | dataclass/contract | `(floor_plan: 'FloorPlan', config: 'FloorPlanPostProcessingConfig', specification: 'FloorPlanGenerationSpec \| None' = None) -> None` | Processing input for one post-processing execution. |
| `PostProcessingResult` | dataclass/contract | `(status: 'PipelineStatus', floor_plan: 'FloorPlan', failure: 'ProcessingFailure \| None' = None) -> None` | PostProcessingResult(status: 'PipelineStatus', floor_plan: 'FloorPlan', failure: 'ProcessingFailure \| None' = None) |
| `ProcessingFailure` | dataclass/contract | `(code: 'str', message: 'str', processor_id: 'str \| None' = None) -> None` | ProcessingFailure(code: 'str', message: 'str', processor_id: 'str \| None' = None) |
| `ProcessorError` | exception | `constructor has no separately inspectable signature` | Documented in the corresponding feature/shared section. |
| `ProcessorExecution` | dataclass/contract | `(processor_id: 'str', status: 'ProcessorStatus', duration_ms: 'float', rolled_back: 'bool' = False, outcome: 'ProcessorOutcome \| None' = None, failure: 'ProcessingFailure \| None' = None) -> None` | ProcessorExecution(processor_id: 'str', status: 'ProcessorStatus', duration_ms: 'float', rolled_back: 'bool' = False, outcome: 'ProcessorOutcome \| None' = None, failure: 'ProcessingFailure \| None' = None) |
| `ProcessorOutcome` | dataclass/contract | `(status: 'ProcessorStatus', message: 'str', affected_room_ids: 'tuple[RoomId, ...]' = (), identity_redirects: 'Mapping[RoomId, RoomId]' = <factory>, metrics: 'Mapping[str, int \| float \| str \| bool]' = <factory>) -> None` | ProcessorOutcome(status: 'ProcessorStatus', message: 'str', affected_room_ids: 'tuple[RoomId, ...]' = (), identity_redirects: 'Mapping[RoomId, RoomId]' = <factory>, metrics: 'Mapping[str, int \| float \| str \| bool]' = <factory>) |
| `ProcessorRegistry` | class/interface/registry | `(processors: 'Iterable[FloorPlanProcessor]' = ()) -> 'None'` | Documented in the corresponding feature/shared section. |
| `ProcessorStatus` | enum | `CHANGED='changed'; NO_CHANGE='no_change'; NOT_APPLICABLE='not_applicable'; FAILED='failed'; SKIPPED='skipped'` | Documented in the corresponding feature/shared section. |
| `ProcessorUse` | dataclass/contract | `(processor_id: 'str', config: 'object', required: 'bool' = False, validate_after: 'bool' = False) -> None` | Configuration for one processor in the ordered pipeline. |
| `RectilinearSimplificationConfig` | dataclass/contract | `() -> None` | RectilinearSimplificationConfig() |
| `RollbackError` | exception | `constructor has no separately inspectable signature` | Documented in the corresponding feature/shared section. |
| `ValidationError` | exception | `constructor has no separately inspectable signature` | Documented in the corresponding feature/shared section. |
| `VerandaAdjustmentConfig` | dataclass/contract | `(transformation_version: 'str' = 'veranda_adjustment:v1') -> None` | VerandaAdjustmentConfig(transformation_version: 'str' = 'veranda_adjustment:v1') |
| `WallExtensionConfig` | dataclass/contract | `(rules: 'tuple[WallExtensionRule, ...]' = (WallExtensionRule(room_type=<RoomType.VERANDA: 'veranda'>, min_wall_length=10, max_wall_length=50, max_rooms=3, max_selections=1, expansion_percentage=0.8, max_distance=40), WallExtensionRule(room_type=<RoomType.LIVING_ROOM: 'living_room'>, min_wall_length=10, max_wall_length=40, max_rooms=1, max_selections=2, expansion_percentage=0.8, max_distance=20), WallExtensionRule(room_type=<RoomType.KITCHEN: 'kitchen'>, min_wall_length=10, max_wall_length=40, max_rooms=1, max_selections=1, expansion_percentage=0.8, max_distance=10), WallExtensionRule(room_type=<RoomType.HALLWAY: 'hallway'>, min_wall_length=5, max_wall_length=50, max_rooms=3, max_selections=3, expansion_percentage=0.8, max_distance=2), WallExtensionRule(room_type=<RoomType.BEDROOM: 'bedroom'>, min_wall_length=10, max_wall_length=40, max_rooms=3, max_selections=1, expansion_percentage=0.8, max_distance=10)), transformation_version: 'str' = 'wall_extension:v1') -> None` | WallExtensionConfig(rules: 'tuple[WallExtensionRule, ...]' = (WallExtensionRule(room_type=<RoomType.VERANDA: 'veranda'>, min_wall_length=10, max_wall_length=50, max_rooms=3, max_selections=1, expansion_percentage=0.8, max_distance=40), WallExtensionRule(room_type=<RoomType.LIVING_ROOM: 'living_room'>, min_wall_length=10, max_wall_length=40, max_rooms=1, max_selections=2, expansion_percentage=0.8, max_distance=20), WallExtensionRule(room_type=<RoomType.KITCHEN: 'kitchen'>, min_wall_length=10, max_wall_length=40, max_rooms=1, max_selections=1, expansion_percentage=0.8, max_distance=10), WallExtensionRule(room_type=<RoomType.HALLWAY: 'hallway'>, min_wall_length=5, max_wall_length=50, max_rooms=3, max_selections=3, expansion_percentage=0.8, max_distance=2), WallExtensionRule(room_type=<RoomType.BEDROOM: 'bedroom'>, min_wall_length=10, max_wall_length=40, max_rooms=3, max_selections=1, expansion_percentage=0.8, max_distance=10)), transformation_version: 'str' = 'wall_extension:v1') |
| `WallExtensionRule` | dataclass/contract | `(room_type: 'RoomType', min_wall_length: 'float', max_wall_length: 'float', max_rooms: 'int', max_selections: 'int', expansion_percentage: 'float', max_distance: 'float') -> None` | WallExtensionRule(room_type: 'RoomType', min_wall_length: 'float', max_wall_length: 'float', max_rooms: 'int', max_selections: 'int', expansion_percentage: 'float', max_distance: 'float') |
| `create_default_registry` | function | `create_default_registry() -> 'ProcessorRegistry'` | Documented in the corresponding feature/shared section. |
| `post_process_floor_plan` | function | `post_process_floor_plan(request: 'PostProcessingRequest', *, registry: 'ProcessorRegistry \| None' = None, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'PostProcessingExecution'` | Run one configured post-processing pipeline on a typed floor plan. |

### `fpg_core.floor_plan_openings` exports (20)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `generate_openings` | function | `generate_openings(request: 'OpeningGenerationRequest', *, registry: 'OpeningFeatureRegistry \| None' = None, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'OpeningGenerationExecution'` | Generate openings on a finalized floor plan without mutating it. |
| `DimensionConfig` | dataclass/contract | `(door_width: 'float' = 8.0, window_width: 'float' = 16.0, minimum_shared_wall: 'float' = 10.0) -> None` | DimensionConfig(door_width: 'float' = 8.0, window_width: 'float' = 16.0, minimum_shared_wall: 'float' = 10.0) |
| `FeaturePolicy` | dataclass/contract | `(allowed_room_pairs: 'tuple[tuple[RoomType, RoomType], ...]' = ((RoomType.BEDROOM, RoomType.LIVING_ROOM), (RoomType.KITCHEN, RoomType.LIVING_ROOM), (RoomType.BATHROOM, RoomType.LIVING_ROOM), (RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM), (RoomType.VERANDA, RoomType.LIVING_ROOM), (RoomType.GARAGE, RoomType.LIVING_ROOM), (RoomType.DINING_ROOM, RoomType.LIVING_ROOM), (RoomType.BEDROOM, RoomType.HALLWAY), (RoomType.BATHROOM, RoomType.HALLWAY), (RoomType.LIVING_ROOM, RoomType.HALLWAY), (RoomType.KITCHEN, RoomType.HALLWAY), (RoomType.DINING_ROOM, RoomType.HALLWAY), (RoomType.VERANDA, RoomType.HALLWAY), (RoomType.GARAGE, RoomType.HALLWAY), (RoomType.HALLWAY, RoomType.HALLWAY)), room_door_caps: 'tuple[tuple[RoomType, int], ...]' = ((RoomType.BEDROOM, 2), (RoomType.BATHROOM, 1), (RoomType.LIVING_ROOM, 10), (RoomType.HALLWAY, 10), (RoomType.KITCHEN, 1), (RoomType.ATTACHED_BATHROOM, 1), (RoomType.VERANDA, 1), (RoomType.GARAGE, 1), (RoomType.DINING_ROOM, 2)), secondary_room_priority: 'tuple[RoomType, ...]' = (RoomType.KITCHEN, RoomType.HALLWAY), window_room_types: 'tuple[RoomType, ...]' = (RoomType.BEDROOM, RoomType.LIVING_ROOM, RoomType.KITCHEN, RoomType.DINING_ROOM), main_side_priority: 'tuple[str, ...]' = ('south', 'east', 'north', 'west'), secondary_side_priority: 'tuple[str, ...]' = ('north', 'west', 'east', 'south'), window_side_priority: 'tuple[str, ...]' = ('east', 'north', 'south', 'west'), required_access_room_types: 'tuple[RoomType, ...]' = (RoomType.BEDROOM, RoomType.BATHROOM, RoomType.ATTACHED_BATHROOM, RoomType.LIVING_ROOM, RoomType.KITCHEN, RoomType.DINING_ROOM, RoomType.HALLWAY, RoomType.VERANDA, RoomType.GARAGE), door_placement_priority: 'tuple[tuple[RoomType, int], ...]' = ((RoomType.BEDROOM, 100), (RoomType.BATHROOM, 100), (RoomType.ATTACHED_BATHROOM, 100), (RoomType.KITCHEN, 80), (RoomType.DINING_ROOM, 60), (RoomType.GARAGE, 60), (RoomType.VERANDA, 40), (RoomType.LIVING_ROOM, 20), (RoomType.HALLWAY, 10))) -> None` | Consumer-owned authoritative room-pair, access, door-limit, side-priority, and door-end-placement policy. |
| `FloorPlanOpeningsConfig` | dataclass/contract | `(name: 'str', enabled_features: 'tuple[str, ...]' = ('interior_doors', 'exterior_doors', 'windows'), enabled_constraints: 'tuple[str, ...]' = ('shared_placement', 'room_door_limits', 'required_room_access'), geometry: 'GeometryConfig' = <factory>, dimensions: 'DimensionConfig' = <factory>, policy: 'FeaturePolicy' = <factory>, objective: 'ObjectiveConfig' = <factory>, solver: 'SolverConfig' = <factory>) -> None` | Reusable configuration controlling opening generation behavior. |
| `GeometryConfig` | dataclass/contract | `(coordinate_scale: 'int' = 10, tolerance: 'float' = 1e-06, corner_clearance: 'float' = 0.0, window_spacing: 'float' = 5.0) -> None` | GeometryConfig(coordinate_scale: 'int' = 10, tolerance: 'float' = 1e-06, corner_clearance: 'float' = 0.0, window_spacing: 'float' = 5.0) |
| `ObjectiveConfig` | dataclass/contract | `(tier_order: 'tuple[str, ...]' = ('window', 'secondary_entrance', 'other_interior', 'preferred_hallway', 'bathroom_hallway', 'attached_bathroom', 'main_entrance')) -> None` | ObjectiveConfig(tier_order: 'tuple[str, ...]' = ('window', 'secondary_entrance', 'other_interior', 'preferred_hallway', 'bathroom_hallway', 'attached_bathroom', 'main_entrance')) |
| `SolverConfig` | dataclass/contract | `(max_time_seconds: 'float' = 10.0, num_search_workers: 'int' = 1, random_seed: 'int' = 0, cp_model_presolve: 'bool' = True, log_search_progress: 'bool' = False) -> None` | SolverConfig(max_time_seconds: 'float' = 10.0, num_search_workers: 'int' = 1, random_seed: 'int' = 0, cp_model_presolve: 'bool' = True, log_search_progress: 'bool' = False) |
| `OpeningDiagnostics` | dataclass/contract | `(raw_status: 'str', wall_time_seconds: 'float' = 0.0, objective_value: 'float \| None' = None, best_objective_bound: 'float \| None' = None, conflicts: 'int' = 0, branches: 'int' = 0, analyzed_wall_count: 'int' = 0, demand_counts: 'Mapping[str, int]' = <factory>, candidate_counts: 'Mapping[str, int]' = <factory>, selected_counts: 'Mapping[str, int]' = <factory>, applied_constraints: 'tuple[str, ...]' = (), objective_terms: 'tuple[str, ...]' = (), issues: 'tuple[OpeningIssue, ...]' = ()) -> None` | OpeningDiagnostics(raw_status: 'str', wall_time_seconds: 'float' = 0.0, objective_value: 'float \| None' = None, best_objective_bound: 'float \| None' = None, conflicts: 'int' = 0, branches: 'int' = 0, analyzed_wall_count: 'int' = 0, demand_counts: 'Mapping[str, int]' = <factory>, candidate_counts: 'Mapping[str, int]' = <factory>, selected_counts: 'Mapping[str, int]' = <factory>, applied_constraints: 'tuple[str, ...]' = (), objective_terms: 'tuple[str, ...]' = (), issues: 'tuple[OpeningIssue, ...]' = ()) |
| `OpeningGenerationExecution` | constant/type alias | `_GenericAlias instance` | Documented in the corresponding feature/shared section. |
| `OpeningGenerationRequest` | dataclass/contract | `(floor_plan: 'FloorPlan', config: 'FloorPlanOpeningsConfig') -> None` | OpeningGenerationRequest(floor_plan: 'FloorPlan', config: 'FloorPlanOpeningsConfig') |
| `OpeningGenerationResult` | dataclass/contract | `(status: 'OpeningGenerationStatus', floor_plan: 'FloorPlan \| None', profile_name: 'str', message: 'str') -> None` | OpeningGenerationResult(status: 'OpeningGenerationStatus', floor_plan: 'FloorPlan \| None', profile_name: 'str', message: 'str') |
| `OpeningGenerationStatus` | enum | `OPTIMAL='optimal'; FEASIBLE='feasible'; INFEASIBLE='infeasible'; MODEL_INVALID='model_invalid'; UNKNOWN='unknown'; INVALID_INPUT='invalid_input'` | Documented in the corresponding feature/shared section. |
| `OpeningIssue` | dataclass/contract | `(code: 'str', message: 'str', feature_id: 'str \| None' = None, demand_id: 'str \| None' = None, wall_id: 'str \| None' = None) -> None` | OpeningIssue(code: 'str', message: 'str', feature_id: 'str \| None' = None, demand_id: 'str \| None' = None, wall_id: 'str \| None' = None) |
| `DEFAULT_OPENING_CONFIG` | dataclass/contract | `constructor has no separately inspectable signature` | Reusable configuration controlling opening generation behavior. |
| `DEFAULT_OPENING_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Reusable configuration controlling opening generation behavior. |
| `OpeningGenerationProfile` | dataclass/contract | `(name: 'str', enabled_features: 'tuple[str, ...]' = ('interior_doors', 'exterior_doors', 'windows'), enabled_constraints: 'tuple[str, ...]' = ('shared_placement', 'room_door_limits', 'required_room_access'), geometry: 'GeometryConfig' = <factory>, dimensions: 'DimensionConfig' = <factory>, policy: 'FeaturePolicy' = <factory>, objective: 'ObjectiveConfig' = <factory>, solver: 'SolverConfig' = <factory>) -> None` | Reusable configuration controlling opening generation behavior. |
| `OpeningFeatureRegistry` | class/interface/registry | `() -> 'None'` | Documented in the corresponding feature/shared section. |
| `create_default_registry` | function | `create_default_registry() -> 'OpeningFeatureRegistry'` | Documented in the corresponding feature/shared section. |
| `OpeningConfigurationError` | exception | `constructor has no separately inspectable signature` | Raised for programmer-facing configuration or registry errors. |
| `OpeningGenerationError` | exception | `constructor has no separately inspectable signature` | Base class for opening-generation failures. |

### `fpg_core.floor_plan_scoring` exports (64)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `AESTHETIC_GROUP` | constant/type alias | `'aesthetic'` | Documented in the corresponding feature/shared section. |
| `BEDROOM_QUALITY_KEY` | constant/type alias | `'bedroom_quality'` | Documented in the corresponding feature/shared section. |
| `CRITICAL_GROUP` | constant/type alias | `'critical'` | Documented in the corresponding feature/shared section. |
| `DEFAULT_FLOOR_PLAN_SCORING_CONFIG` | dataclass/contract | `constructor has no separately inspectable signature` | Reusable configuration controlling how a floor plan is scored. |
| `DEFAULT_SCORING_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Reusable configuration controlling how a floor plan is scored. |
| `ENCLOSED_VOIDS_KEY` | constant/type alias | `'enclosed_voids'` | Documented in the corresponding feature/shared section. |
| `EXTRA_GROUP` | constant/type alias | `'extra'` | Documented in the corresponding feature/shared section. |
| `FUNCTIONAL_GROUP` | constant/type alias | `'functional'` | Documented in the corresponding feature/shared section. |
| `GEOMETRY_INTEGRITY_KEY` | constant/type alias | `'geometry_integrity'` | Documented in the corresponding feature/shared section. |
| `INWARD_RECESS_KEY` | constant/type alias | `'inward_recess'` | Documented in the corresponding feature/shared section. |
| `KITCHEN_DINING_KEY` | constant/type alias | `'kitchen_dining_proximity'` | Documented in the corresponding feature/shared section. |
| `LIVING_ROOM_BALANCE_KEY` | constant/type alias | `'living_room_balance'` | Documented in the corresponding feature/shared section. |
| `ROOM_SIZE_CONSISTENCY_KEY` | constant/type alias | `'room_size_consistency'` | Stable key for the configurable room-size consistency evaluator. |
| `REQUIRED_ADJACENCY_KEY` | constant/type alias | `'required_adjacency'` | Documented in the corresponding feature/shared section. |
| `BedroomQualityEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `BedroomQualitySettings` | dataclass/contract | `(area_compliance_weight: 'float', consistency_weight: 'float', full_spread_penalty_ratio: 'float', maximum_spread_penalty: 'float') -> None` | BedroomQualitySettings(area_compliance_weight: 'float', consistency_weight: 'float', full_spread_penalty_ratio: 'float', maximum_spread_penalty: 'float') |
| `EnclosedVoidsEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `EnclosedVoidsSettings` | dataclass/contract | `(area_tolerance: 'float') -> None` | EnclosedVoidsSettings(area_tolerance: 'float') |
| `EvaluationStatus` | enum | `COMPLETED='completed'; NOT_APPLICABLE='not_applicable'; SKIPPED='skipped'` | Documented in the corresponding feature/shared section. |
| `EvaluatorContractError` | exception | `constructor has no separately inspectable signature` | Raised when an evaluator returns a result outside the common contract. |
| `EvaluatorExecutionError` | exception | `constructor has no separately inspectable signature` | Raised when an evaluator fails unexpectedly while scoring. |
| `EvaluatorExecutionResult` | dataclass/contract | `(evaluator_key: 'EvaluatorKey', group_key: 'GroupKey', status: 'EvaluationStatus', raw_score: 'float \| None', configured_weight: 'float', normalized_weight: 'float' = 0.0, contribution: 'float' = 0.0, threshold: 'float \| None' = None, passed_threshold: 'bool \| None' = None, findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = (), visualization_payload: 'object \| None' = None) -> None` | EvaluatorExecutionResult(evaluator_key: 'EvaluatorKey', group_key: 'GroupKey', status: 'EvaluationStatus', raw_score: 'float \| None', configured_weight: 'float', normalized_weight: 'float' = 0.0, contribution: 'float' = 0.0, threshold: 'float \| None' = None, passed_threshold: 'bool \| None' = None, findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = (), visualization_payload: 'object \| None' = None) |
| `EvaluatorKey` | constant/type alias | `NewType instance` | NewType creates simple unique types with almost zero runtime overhead. |
| `EvaluatorRegistrationError` | exception | `constructor has no separately inspectable signature` | Raised for duplicate or missing evaluator registrations. |
| `EvaluatorRegistry` | class/interface/registry | `(evaluators: 'Iterable[FloorPlanEvaluator]' = ()) -> 'None'` | Documented in the corresponding feature/shared section. |
| `EvaluatorResult` | dataclass/contract | `(evaluator_key: 'EvaluatorKey', status: 'EvaluationStatus', score: 'float \| None', findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = (), visualization_payload: 'object \| None' = None) -> None` | EvaluatorResult(evaluator_key: 'EvaluatorKey', status: 'EvaluationStatus', score: 'float \| None', findings: 'tuple[ScoreFinding, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = (), visualization_payload: 'object \| None' = None) |
| `EvaluatorRule` | dataclass/contract | `(key: 'EvaluatorKey', group_key: 'GroupKey', settings: 'object', enabled: 'bool' = True, order: 'int' = 0, weight: 'float' = 1.0, minimum_score: 'float \| None' = None) -> None` | Configuration for one registered evaluator inside a scoring group. |
| `FindingSeverity` | enum | `INFO='info'; WARNING='warning'; ERROR='error'` | Documented in the corresponding feature/shared section. |
| `FloorPlanEvaluator` | class/interface/registry | `()` | Common contract for all floor-plan evaluators. |
| `FloorPlanScoringConfig` | dataclass/contract | `(groups: 'tuple[ScoringGroupRule, ...]', evaluators: 'tuple[EvaluatorRule, ...]') -> None` | Reusable configuration controlling how a floor plan is scored. |
| `FloorPlanScoringDetails` | dataclass/contract | `(group_results: 'tuple[ScoringGroupResult, ...]', evaluator_results: 'tuple[EvaluatorExecutionResult, ...]', findings: 'tuple[ScoreFinding, ...]' = ()) -> None` | DEBUG-only scoring breakdown and evaluator diagnostics. |
| `FloorPlanScoringError` | exception | `constructor has no separately inspectable signature` | Base exception for the floor-plan scoring package. |
| `FloorPlanScoringExecution` | constant/type alias | `_GenericAlias instance` | Documented in the corresponding feature/shared section. |
| `FloorPlanScoringInput` | dataclass/contract | `(floor_plan: 'FloorPlan', specification: 'FloorPlanGenerationSpec', config: 'FloorPlanScoringConfig') -> None` | Request-specific scoring data plus reusable scoring configuration. |
| `FloorPlanScoringResult` | dataclass/contract | `(total_score: 'float', passed_critical: 'bool', critical_failure: 'ScoreFinding \| None') -> None` | FloorPlanScoringResult(total_score: 'float', passed_critical: 'bool', critical_failure: 'ScoreFinding \| None') |
| `GeometryIntegrityEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `GeometryIntegritySettings` | dataclass/contract | `(tolerance: 'float') -> None` | GeometryIntegritySettings(tolerance: 'float') |
| `GroupKey` | constant/type alias | `NewType instance` | NewType creates simple unique types with almost zero runtime overhead. |
| `GroupStatus` | enum | `COMPLETED='completed'; FAILED='failed'; NOT_APPLICABLE='not_applicable'; SKIPPED='skipped'` | Documented in the corresponding feature/shared section. |
| `InwardRecessEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `InwardRecessSettings` | dataclass/contract | `(maximum_length: 'float', tolerance: 'float') -> None` | InwardRecessSettings(maximum_length: 'float', tolerance: 'float') |
| `KitchenDiningEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `KitchenDiningSettings` | dataclass/contract | `(minimum_shared_boundary: 'float', maximum_distance: 'float', tolerance: 'float') -> None` | KitchenDiningSettings(minimum_shared_boundary: 'float', maximum_distance: 'float', tolerance: 'float') |
| `LivingRoomBalanceEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `LivingRoomBalanceSettings` | dataclass/contract | `(maximum_excess_ratio: 'float') -> None` | LivingRoomBalanceSettings(maximum_excess_ratio: 'float') |
| `RoomAreaAggregation` | enum | `MIN='min'; AVERAGE='average'; MAX='max'; TOTAL='total'` | Controls how multiple rooms of one type are reduced to one area for a relation rule. |
| `RoomSizeConsistencyEvaluator` | class/interface/registry | `()` | Evaluates configurable inter-type area ratios and same-type area spread. |
| `RoomSizeConsistencySettings` | dataclass/contract | `(relation_rules: 'tuple[RoomSizeRelationRule, ...]' = (), consistency_rules: 'tuple[RoomTypeConsistencyRule, ...]' = (), default_full_penalty_ratio_delta: 'float' = 0.5) -> None` | Settings container; requires at least one relation or consistency rule. |
| `RoomSizeRelationRule` | dataclass/contract | `(reference_type: 'RoomType', compared_type: 'RoomType', min_ratio: 'float | None' = None, max_ratio: 'float | None' = None, reference_aggregation: 'RoomAreaAggregation' = MAX, compared_aggregation: 'RoomAreaAggregation' = MAX, weight: 'float' = 1.0, full_penalty_ratio_delta: 'float | None' = None) -> None` | Configures preferred `compared_area / reference_area` bounds. |
| `RoomTypeConsistencyRule` | dataclass/contract | `(room_type: 'RoomType', maximum_spread_ratio: 'float', weight: 'float' = 1.0, full_penalty_ratio_delta: 'float | None' = None) -> None` | Configures preferred same-type area spread, `largest / smallest - 1`. |
| `RequiredAdjacencyEvaluator` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `RequiredAdjacencySettings` | dataclass/contract | `(minimum_shared_boundary: 'float', tolerance: 'float') -> None` | RequiredAdjacencySettings(minimum_shared_boundary: 'float', tolerance: 'float') |
| `ScoreFinding` | dataclass/contract | `(code: 'str', message: 'str', severity: 'FindingSeverity' = <FindingSeverity.INFO: 'info'>, subject_ids: 'tuple[str, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = ()) -> None` | ScoreFinding(code: 'str', message: 'str', severity: 'FindingSeverity' = <FindingSeverity.INFO: 'info'>, subject_ids: 'tuple[str, ...]' = (), metrics: 'tuple[ScoreMetric, ...]' = ()) |
| `ScoreMetric` | dataclass/contract | `(name: 'str', value: 'float', unit: 'str \| None' = None) -> None` | ScoreMetric(name: 'str', value: 'float', unit: 'str \| None' = None) |
| `ScoringConfigurationError` | exception | `constructor has no separately inspectable signature` | Raised when a scoring profile or registry is inconsistent. |
| `ScoringContext` | dataclass/contract | `(mode: 'ExecutionMode', floor_width: 'float', floor_length: 'float', floor_points: 'tuple[tuple[float, float], ...]', floor_polygon: 'Polygon', rooms: 'tuple[NormalizedRoom, ...]', room_specs: 'tuple[NormalizedRoomSpec, ...]', relations: 'tuple[NormalizedRelation, ...]', rooms_by_id: 'Mapping[str, NormalizedRoom]', specs_by_id: 'Mapping[str, NormalizedRoomSpec]', identity_redirects: 'Mapping[str, str]', room_union: 'BaseGeometry \| None', geometry_build_error: 'str \| None', shared_boundary_lengths: 'Mapping[tuple[str, str], float]') -> None` | ScoringContext(mode: 'ExecutionMode', floor_width: 'float', floor_length: 'float', floor_points: 'tuple[tuple[float, float], ...]', floor_polygon: 'Polygon', rooms: 'tuple[NormalizedRoom, ...]', room_specs: 'tuple[NormalizedRoomSpec, ...]', relations: 'tuple[NormalizedRelation, ...]', rooms_by_id: 'Mapping[str, NormalizedRoom]', specs_by_id: 'Mapping[str, NormalizedRoomSpec]', identity_redirects: 'Mapping[str, str]', room_union: 'BaseGeometry \| None', geometry_build_error: 'str \| None', shared_boundary_lengths: 'Mapping[tuple[str, str], float]') |
| `ScoringGroupResult` | dataclass/contract | `(group_key: 'GroupKey', status: 'GroupStatus', normalized_maximum: 'float', raw_score: 'float \| None', contribution: 'float') -> None` | ScoringGroupResult(group_key: 'GroupKey', status: 'GroupStatus', normalized_maximum: 'float', raw_score: 'float \| None', contribution: 'float') |
| `ScoringGroupRule` | dataclass/contract | `(key: 'GroupKey', enabled: 'bool' = True, order: 'int' = 0, weight: 'float' = 1.0) -> None` | Configuration for one scoring group. |
| `ScoringInputError` | exception | `constructor has no separately inspectable signature` | Raised when floor-plan or specification data is structurally broken. |
| `ScoringProfile` | dataclass/contract | `(groups: 'tuple[ScoringGroupRule, ...]', evaluators: 'tuple[EvaluatorRule, ...]') -> None` | Reusable configuration controlling how a floor plan is scored. |
| `create_default_config` | function | `create_default_config() -> 'FloorPlanScoringConfig'` | Documented in the corresponding feature/shared section. |
| `create_default_profile` | function | `create_default_profile() -> 'ScoringProfile'` | Compatibility alias for create_default_config(). |
| `create_default_registry` | function | `create_default_registry() -> 'EvaluatorRegistry'` | Documented in the corresponding feature/shared section. |
| `score_floor_plan` | function | `score_floor_plan(scoring_input: 'FloorPlanScoringInput', *, registry: 'EvaluatorRegistry \| None' = None, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FloorPlanScoringExecution'` | Score one completed floor plan without application-layer orchestration. |


## Documentation Verification Record

Verified against the current supplied source and packaging metadata:

- [x] `pyproject.toml`
- [x] `MANIFEST.in`
- [x] package-root exports
- [x] every feature-root `__init__.py` / `__all__`
- [x] every public `api.py`
- [x] public input/output/config contracts
- [x] `fpg_core.domain` exports
- [x] enums and typed IDs
- [x] validation rules
- [x] exceptions and returned statuses
- [x] defaults/profiles
- [x] extension registries/interfaces
- [ ] relevant automated tests — test files were not included in the supplied 2026-08-15 source/docs archive
- [x] mutation/copy behavior from the supplied implementation
- [x] execution-mode differences
- [x] examples/import paths
- [x] compatibility aliases
- [x] public API coverage audit
- [x] Python source syntax compilation (`compileall`)

Known unverified areas:

- Automated behavior of the updated features was not re-run because the relevant test suite was not included in the supplied archive.
- OR-Tools-backed runtime execution was not performed in this sandbox; the supplied implementation, contracts, validators, registrations, defaults, and syntax were verified statically.

Documentation updated and source-verified on 2026-08-15 against the supplied source archive. No repository commit hash was supplied with this update. The coverage inventory accounts for all 340 names exported by `fpg_core`, `fpg_core.domain`, and the ten feature roots.
