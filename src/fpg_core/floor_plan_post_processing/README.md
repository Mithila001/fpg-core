# Floor Plan Post-Processing

Runs an ordered processor pipeline that refines solved floor-plan geometry with validation and rollback.

## Guide

### Public API

Use the feature through `fpg_core.floor_plan_post_processing.api`.

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_post_processing.api import (
    INITIAL_GENERATION_PROFILE,
    PostProcessingRequest,
    post_process_floor_plan,
)

execution = post_process_floor_plan(
    PostProcessingRequest(
        floor_plan=floor_plan,
        specification=generation_spec,
        config=INITIAL_GENERATION_PROFILE,
    ),
    mode=ExecutionMode.DEBUG,
)

processed_floor_plan = execution.result.floor_plan
```

`INITIAL_GENERATION_PROFILE` is a predefined `FloorPlanPostProcessingConfig`. The word "profile" means a named configuration preset; it is still passed through the explicit `config` field.

### Inputs

`PostProcessingRequest` clearly separates processing data from configuration:

```text
PostProcessingRequest
├── floor_plan       processing input
├── specification    optional processing/domain input
└── config            reusable post-processing configuration
```

- `floor_plan: FloorPlan` is the working floor plan being transformed.
- `specification: FloorPlanGenerationSpec | None` supplies optional request-specific generation context used by processors that need it.
- `config: FloorPlanPostProcessingConfig` controls how the feature performs post-processing.

`FloorPlanPostProcessingConfig` contains:

- `name`: configuration/preset name.
- `processors`: ordered `ProcessorUse` entries.
- `numeric`: shared `NumericPolicy` for tolerance and grid size.
- `reject_existing_openings`: whether pre-existing openings make the initial input invalid.

Each `ProcessorUse` contains:

- `processor_id`: registered processor identifier.
- `config`: that processor's typed configuration object.
- `required`: whether failure stops the pipeline.
- `validate_after`: whether the floor plan is validated immediately after success.

Built-in processor configuration types include:

- `VerandaAdjustmentConfig`
- `WallExtensionConfig` / `WallExtensionRule`
- `PlaceholderRemovalConfig`
- `HallwayMergeConfig`
- `GridSnapConfig`
- `RectilinearSimplificationConfig`

Example custom configuration:

```python
from fpg_core.floor_plan_post_processing.api import (
    FloorPlanPostProcessingConfig,
    GridSnapConfig,
    NumericPolicy,
    ProcessorUse,
)

config = FloorPlanPostProcessingConfig(
    name="snap_only",
    processors=(
        ProcessorUse(
            processor_id="grid_snap",
            config=GridSnapConfig(grid_size=1.0),
            required=True,
            validate_after=True,
        ),
    ),
    numeric=NumericPolicy(tolerance=1e-6, grid_size=1.0),
)
```

An optional custom `ProcessorRegistry` may be supplied to `post_process_floor_plan` when processor extension is required.

`ExecutionMode.PRODUCTION` is the default. `ExecutionMode.DEBUG` additionally captures ordered processor execution details.

### Outputs

The API returns `PostProcessingExecution`, an alias of `FeatureExecution[PostProcessingResult, PostProcessingDetails]`.

- `result` always contains pipeline status, the resulting/restored floor plan, and an optional terminal failure.
- `details` is `None` in `PRODUCTION`.
- In `DEBUG`, `details.executions` records processor status, duration, outcome, affected room IDs, identity redirects, metrics, rollback state, and failures.
- `metadata` contains shared execution mode and total duration.

### Errors and Expected Behaviour

The supplied `FloorPlan` is the pipeline working object. Successful processors may mutate it.

A processor failure restores the snapshot taken immediately before that processor. A required processor failure stops the pipeline. An optional failure may allow later processors to continue.

Expected processing failures are represented by `PostProcessingResult.status` and `ProcessingFailure`. Configuration and validation errors use the feature exception hierarchy rooted at `PostProcessingError`.

Geometry-changing configurations normally reject floor plans that already contain openings. The built-in initial-generation profile removes solver placeholders and performs final validation requiring no placeholders.

### Extension Points

Custom processors implement `FloorPlanProcessor`, declare:

- `processor_id`
- `description`
- `config_type`
- optional `prerequisites`

and implement `process(...)`. Register them with `ProcessorRegistry`, then reference their IDs through `ProcessorUse` entries in `FloorPlanPostProcessingConfig`.

`PostProcessingProfile` remains available as a backward-compatible alias of `FloorPlanPostProcessingConfig`. New code should prefer the explicit configuration name.

#### Migration from the previous request contract

Old:

```python
PostProcessingRequest(
    floor_plan=floor_plan,
    specification=generation_spec,
    profile=INITIAL_GENERATION_PROFILE,
)
```

New:

```python
PostProcessingRequest(
    floor_plan=floor_plan,
    specification=generation_spec,
    config=INITIAL_GENERATION_PROFILE,
)
```

The processor behavior and built-in profile order are unchanged.

## AI Instructions

- Keep processing input and configuration clearly separated in the public contract.
- Keep feature-only configuration in `config.py`.
- Keep processor ordering, prerequisites, mutation, and rollback explicit.
- Preserve room identity redirects.
- Keep this README synchronized with public contracts and DEBUG details.
- Do not document internal pipeline helpers as supported API.
- Do not import another feature's internal modules.
