# Floor Plan Openings

Analyzes finalized room walls and uses CP-SAT to place interior doors, exterior doors, and windows.

## Guide

### Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_openings import DEFAULT_OPENING_PROFILE
from fpg_core.floor_plan_openings.api import OpeningGenerationRequest, generate_openings

execution = generate_openings(
    OpeningGenerationRequest(
        floor_plan=floor_plan,
        profile=DEFAULT_OPENING_PROFILE,
    ),
    mode=ExecutionMode.DEBUG,
)
floor_plan_with_openings = execution.result.floor_plan
```

### Inputs

- `OpeningGenerationRequest` contains finalized room geometry and an opening-generation profile.
- An optional custom `OpeningFeatureRegistry` supplies opening-demand features.
- `ExecutionMode.PRODUCTION` is the default; `ExecutionMode.DEBUG` enables analysis and solver diagnostics.

### Outputs

The API returns `OpeningGenerationExecution`, an alias of `FeatureExecution[OpeningGenerationResult, OpeningDiagnostics]`.

- `result` always contains status, optional generated floor plan, profile name, and message.
- `details` is `None` in PRODUCTION. In DEBUG it contains solver statistics, wall and demand counts, candidates, selections, applied constraints, objective terms, and issues.
- `metadata` contains the execution mode and total duration.

### Errors and Expected Behaviour

Invalid floor-plan input returns `INVALID_INPUT`; infeasible, model-invalid, and interrupted solver outcomes are also statuses. Configuration and unsupported extensions may raise `OpeningGenerationError` subclasses. The source floor plan is never mutated.

### Extension Points

Opening-demand features are registered through `OpeningFeatureRegistry`; profiles select public feature and constraint IDs.

## AI Instructions

- Keep wall analysis, OR-Tools models, and extraction private.
- Preserve the non-mutating API and structured statuses.
- Keep this README synchronized with public contracts and DEBUG details.
- Do not import another feature's internal modules.
