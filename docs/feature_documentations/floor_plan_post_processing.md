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

`PostProcessingRequest(floor_plan, config, specification=None)`. The plan boundary
and room polygons must be canonical, rooms must have unique IDs and names, standard
rooms may not overlap or leave the floor, parent/redirect/opening references must be
valid, and identity redirects must be acyclic. The specification is optional context
for processors.

## Configuration

- `FloorPlanPostProcessingConfig(name, processors, numeric=NumericPolicy(),
  reject_existing_openings=True)`. `PostProcessingProfile` is a compatibility alias.
- `NumericPolicy(tolerance=1e-6, grid_size=1.0)` requires positive values. Tolerance
  controls geometric comparisons/validation; grid size is the default snap interval.
- Each `ProcessorUse(processor_id, config, required=False,
  validate_after=False)` must resolve in the registry, use the processor's exact
  config type, appear once, and follow prerequisites. A required failure terminates
  the profile; `validate_after` checks the mutated plan immediately.
- The built-in profile uses processor IDs `veranda_adjustment`, `wall_extension`,
  `remove_placeholder_rooms`, `hallway_merge`, `grid_snap`, and
  `rectilinear_simplification` in that order. It rejects plans that already contain
  openings; `remove_placeholder_rooms` and `grid_snap` are required and validated.
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

## Important behavioral notes

The supplied `FloorPlan` is the mutable working object; successful changes are
observable through the original object. A failing processor restores its snapshot.
Run geometry-changing profiles before openings unless the profile explicitly permits
and preserves existing openings.


## Warnings / diagnostics

Post-processing uses structured processor outcomes rather than a separate warning list. A processor may report `CHANGED`, `NO_CHANGE`, `NOT_APPLICABLE`, `FAILED`, or `SKIPPED`; pipeline success/failure is reported separately by `PipelineStatus`. In `DEBUG`, `PostProcessingDetails.executions` records each processor's status, duration, rollback flag, outcome, and optional failure. `PRODUCTION` omits that execution trace.

## Public Export Inventory

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

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
