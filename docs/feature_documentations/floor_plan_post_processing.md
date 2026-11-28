# Floor Plan Post-Processing

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Implementation rationale is maintained in the internal architecture and feature notes. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Applies an ordered profile of geometry transformations to one solved floor plan, with
validation and rollback around every processor. Use it when a consumer needs the
built-in initial-generation cleanup or an explicitly registered custom processor
profile.

## Public API

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

## Inputs

`PostProcessingRequest(floor_plan, config, specification=None, solver_config=None)`. The plan boundary
and room polygons must be canonical, rooms must have unique IDs and names, standard
rooms may not overlap or leave the floor, parent/redirect/opening references must be
valid, and identity redirects must be acyclic. The specification is optional context
for processors. `solver_config` is the `FloorPlanSolverConfig` used for the final
successful solve. Opportunistic repair skips when either it or the specification
is missing. Geometry-changing grid snapping rejects changes it cannot protect.

## Configuration

- `FloorPlanPostProcessingConfig(name, processors, numeric=NumericPolicy(),
  reject_existing_openings=True)`. `PostProcessingProfile` is a compatibility alias.
- `NumericPolicy(tolerance=1e-6, grid_size=1.0)` requires positive values. Tolerance
  controls geometric comparisons/validation; grid size is the default snap interval.
- Each `ProcessorUse(processor_id, config, required=False,
  validate_after=False)` must resolve in the registry, use the processor's exact
  config type, appear once, and follow prerequisites. A required failure terminates
  the profile; `validate_after` checks the mutated plan immediately.
- The built-in profile uses `remove_placeholder_rooms`, `grid_snap`,
  `wall_extension`, `hallway_merge`, and `rectilinear_simplification` in that order.
  It rejects plans that already contain
  openings; `remove_placeholder_rooms` and `grid_snap` are required and validated.
- `PlaceholderRemovalConfig` and `RectilinearSimplificationConfig` have no tuning.
  The placeholder-dependent veranda processor is no longer in the default registry.
- `HallwayMergeConfig(minimum_shared_wall=10)` sets the minimum shared project-unit
  wall for merging hallway rooms. `GridSnapConfig(grid_size=None)` uses the profile's
  numeric grid when `None`, otherwise a positive per-processor grid size.
- `WallExtensionConfig` uses `WallExtensionRule(room_type, max_distance)` for eligible
  room types. Defaults are veranda 40, living room 20, kitchen 10, hallway 2 and
  bedroom 10 units. Directional `ExteriorStepPolicy` defaults are left/right
  `(10, 10, 2)`, back `(8, 8, 3)` and front `(5, 5, 4)`: minimum step depth,
  minimum wall segment length and preferred maximum step count. Recess depth/width
  defaults to 1 and nesting/branching to 1; minimum pocket area is 1 square unit.
  Contact and residual edge minimums are 5 units; ordinary extension width and depth
  are 5, hallway width and depth 2 and 1. Area and width excess default to 0.05 of
  the original specification maximum; zero enforces the original limit. Repair is
  bounded by 20 iterations and 1000 candidate evaluations.

Repair uses detected pockets, unacceptable recesses and localized step targets.
It tests rectangular additions one room at a time against the entire target, floor,
room size, shape and active hard constraints, then remeasures the footprint. It
accepts only improvements that do not worsen another measured problem category.
Shape and hard-constraint checks are conservative: unsupported hard constraints,
changed hallway geometry under hallway limits, changed bathroom/hallway contact,
and altered attached-bathroom pair qualifications cause rejection. Fully shared
walls use directional visible-wall segments and a combined uncovered-length
allowance. Front wall setback uses the minimum Y of all standard room geometries
and rechecks every applicable room against the new reference edge. Aspect ratio
uses the room bounding dimensions. Exposure uses outward
silhouettes, with distant rooms blocking their projections; disconnected physical
walls do not form one continuous segment. The implementation can therefore leave
repairable layouts unchanged. Candidate widths use wall and target vertices and a
small set of grid-aligned cuts, so the search is not exhaustive. A grid snap that
changes the floor boundary, removes room area, lacks solver/specification context,
or cannot prove applicable protections is rolled back. Because the built-in snap is
required, its failure stops the pipeline.

## Recommended values

Use `INITIAL_GENERATION_PROFILE` for the solver's initial output. Its numeric defaults
(`1e-6`, `1.0`) are the implementation-backed baseline. Custom processor tuning is
extension-specific; do not alter ordering without satisfying declared prerequisites.

## Outputs

