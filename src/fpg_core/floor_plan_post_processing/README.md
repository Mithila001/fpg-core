# Floor Plan Post-Processing

Runs an ordered processor pipeline that refines solved floor-plan geometry with validation and rollback.

## Guide

### Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_post_processing import INITIAL_GENERATION_PROFILE
from fpg_core.floor_plan_post_processing.api import (
    PostProcessingRequest,
    post_process_floor_plan,
)

execution = post_process_floor_plan(
    PostProcessingRequest(
        floor_plan=floor_plan,
        profile=INITIAL_GENERATION_PROFILE,
        specification=generation_spec,
    ),
    mode=ExecutionMode.DEBUG,
)
floor_plan = execution.result.floor_plan
```

### Inputs

- `PostProcessingRequest` contains the working floor plan, ordered profile, and optional original specification.
- An optional custom `ProcessorRegistry` supplies processor implementations.
- `ExecutionMode.PRODUCTION` is the default; `ExecutionMode.DEBUG` enables processor execution records.

### Outputs

The API returns `PostProcessingExecution`, an alias of `FeatureExecution[PostProcessingResult, PostProcessingDetails]`.

- `result` always contains pipeline status, the resulting or restored floor plan, and an optional terminal failure.
- `details` is `None` in PRODUCTION. In DEBUG it contains ordered processor statuses, durations, outcomes, affected room IDs, identity redirects, metrics, rollback state, and failures.
- `metadata` contains the execution mode and total duration.

### Errors and Expected Behaviour

The supplied floor plan is the pipeline working object and successful processors may mutate it. A failed processor is rolled back. Required failures stop the pipeline; optional failures may allow later processors to continue. Expected pipeline failures are returned as results, while invalid configuration can raise `PostProcessingError` subclasses.

### Extension Points

Custom processors implement `FloorPlanProcessor`, declare an ID, configuration type, and prerequisites, and are registered through `ProcessorRegistry`.

## AI Instructions

- Keep processor ordering, prerequisites, mutation, and rollback explicit.
- Preserve room identity redirects.
- Keep this README synchronized with public contracts and DEBUG details.
- Do not import another feature's internal modules.
