# fpg-core Consumer API Guide

This is the package-wide consumer contract guide. It contains the conventions and shared types that apply across features. Exact feature-specific inputs, outputs, configuration, errors, warnings/diagnostics, and examples live under [`feature_documentations/`](feature_documentations/README.md).

> A consumer should not need to inspect `src/fpg_core` to determine how to call a supported public feature. Internal feature `README.md` files are development notes, not consumer API documentation.
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
## Feature Documentation Index

| Feature | Consumer document | Preferred operation |
|---|---|---|
| Buildable Land | [buildable_land.md](feature_documentations/buildable_land.md) | `calculate_buildable_land` |
| Usable Land | [usable_land.md](feature_documentations/usable_land.md) | `find_usable_land` |
| Floor Plan Preprocessing | [floor_plan_preprocessing.md](feature_documentations/floor_plan_preprocessing.md) | `prepare_generation_input` |
| Candidate Search | [candidate_search.md](feature_documentations/candidate_search.md) | `search_candidates` |
| Candidate Circulation | [candidate_circulation.md](feature_documentations/candidate_circulation.md) | `refine_candidate_circulation` |
| Candidate Scoring | [candidate_scoring.md](feature_documentations/candidate_scoring.md) | `evaluate_candidate` |
| Floor Plan Solver | [floor_plan_solver.md](feature_documentations/floor_plan_solver.md) | `generate_floor_plan` |
| Floor Plan Post-Processing | [floor_plan_post_processing.md](feature_documentations/floor_plan_post_processing.md) | `post_process_floor_plan` |
| Floor Plan Openings | [floor_plan_openings.md](feature_documentations/floor_plan_openings.md) | `generate_openings` |
| Floor Plan Scoring | [floor_plan_scoring.md](feature_documentations/floor_plan_scoring.md) | `score_floor_plan` |
## Reusable Example Fixtures

Several feature documents reuse these fully constructed public contracts. Copy
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
## API Versioning and Compatibility

`fpg-core` uses the package version as the public API version. Features do not receive independent API version numbers.

The repository is currently pre-1.0. Until `1.0.0`:

- PATCH releases (`0.x.y`) must not intentionally break documented public APIs.
- A MINOR release (`0.x.0`) may contain a deliberate breaking public API change, but the change must be recorded in `CHANGELOG.md`, the affected consumer documentation must be updated in the same change, and migration guidance must be provided.
- Internal implementation changes that do not alter documented public behavior do not require consumer migration notes.
- Deprecations should identify the replacement and the release in which removal may occur.

After `1.0.0`, use normal Semantic Versioning: MAJOR for breaking public API changes, MINOR for backward-compatible capabilities, and PATCH for backward-compatible fixes.

### Current metadata state

The checked-in `pyproject.toml` declares distribution version `0.1.0`, while `CHANGELOG.md` contains a `0.2.0` release section plus additional `Unreleased` changes and the source-checkout fallback in `fpg_core.__version__` is `0.2.0`. Consumer documentation in this directory therefore targets the **current source tree**, not a claim that all of these contracts are already published under the `0.1.0` distribution metadata. Before publishing a package release, synchronize the distribution version, changelog, and documentation target.

## Documentation Scope

The canonical consumer documentation set is:

- `docs/API_GUIDE.md` — package-wide conventions, shared contracts, compatibility, errors/statuses, and integration guidance.
- `docs/feature_documentations/<feature>.md` — one complete consumer document per public feature.

`src/fpg_core/<feature>/README.md` files are intentionally excluded from the consumer contract. They may contain algorithm design, maintenance notes, internal decisions, and R&D context.
