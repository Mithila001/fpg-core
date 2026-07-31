# Floor Plan Openings

Analyzes finalized room walls and uses CP-SAT to place interior doors, exterior doors, and windows according to an opening-generation profile.

## Guide

### Public API

```python
from fpg_core.floor_plan_openings.api import generate_openings
from fpg_core.floor_plan_openings import (
    DEFAULT_OPENING_PROFILE,
    OpeningGenerationRequest,
)

result = generate_openings(
    OpeningGenerationRequest(
        floor_plan=floor_plan,
        profile=DEFAULT_OPENING_PROFILE,
    )
)
```

### Inputs

- `FloorPlan`: finalized room geometry without conflicting existing openings.
- `OpeningGenerationProfile`: enabled features and constraints, geometry scale, dimensions, room policies, objective order, and solver settings.
- Optional custom `OpeningFeatureRegistry` passed to the API.

### Outputs

`OpeningGenerationResult` contains status, optional floor plan with openings, profile name, message, and diagnostics.

Diagnostics include solver statistics, analyzed wall count, demand/candidate/selection counts, applied constraints, objective terms, and issues.

### Errors and Expected Behaviour

Invalid floor-plan input is returned with `INVALID_INPUT` status and diagnostics. Feasible, infeasible, model-invalid, and unknown solver outcomes are also returned as statuses.

Profile construction and unsupported extension configuration may raise subclasses of `OpeningGenerationError`. The source floor plan is not mutated; a generated plan is returned when solved.

### Extension Points

Opening-demand features are registered through `OpeningFeatureRegistry`. Profiles select feature and constraint IDs without exposing OR-Tools objects.

## AI Instructions

- Keep wall analysis, OR-Tools model objects, and placement extraction internal.
- Preserve the non-mutating public API and structured status result.
- Update this README when opening policies, dimensions, statuses, diagnostics, or extension IDs change.
- Keep feature tests under `tests/floor_plan_openings/test_end_to_end.py` unless extra tests are explicitly justified.
