# Floor Plan Preprocessing

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Internal feature `README.md` files are development notes and are not the consumer contract. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Converts client room choices and reference rules into a validated
`FloorPlanGenerationSpec`, exact centered candidate grid, and allowed hallway-room
count. Use it to turn permissive client-facing values into canonical typed generation
inputs.

## Public API

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

## Inputs

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

## Configuration

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

## Recommended values

Use the package defaults for optional policy fields unless product rules require a
change. Room sizes, buffers, count rules, grid spacing, and supported ratios are
project reference data; the code provides no universal values. Choose spacing that
is even and leaves enough interior nodes for every possible room.

## Outputs

`PreprocessingExecution` is
`FeatureExecution[PreparedGenerationInput, PreprocessingReport]`. The result contains
`generation_spec`, `candidate_grid`, and `hallway_room_count_range`. Its
`generation_spec_for_candidate(candidate)` validates grid/room identity and returns a
spec containing exactly the selected hallway rooms. In DEBUG, `details` records
normalizations, room/relation decisions, size choice, floor/grid selection, hallway
range, defaults, and warnings. Metadata contains mode and duration.

## Warnings / diagnostics

Warnings are DEBUG-only data in `PreprocessingReport.warnings: tuple[str, ...]`. The same report also records applied defaults, normalization records, room/relation decisions, floor selection, candidate-grid selection, and hallway-count selection. Consumers must not depend on `execution.details` or warning strings being present in `PRODUCTION`. Expected invalid requests still raise typed preprocessing exceptions rather than being downgraded to warnings.

## Errors / failure conditions

Expected failures raise `FloorPlanPreprocessingError` subclasses. Inspect `.stage`,
`.code`, `.message`, and immutable `.details`. Failures include invalid input/reference
data, forbidden/count-invalid rooms, duplicate IDs, excess attached bathrooms,
missing sizes/relations, insufficient floor limits, excessive aspect residual, or an
invalid output grid. A non-`ExecutionMode` mode raises `TypeError`.

## Usage example

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

## Important behavioral notes

The result template contains every possible hallway room, not a selected subset.
Compatibility `candidate_search_space` properties are derived views; the exact
`ResolvedCandidateGrid` is authoritative. The operation does not invoke search or a
solver.

## Public Export Inventory

The supported feature-root import surface is `fpg_core.floor_plan_preprocessing`. Its current exported symbols are:

- `AspectRatioRule`
- `BusinessRuleError`
- `CandidateGridSelection`
- `CandidateSearchSpaceSelection`
- `ContextValidationError`
- `ExcessAttachedBathroomPolicy`
- `FloorLimits`
- `FloorPlanPreprocessingError`
- `FloorPreparationError`
- `FloorSelection`
- `InputValidationError`
- `NormalizationError`
- `NormalizationRecord`
- `OutputValidationError`
- `PreprocessingConfig`
- `PreprocessingErrorCode`
- `PreprocessingExecution`
- `PreprocessingInput`
- `PreprocessingPolicy`
- `PreprocessingReferenceData`
- `PreprocessingReport`
- `PreprocessingRequest`
- `PreprocessingStage`
- `PreparedGenerationInput`
- `ReferenceDataError`
- `RelationDecision`
- `RelationPreparationError`
- `RequestedRoom`
- `RoomCountRule`
- `RoomDecision`
- `RoomPreparationError`
- `RoomRelationReference`
- `RoomSizeReference`
- `RoomSizeSelectionStrategy`
- `canonical_aspect_ratio`
- `prepare_generation_input`

Consumers should prefer the feature-root import surface shown above and `fpg_core.domain` for canonical shared contracts. Implementation submodules are not part of the supported consumer surface unless explicitly documented.

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
