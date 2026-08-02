# Floor Plan Preprocessing

Converts a client-facing room request and reference configuration into one validated `FloorPlanGenerationSpec`.

## Guide

### Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_preprocessing import (
    PreprocessingInput,
    prepare_generation_input,
)

execution = prepare_generation_input(
    PreprocessingInput(request=request, config=config),
    mode=ExecutionMode.PRODUCTION,
)

generation_spec = execution.result.generation_spec
```

`prepare_generation_input` is the supported execution entry point.

### Inputs

`PreprocessingInput` contains:

- `request`: floor limits, requested aspect ratio, and requested rooms.
- `config`: allowed room counts, canonical aspect ratios, room-size references, relation references, mandatory rooms, hallway policy, and normalization policy.
- `mode`: shared `ExecutionMode`, supplied to `prepare_generation_input`.

Requested rooms may provide an ID, display name, and requested size. Missing values may be normalized or defaulted according to configuration.

### Outputs

The operation returns:

```text
FeatureExecution[PreparedGenerationInput, PreprocessingReport]
├── result
│   └── generation_spec
├── details
└── metadata
```

- `result` always contains the validated `FloorPlanGenerationSpec`.
- `metadata` always contains the selected execution mode and duration.
- In `PRODUCTION`, `details` is `None` and report-only records are not collected.
- In `DEBUG`, `details` is a `PreprocessingReport` containing normalizations, room decisions, relation decisions, selected room size, floor selection, defaults, and warnings.

### Errors and Expected Behaviour

The pipeline raises subclasses of `FloorPlanPreprocessingError`. Each exception records a preprocessing stage and error code.

Main categories are input validation, normalization, reference data, business rules, room preparation, relation preparation, floor preparation, context validation, and output validation.

The operation is deterministic, request-independent, and has no external side effects.

## AI Instructions

- Keep `prepare_generation_input` as the supported execution entry point.
- Preserve the separation between client request contracts and canonical shared domain contracts.
- Keep production results under `execution.result` and debug-only data under `execution.details`.
- Update this README when normalization rules, policy fields, details fields, or execution behavior changes.
- Keep feature tests under `tests/floor_plan_preprocessing/test_end_to_end.py` unless extra tests are explicitly justified.
- Do not import another feature's internal modules.