`PostProcessingExecution` is
`FeatureExecution[PostProcessingResult, PostProcessingDetails]`. Result has
`SUCCESS`/`FAILED`, the current/restored `floor_plan`, and optional
`ProcessingFailure(code, message, processor_id)`. DEBUG details contain ordered
`ProcessorExecution`s with status, duration milliseconds, rollback flag, outcome,
affected IDs, redirects, metrics, or failure.

## Errors / failure conditions

Expected request, configuration, validation, and processor failures are normally
captured in a `FAILED` result. Required failures stop; optional failures are rolled
back and later independent processors may run. A failed prerequisite causes a skip.
Severe rollback failure also returns failure. A non-`ExecutionMode` mode raises
`TypeError`. Exception classes used by custom processors are importable from
`fpg_core.floor_plan_post_processing.exceptions`.

## Usage example

```python
from fpg_core.floor_plan_post_processing import (
    INITIAL_GENERATION_PROFILE,
    PipelineStatus,
    PostProcessingRequest,
    post_process_floor_plan,
)
from fpg_core.floor_plan_solver import INITIAL_GENERATION_PROFILE as SOLVER_PROFILE

execution = post_process_floor_plan(
    PostProcessingRequest(
        floor_plan=example_floor_plan,
        config=INITIAL_GENERATION_PROFILE,
        specification=example_specification,
        solver_config=SOLVER_PROFILE,
    )
)
if execution.result.status is not PipelineStatus.SUCCESS:
    raise RuntimeError(execution.result.failure)
processed_plan = execution.result.floor_plan
```

For an actual solved plan, replace `SOLVER_PROFILE` with the effective configuration
used by its final successful solve or refinement.

## Important behavioral notes

The supplied `FloorPlan` is the mutable working object; successful changes are
observable through the original object. A failing processor restores its snapshot.
Run geometry-changing profiles before openings unless the profile explicitly permits
and preserves existing openings.


## Warnings / diagnostics

Post-processing uses structured processor outcomes rather than a separate warning list. A processor may report `CHANGED`, `NO_CHANGE`, `NOT_APPLICABLE`, `FAILED`, or `SKIPPED`; pipeline success/failure is reported separately by `PipelineStatus`. In `DEBUG`, `PostProcessingDetails.executions` records each processor's status, duration, rollback flag, outcome, and optional failure. Wall-extension outcomes include typed `RepairDiagnostic` records with problem/candidate bounds and rejection reasons. `PRODUCTION` omits that execution trace.

## Public Export Inventory

