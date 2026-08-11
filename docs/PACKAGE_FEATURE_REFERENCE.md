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
    route_rules=(example_route_rule,),
    always_traversable_room_types=(RoomType.HALLWAY,),
)
execution = refine_candidate_circulation(
    CandidateCirculationInput(example_candidate, config)
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
diagnostic contracts; `FloorPlanSolverConfig` (with compatibility alias
`GenerationProfile`), `HardConstraintUse`, `SoftConstraintUse`, `SolverConfig`,
`PreparationConfig`, `SeedPolicy`, `SeedSource`, `DefaultProfileSettings`,
`ProfileCatalog`, and `ConstraintRegistry`; built-ins `INITIAL_GENERATION_PROFILE`,
`REFINEMENT_A_PROFILE`, `REFINEMENT_B_PROFILE`, `DEFAULT_PROFILES`; and
`build_default_profiles()`.

### Inputs

- `FloorPlanSolveRequest(specification, config, candidate_hints=(),
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
- `FloorPlanSolverConfig` names unique hard/soft constraint uses. Soft weights are
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

Exact common hard-constraint uses in all three profiles are:

| Key | Exact built-in settings |
|---|---|
| `aspect_ratio` | min `0.60`, max `1.80`, hallway excluded; garage override `0.45..0.70`; veranda override `1.20..3.50` |
| `room_relations` | `minimum_overlap=10` |
| `attached_bathroom_pairing` | minimum shared wall `10`; attached-bathroom type to bedroom type |
| `minimum_coverage` | `ratio=0.6` |
| `hallway_connectivity` | minimum overlap `10`; hallway type anchored to living-room type |
| `hallway_dimensions` | hallway width `8..10` |
| `front_anchor` | veranda, living room, bedroom, garage |
| `back_exposure` | hallway and kitchen; minimum exposure `10.0` |
| `garage_placement` | garage type |
| `boundary_placement` | veranda on `front` with offset `0.0` |

| Profile | Exact soft uses (`key: weight`; settings) | Runtime/seed |
|---|---|---|
| `initial_generation` | `room_relations:40` (overlap 10), `floor_cluster_position:1` (horizontal 1/front 2), `dead_space:3`, `bathroom_depth:2`, `kitchen_back_exposure:10` (exposure 10) | 5 s; candidate hints optional; no movement/size bounds |
| `refinement_a` | `room_relations:50`, `seed_stability:20` (position 2/size 1), `floor_cluster_position:1` (horizontal 1/front 2), `dead_space:4`, `bathroom_depth:3`, `kitchen_back_exposure:10` | 2 s; existing plan required; position/size tolerance 10 |
| `refinement_b` | `room_relations:60`, `seed_stability:35` (position 2/size 2), `dead_space:6`, `bathroom_depth:4`, `kitchen_back_exposure:10` | 2 s; existing plan required; position/size tolerance 5 |

All use `coordinate_scale=1`; otherwise the `SolverConfig` defaults apply: workers
`0`, random seed `None`, logging off, no relative-gap limit, and presolve enabled.

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

`OpeningGenerationRequest(floor_plan, config)` requires finite canonical rectilinear
floor/room polygons; positive area; unique room IDs; standard rooms inside the floor
without area overlap; and no existing openings. Adjacent/shared and
exterior walls must be long enough for configured openings and clearances.

### Configuration

- `FloorPlanOpeningsConfig(name, enabled_features=('interior_doors',
  'exterior_doors', 'windows'), enabled_constraints=('shared_placement',
  'room_door_limits'), geometry=GeometryConfig(), dimensions=DimensionConfig(),
  policy=FeaturePolicy(), objective=ObjectiveConfig(), solver=SolverConfig())`.
  `OpeningGenerationProfile` is a compatibility alias. IDs must be
  unique; `shared_placement` is mandatory.
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
    floor_plan=example_floor_plan,
    config=DEFAULT_OPENING_PROFILE,
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

`FloorPlanScoringInput(floor_plan, specification, config)` requires a typed plan and
the specification that defines room IDs, size ranges, and relations. Plan rooms need
valid finite polygon geometry and IDs consistent with specification or valid identity
redirects.

### Configuration

- `FloorPlanScoringConfig(groups, evaluators)` requires at least one group, unique keys,
  finite positive weights, and exactly one enabled `critical` gate that executes no
  later than other groups. Every enabled group needs an enabled evaluator.
  `ScoringProfile` is a compatibility alias.
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
        floor_plan=example_floor_plan,
        specification=example_specification,
        config=create_default_profile(),
    ),
    mode=ExecutionMode.DEBUG,
)
score = execution.result.total_score
```

### Important behavioral notes

Scoring never mutates the plan. Openings do not affect the current built-in scores.
In PRODUCTION, result findings remain consumer-safe while evaluator metrics and
visualization payloads are omitted with `details=None`.

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
importance_weight)`, `GridRoutingCostProfile(empty_node_cost,
traversable_hint_node_cost, turn_cost, perimeter_bias_max_cost)`, and
`HallwayClassification(room_id, hint_index, traffic_class)`. Destination selection
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
| Candidate Circulation | refined `CandidateMap`, classifications | Floor Plan Solver hints / later scoring | removed hallway points are absent from the returned map; consumers must keep room/spec identities consistent |
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
| Floor Plan Solver | `DEFAULT_PROFILES`; three named constants | `initial_generation`: 5 s, optional candidate hints; `refinement_a`: 2 s, required existing plan, position/size tolerance 10; `refinement_b`: 2 s, required existing plan, tolerances 5. All use coordinate scale 1 and the hard rules/soft weights described in the solver section |
| Post-Processing | `INITIAL_GENERATION_PROFILE` | order: veranda adjustment, wall extension, required placeholder removal+validation, hallway merge, required grid snap+validation, rectilinear simplification; tolerance `1e-6`, grid 1, rejects existing openings |
| Openings | `DEFAULT_OPENING_CONFIG` / `DEFAULT_OPENING_PROFILE` | name `default_openings`; features `interior_doors`, `exterior_doors`, `windows`; constraints `shared_placement`, `room_door_limits`; 10 s, one worker, seed 0 |
| Floor Plan Scoring | `DEFAULT_FLOOR_PLAN_SCORING_CONFIG` / `DEFAULT_SCORING_PROFILE` | critical group: geometry integrity, required adjacency, enclosed voids, inward recess, each threshold 100; functional group: living balance, bedroom quality, kitchen/dining proximity |

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
| `CirculationRouteRule` | dataclass/contract | `(id: 'int', name: 'str', source_room_type: 'RoomType', destination_room_type: 'RoomType', destination_selection: 'DestinationSelection', traffic_class: 'CirculationTrafficClass', allowed_transit_room_types: 'tuple[RoomType, ...]', importance_weight: 'float') -> None` | Shared typed request for room-type circulation routing. |
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

### `fpg_core.candidate_circulation` exports (22)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `CandidateCirculationConfig` | dataclass/contract | `(costs: 'RoutingCostProfile', route_rules: 'tuple[CirculationRouteRule, ...]', always_traversable_room_types: 'tuple[RoomType, ...]', max_routing_passes: 'int' = 3) -> None` | Reusable routing policy; request-specific grid comes from CandidateMap. |
| `CandidateCirculationDetails` | dataclass/contract | `(circulation_efficiency_score: 'float', routing_pass_count: 'int', grid_node_count: 'int', passes: 'tuple[RoutingPassDetails, ...]', final_hallway_traffic: 'tuple[HallwayTrafficDetails, ...]', removed_hallway_points: 'tuple[RemovedHallwayPointDetails, ...]') -> None` | DEBUG-only route efficiency, hallway traffic, and removal data. |
| `CandidateCirculationError` | exception | `constructor has no separately inspectable signature` | Base exception for candidate circulation failures. |
| `CandidateCirculationInput` | dataclass/contract | `(candidate: 'CandidateMap', config: 'CandidateCirculationConfig') -> None` | Candidate map and reusable circulation policy. |
| `CandidateCirculationInputError` | exception | `constructor has no separately inspectable signature` | Raised when the circulation input or configuration is invalid. |
| `CandidateCirculationResult` | dataclass/contract | `(candidate: 'CandidateMap', hallway_classifications: 'tuple[HallwayClassification, ...]' = ()) -> None` | Production result with cleaned candidate and hallway traffic tags. |
| `CirculationPathDetails` | dataclass/contract | `(rule_id: 'int', rule_name: 'str', traffic_class: 'CirculationTrafficClass', destination_selection: 'DestinationSelection', allowed_transit_room_types: 'tuple[RoomType, ...]', importance_weight: 'float', source_point_key: 'str', source_room_id: 'str', source_room_type: 'RoomType', destination_point_key: 'str', destination_room_id: 'str', destination_room_type: 'RoomType', nodes: 'tuple[CirculationGridNode, ...]', step_count: 'int', manhattan_step_count: 'int', detour_step_count: 'int', turn_count: 'int', manhattan_reference_cost: 'float', costs: 'RouteCostBreakdown', path_efficiency_score: 'float') -> None` | DEBUG data for one expanded and resolved route. |
| `CirculationTrafficClass` | enum | `PUBLIC='public'; PRIVATE='private'` | Architectural traffic carried by a configured route. |
| `CirculationPathNotFoundError` | exception | `constructor has no separately inspectable signature` | Raised when a configured route cannot be resolved on the grid. |
| `CirculationRouteRule` | dataclass/contract | `(id: 'int', name: 'str', source_room_type: 'RoomType', destination_room_type: 'RoomType', destination_selection: 'DestinationSelection', traffic_class: 'CirculationTrafficClass', allowed_transit_room_types: 'tuple[RoomType, ...]', importance_weight: 'float') -> None` | Shared typed request for room-type circulation routing. |
| `DestinationSelection` | enum | `ALL_MATCHING='all_matching'; LOWEST_COST_MATCH='lowest_cost_match'` | Determines which matching destinations a route rule selects. |
| `GridAlignmentError` | exception | `constructor has no separately inspectable signature` | Raised when a hint point does not align with the configured grid. |
| `GridNode` | dataclass/contract | `(x_index: 'int', y_index: 'int', x: 'float', y: 'float') -> None` | One grid node used by an orthogonal circulation path. |
| `HallwayClassification` | dataclass/contract | `(room_id: 'RoomId', hint_index: 'int', traffic_class: 'HallwayTrafficClass') -> None` | Production-safe traffic classification for one hallway hint point. |
| `HallwayTrafficClass` | enum | `PUBLIC='public'; PRIVATE='private'; MIXED='mixed'; UNCLASSIFIED='unclassified'; UNUSED='unused'` | Traffic role assigned to one hallway hint point. |
| `HallwayTrafficDetails` | dataclass/contract | `(point_key: 'str', room_id: 'str', hint_index: 'int', x: 'float', y: 'float', public_route_count: 'int', private_route_count: 'int', public_importance_weight: 'float', private_importance_weight: 'float', traffic_class: 'HallwayTrafficClass', removed: 'bool') -> None` | Traffic totals and final role for one hallway hint point. |
| `RemovedHallwayPointDetails` | dataclass/contract | `(point_key: 'str', room_id: 'str', hint_index: 'int', x: 'float', y: 'float') -> None` | Identity and position of one hallway hint removed from the candidate. |
| `RouteCostBreakdown` | dataclass/contract | `(movement_cost: 'float', perimeter_bias_cost: 'float', turn_cost: 'float', traffic_conflict_cost: 'float', total_cost: 'float') -> None` | Cost components accumulated by one resolved circulation route. |
| `RoutingCostProfile` | dataclass/contract | `(empty_node_cost: 'float', traversable_hint_node_cost: 'float', turn_cost: 'float', perimeter_bias_max_cost: 'float', traffic_conflict_cost: 'float') -> None` | Routing costs including the multi-pass hallway conflict penalty. |
| `RoutingPassDetails` | dataclass/contract | `(pass_number: 'int', classifications_changed_from_previous: 'bool', paths: 'tuple[CirculationPathDetails, ...]', hallway_traffic: 'tuple[HallwayTrafficDetails, ...]') -> None` | DEBUG snapshot of one routing and hallway-classification pass. |
| `TrafficClass` | enum | `PUBLIC='public'; PRIVATE='private'` | Architectural traffic carried by a configured route. |
| `refine_candidate_circulation` | function | `refine_candidate_circulation(circulation_input: 'CandidateCirculationInput', *, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]'` | Resolve routes, classify hallways, and remove unused hallway hints. |

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
| `DefaultProfileSettings` | dataclass/contract | `(coordinate_scale: 'int' = 1, minimum_coverage_ratio: 'float' = 0.6, minimum_adjacency_overlap: 'float' = 10, attached_bathroom_minimum_shared_wall: 'float' = 10.0, initial_max_time_seconds: 'float' = 5.0, refinement_max_time_seconds: 'float' = 2.0, refinement_position_tolerance: 'float' = 10, refinement_size_tolerance: 'float' = 10) -> None` | Central tuning values used to construct the built-in profiles. |
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
| `FeaturePolicy` | dataclass/contract | `(allowed_room_pairs: 'tuple[tuple[RoomType, RoomType], ...]' = ((<RoomType.BEDROOM: 'bedroom'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.KITCHEN: 'kitchen'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.BATHROOM: 'bathroom'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.BEDROOM: 'bedroom'>, <RoomType.ATTACHED_BATHROOM: 'attached_bathroom'>), (<RoomType.VERANDA: 'veranda'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.GARAGE: 'garage'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.GARAGE: 'garage'>, <RoomType.HALLWAY: 'hallway'>), (<RoomType.DINING_ROOM: 'dining_room'>, <RoomType.LIVING_ROOM: 'living_room'>)), room_door_caps: 'tuple[tuple[RoomType, int], ...]' = ((<RoomType.BEDROOM: 'bedroom'>, 2), (<RoomType.BATHROOM: 'bathroom'>, 1), (<RoomType.LIVING_ROOM: 'living_room'>, 10), (<RoomType.HALLWAY: 'hallway'>, 10), (<RoomType.KITCHEN: 'kitchen'>, 1), (<RoomType.ATTACHED_BATHROOM: 'attached_bathroom'>, 1), (<RoomType.VERANDA: 'veranda'>, 1), (<RoomType.GARAGE: 'garage'>, 1), (<RoomType.DINING_ROOM: 'dining_room'>, 2)), secondary_room_priority: 'tuple[RoomType, ...]' = (<RoomType.KITCHEN: 'kitchen'>, <RoomType.HALLWAY: 'hallway'>), window_room_types: 'tuple[RoomType, ...]' = (<RoomType.BEDROOM: 'bedroom'>, <RoomType.LIVING_ROOM: 'living_room'>, <RoomType.KITCHEN: 'kitchen'>, <RoomType.DINING_ROOM: 'dining_room'>), main_side_priority: 'tuple[str, ...]' = ('south', 'east', 'north', 'west'), secondary_side_priority: 'tuple[str, ...]' = ('north', 'west', 'east', 'south'), window_side_priority: 'tuple[str, ...]' = ('east', 'north', 'south', 'west')) -> None` | FeaturePolicy(allowed_room_pairs: 'tuple[tuple[RoomType, RoomType], ...]' = ((<RoomType.BEDROOM: 'bedroom'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.KITCHEN: 'kitchen'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.BATHROOM: 'bathroom'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.BEDROOM: 'bedroom'>, <RoomType.ATTACHED_BATHROOM: 'attached_bathroom'>), (<RoomType.VERANDA: 'veranda'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.GARAGE: 'garage'>, <RoomType.LIVING_ROOM: 'living_room'>), (<RoomType.GARAGE: 'garage'>, <RoomType.HALLWAY: 'hallway'>), (<RoomType.DINING_ROOM: 'dining_room'>, <RoomType.LIVING_ROOM: 'living_room'>)), room_door_caps: 'tuple[tuple[RoomType, int], ...]' = ((<RoomType.BEDROOM: 'bedroom'>, 2), (<RoomType.BATHROOM: 'bathroom'>, 1), (<RoomType.LIVING_ROOM: 'living_room'>, 10), (<RoomType.HALLWAY: 'hallway'>, 10), (<RoomType.KITCHEN: 'kitchen'>, 1), (<RoomType.ATTACHED_BATHROOM: 'attached_bathroom'>, 1), (<RoomType.VERANDA: 'veranda'>, 1), (<RoomType.GARAGE: 'garage'>, 1), (<RoomType.DINING_ROOM: 'dining_room'>, 2)), secondary_room_priority: 'tuple[RoomType, ...]' = (<RoomType.KITCHEN: 'kitchen'>, <RoomType.HALLWAY: 'hallway'>), window_room_types: 'tuple[RoomType, ...]' = (<RoomType.BEDROOM: 'bedroom'>, <RoomType.LIVING_ROOM: 'living_room'>, <RoomType.KITCHEN: 'kitchen'>, <RoomType.DINING_ROOM: 'dining_room'>), main_side_priority: 'tuple[str, ...]' = ('south', 'east', 'north', 'west'), secondary_side_priority: 'tuple[str, ...]' = ('north', 'west', 'east', 'south'), window_side_priority: 'tuple[str, ...]' = ('east', 'north', 'south', 'west')) |
| `FloorPlanOpeningsConfig` | dataclass/contract | `(name: 'str', enabled_features: 'tuple[str, ...]' = ('interior_doors', 'exterior_doors', 'windows'), enabled_constraints: 'tuple[str, ...]' = ('shared_placement', 'room_door_limits'), geometry: 'GeometryConfig' = <factory>, dimensions: 'DimensionConfig' = <factory>, policy: 'FeaturePolicy' = <factory>, objective: 'ObjectiveConfig' = <factory>, solver: 'SolverConfig' = <factory>) -> None` | Reusable configuration controlling opening generation behavior. |
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
| `OpeningGenerationProfile` | dataclass/contract | `(name: 'str', enabled_features: 'tuple[str, ...]' = ('interior_doors', 'exterior_doors', 'windows'), enabled_constraints: 'tuple[str, ...]' = ('shared_placement', 'room_door_limits'), geometry: 'GeometryConfig' = <factory>, dimensions: 'DimensionConfig' = <factory>, policy: 'FeaturePolicy' = <factory>, objective: 'ObjectiveConfig' = <factory>, solver: 'SolverConfig' = <factory>) -> None` | Reusable configuration controlling opening generation behavior. |
| `OpeningFeatureRegistry` | class/interface/registry | `() -> 'None'` | Documented in the corresponding feature/shared section. |
| `create_default_registry` | function | `create_default_registry() -> 'OpeningFeatureRegistry'` | Documented in the corresponding feature/shared section. |
| `OpeningConfigurationError` | exception | `constructor has no separately inspectable signature` | Raised for programmer-facing configuration or registry errors. |
| `OpeningGenerationError` | exception | `constructor has no separately inspectable signature` | Base class for opening-generation failures. |

### `fpg_core.floor_plan_scoring` exports (58)

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

Verified against the current supplied source:

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
- [x] relevant tests
- [x] mutation/copy behavior
- [x] execution-mode differences
- [x] examples/import paths
- [x] compatibility aliases
- [x] public API coverage audit

Known unverified areas:

- None.

Documentation generated and verified on 2026-08-11 against commit
`b74f94b9e6a28700630b80c6861ce2fd805e2912`. The coverage inventory accounts for
all 330 names exported by `fpg_core`, `fpg_core.domain`, and the ten feature roots.
