# Floor Plan Preprocessing

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Implementation rationale is maintained in the internal architecture and feature notes. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

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
  always one. `hallway_min_width` sets their width constraint and must be at least 10 project units.
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
    hallway_min_width=10,
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


## Warnings / diagnostics

Warnings are DEBUG-only data in `PreprocessingReport.warnings: tuple[str, ...]`. The same report also records applied defaults, normalization records, room/relation decisions, floor selection, candidate-grid selection, and hallway-count selection. Consumers must not depend on `execution.details` or warning strings being present in `PRODUCTION`. Expected invalid requests still raise typed preprocessing exceptions rather than being downgraded to warnings.

## Public Export Inventory

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

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