### `fpg_core.floor_plan_post_processing` exports (32)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `ExteriorStepPolicy` | dataclass/contract | `direction, minimum_depth, minimum_segment_length, preferred_max_steps` | Directional exterior consistency thresholds. |
| `RepairDiagnostic` | dataclass/contract | `kind, room_id, bounds, detail, geometry, associated_room_ids, shared_walls` | Debug repair finding or candidate. |
| `ConfigurationError` | exception | `constructor has no separately inspectable signature` | Documented in the corresponding feature/shared section. |
| `FloorPlanPostProcessingConfig` | dataclass/contract | `(name: 'str', processors: 'tuple[ProcessorUse, ...]', numeric: 'NumericPolicy' = <factory>, reject_existing_openings: 'bool' = True) -> None` | Complete reusable configuration for floor-plan post-processing. |
| `FloorPlanProcessor` | class/interface/registry | `()` | Documented in the corresponding feature/shared section. |
| `GridSnapConfig` | dataclass/contract | `(grid_size: 'float \| None' = None) -> None` | GridSnapConfig(grid_size: 'float \| None' = None) |
| `HallwayMergeConfig` | dataclass/contract | `(minimum_shared_wall: 'float' = 10.0) -> None` | HallwayMergeConfig(minimum_shared_wall: 'float' = 10.0) |
| `INITIAL_GENERATION_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Complete reusable configuration for floor-plan post-processing. |
| `NumericPolicy` | dataclass/contract | `(tolerance: 'float' = 1e-06, grid_size: 'float' = 1.0) -> None` | Numerical tolerances and grid settings used by the pipeline. |
| `PipelineStatus` | enum | `SUCCESS='success'; FAILED='failed'` | Documented in the corresponding feature/shared section. |
| `PlaceholderRemovalConfig` | dataclass/contract | `() -> None` | PlaceholderRemovalConfig() |
| `PostProcessingContext` | dataclass/contract | `(mode: 'ExecutionMode', specification: 'FloorPlanGenerationSpec \| None', floor_boundary: 'Polygon', numeric: 'NumericPolicy', profile_name: 'str', solver_config: 'FloorPlanSolverConfig \| None' = None) -> None` | Processor execution context. |
| `PostProcessingDetails` | dataclass/contract | `(executions: 'tuple[ProcessorExecution, ...]') -> None` | PostProcessingDetails(executions: 'tuple[ProcessorExecution, ...]') |
| `PostProcessingError` | exception | `constructor has no separately inspectable signature` | Base error for the standalone post-processing component. |
| `PostProcessingExecution` | constant/type alias | `_GenericAlias instance` | Documented in the corresponding feature/shared section. |
| `PostProcessingProfile` | dataclass/contract | `(name: 'str', processors: 'tuple[ProcessorUse, ...]', numeric: 'NumericPolicy' = <factory>, reject_existing_openings: 'bool' = True) -> None` | Complete reusable configuration for floor-plan post-processing. |
| `PostProcessingRequest` | dataclass/contract | `(floor_plan: 'FloorPlan', config: 'FloorPlanPostProcessingConfig', specification: 'FloorPlanGenerationSpec \| None' = None, solver_config: 'FloorPlanSolverConfig \| None' = None) -> None` | Processing input for one post-processing execution. |
| `PostProcessingResult` | dataclass/contract | `(status: 'PipelineStatus', floor_plan: 'FloorPlan', failure: 'ProcessingFailure \| None' = None) -> None` | PostProcessingResult(status: 'PipelineStatus', floor_plan: 'FloorPlan', failure: 'ProcessingFailure \| None' = None) |
| `ProcessingFailure` | dataclass/contract | `(code: 'str', message: 'str', processor_id: 'str \| None' = None) -> None` | ProcessingFailure(code: 'str', message: 'str', processor_id: 'str \| None' = None) |
| `ProcessorError` | exception | `constructor has no separately inspectable signature` | Documented in the corresponding feature/shared section. |
| `ProcessorExecution` | dataclass/contract | `(processor_id: 'str', status: 'ProcessorStatus', duration_ms: 'float', rolled_back: 'bool' = False, outcome: 'ProcessorOutcome \| None' = None, failure: 'ProcessingFailure \| None' = None) -> None` | ProcessorExecution(processor_id: 'str', status: 'ProcessorStatus', duration_ms: 'float', rolled_back: 'bool' = False, outcome: 'ProcessorOutcome \| None' = None, failure: 'ProcessingFailure \| None' = None) |
| `ProcessorOutcome` | dataclass/contract | `status, message, affected_room_ids, identity_redirects, metrics, diagnostics` | See feature contract above. |
| `ProcessorRegistry` | class/interface/registry | `(processors: 'Iterable[FloorPlanProcessor]' = ()) -> 'None'` | Documented in the corresponding feature/shared section. |
| `ProcessorStatus` | enum | `CHANGED='changed'; NO_CHANGE='no_change'; NOT_APPLICABLE='not_applicable'; FAILED='failed'; SKIPPED='skipped'` | Documented in the corresponding feature/shared section. |
| `ProcessorUse` | dataclass/contract | `(processor_id: 'str', config: 'object', required: 'bool' = False, validate_after: 'bool' = False) -> None` | Configuration for one processor in the ordered pipeline. |
| `RectilinearSimplificationConfig` | dataclass/contract | `() -> None` | RectilinearSimplificationConfig() |
| `RollbackError` | exception | `constructor has no separately inspectable signature` | Documented in the corresponding feature/shared section. |
| `ValidationError` | exception | `constructor has no separately inspectable signature` | Documented in the corresponding feature/shared section. |
| `WallExtensionConfig` | dataclass/contract | `rules, exterior_steps, max_recess_ratio, max_recess_levels, min_pocket_area, min_contact_length, min_residual_edge, min_extension_width, min_extension_depth, hallway_min_extension_width, hallway_min_extension_depth, max_area_excess, max_width_excess, max_iterations, max_candidate_evaluations, transformation_version` | Defaults and semantics are described in Configuration above. |
| `WallExtensionRule` | dataclass/contract | `room_type, max_distance` | See feature contract above. |
| `create_default_registry` | function | `create_default_registry() -> 'ProcessorRegistry'` | Documented in the corresponding feature/shared section. |
| `post_process_floor_plan` | function | `post_process_floor_plan(request: 'PostProcessingRequest', *, registry: 'ProcessorRegistry \| None' = None, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'PostProcessingExecution'` | Run one configured post-processing pipeline on a typed floor plan. |

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
