# Floor Plan Post-Processing

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Internal feature `README.md` files are development notes and are not the consumer contract. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

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

## Warnings / diagnostics

Post-processing uses structured processor outcomes rather than a separate warning list. A processor may report `CHANGED`, `NO_CHANGE`, `NOT_APPLICABLE`, `FAILED`, or `SKIPPED`; pipeline success/failure is reported separately by `PipelineStatus`. In `DEBUG`, `PostProcessingDetails.executions` records each processor's status, duration, rollback flag, outcome, and optional failure. `PRODUCTION` omits that execution trace.

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

## Public Export Inventory

The supported feature-root import surface is `fpg_core.floor_plan_post_processing`. Its current exported symbols are:

- `ConfigurationError`
- `FloorPlanPostProcessingConfig`
- `FloorPlanProcessor`
- `GridSnapConfig`
- `HallwayMergeConfig`
- `INITIAL_GENERATION_PROFILE`
- `NumericPolicy`
- `PipelineStatus`
- `PlaceholderRemovalConfig`
- `PostProcessingContext`
- `PostProcessingDetails`
- `PostProcessingError`
- `PostProcessingExecution`
- `PostProcessingProfile`
- `PostProcessingRequest`
- `PostProcessingResult`
- `ProcessingFailure`
- `ProcessorError`
- `ProcessorExecution`
- `ProcessorOutcome`
- `ProcessorRegistry`
- `ProcessorStatus`
- `ProcessorUse`
- `RectilinearSimplificationConfig`
- `RollbackError`
- `ValidationError`
- `VerandaAdjustmentConfig`
- `WallExtensionConfig`
- `WallExtensionRule`
- `create_default_registry`
- `post_process_floor_plan`

Consumers should prefer the feature-root import surface shown above and `fpg_core.domain` for canonical shared contracts. Implementation submodules are not part of the supported consumer surface unless explicitly documented.

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
