# Floor Plan Post-Processing

Runs an ordered, configurable processor pipeline that refines solved floor-plan geometry while preserving structured execution and rollback information.

## Guide

### Public API

```python
from fpg_core.floor_plan_post_processing.api import post_process_floor_plan
from fpg_core.floor_plan_post_processing import (
    INITIAL_GENERATION_PROFILE,
    PostProcessingRequest,
)

result = post_process_floor_plan(
    PostProcessingRequest(
        floor_plan=floor_plan,
        profile=INITIAL_GENERATION_PROFILE,
        specification=generation_spec,
    )
)
```

The supplied floor plan is the pipeline working object and may be mutated by successful processors. Use a copy before calling when the original must be retained.

### Inputs

- `PostProcessingRequest.floor_plan`: solved floor plan.
- `profile`: ordered processor uses, numeric policy, required flags, and validation flags.
- Optional generation specification for processors that need original intent.
- Optional custom `ProcessorRegistry` passed to the API.

### Outputs

`PostProcessingResult` contains:

- `SUCCESS` or `FAILED` status;
- the resulting or restored floor plan;
- execution record for each processor;
- optional structured failure.

Processor execution records include status, duration, rollback state, outcome, affected room IDs, redirects, and metrics.

### Errors and Expected Behaviour

Expected pipeline failures are normally returned as `PostProcessingResult` rather than raised. A failed processor is rolled back. Failure of a required processor stops the pipeline; optional processor failures may allow later processors to continue.

### Extension Points

Custom processors implement `FloorPlanProcessor`, declare an ID, configuration type, and prerequisites, and are registered through `ProcessorRegistry`.

## AI Instructions

- Keep processor ordering and prerequisites explicit in profiles.
- Preserve rollback behaviour and room identity redirects.
- Update this README when mutation, processor statuses, profiles, or failure handling change.
- Keep feature tests under `tests/floor_plan_post_processing/test_end_to_end.py` unless extra tests are explicitly justified.
