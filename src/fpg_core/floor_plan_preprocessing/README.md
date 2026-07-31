# Floor Plan Preprocessing

Converts a client-facing room request and reference configuration into one validated `FloorPlanGenerationSpec` plus an explanation report.

## Guide

### Public API

```python
from fpg_core.floor_plan_preprocessing.api import prepare_generation_input
from fpg_core.floor_plan_preprocessing import PreprocessingInput

prepared = prepare_generation_input(
    PreprocessingInput(request=request, config=config)
)
```

### Inputs

`PreprocessingInput` contains:

- `request`: floor limits, requested aspect ratio, and requested rooms.
- `config`: allowed room counts, canonical aspect ratios, room-size references, relation references, mandatory rooms, hallway policy, and normalization policy.

Requested rooms may provide an ID, display name, and requested size. Missing values may be normalized or defaulted according to configuration.

### Outputs

`PreparedGenerationInput` contains:

- `generation_spec`: canonical floor, room, size, and relation contracts used by later features.
- `report`: normalizations, room decisions, relation decisions, selected size, floor selection, defaults, and warnings.

### Errors and Expected Behaviour

The pipeline raises subclasses of `FloorPlanPreprocessingError`. Each exception records a preprocessing stage and error code.

Main categories are input validation, normalization, reference data, business rules, room preparation, relation preparation, floor preparation, context validation, and output validation.

The operation is deterministic, request-independent, and has no external side effects.

## AI Instructions

- Keep `prepare_generation_input` as the supported execution entry point.
- Preserve the separation between client request contracts and canonical shared domain contracts.
- Update this README when normalization rules, policy fields, report fields, or error stages change.
- Keep feature tests under `tests/floor_plan_preprocessing/test_end_to_end.py` unless extra tests are explicitly justified.
