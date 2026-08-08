# Floor Plan Openings

Analyzes finalized room walls and uses CP-SAT to place interior doors, exterior doors, and windows without mutating the source floor plan.

## Guide

### Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_openings.api import (
    DEFAULT_OPENING_CONFIG,
    OpeningGenerationRequest,
    generate_openings,
)

execution = generate_openings(
    OpeningGenerationRequest(
        floor_plan=floor_plan,
        config=DEFAULT_OPENING_CONFIG,
    ),
    mode=ExecutionMode.DEBUG,
)

floor_plan_with_openings = execution.result.floor_plan
```

The supported operation is `generate_openings(...)` from `fpg_core.floor_plan_openings.api`.

### Inputs

`OpeningGenerationRequest` keeps processing input separate from reusable feature configuration:

```python
OpeningGenerationRequest(
    floor_plan=floor_plan,              # processing input
    config=DEFAULT_OPENING_CONFIG,      # opening-generation configuration
)
```

- `floor_plan: FloorPlan` is the finalized request-specific floor plan to process. It must not already contain openings.
- `config: FloorPlanOpeningsConfig` controls how openings are generated.
- `registry: OpeningFeatureRegistry | None` is an optional extension registry supplied to `generate_openings(...)`.
- `mode: ExecutionMode` controls production versus debug execution.

`FloorPlanOpeningsConfig` contains:

- `name`: configuration/preset name.
- `enabled_features`: opening-demand feature IDs to run.
- `enabled_constraints`: opening-model constraint IDs to apply.
- `geometry: GeometryConfig`: coordinate scaling, tolerance, corner clearance, and window spacing.
- `dimensions: DimensionConfig`: door width, window width, and minimum shared-wall length.
- `policy: FeaturePolicy`: room-pair rules, door caps, room priorities, and side priorities.
- `objective: ObjectiveConfig`: CP-SAT objective tier ordering.
- `solver: SolverConfig`: CP-SAT time limit, worker count, seed, presolve, and logging settings.

`DEFAULT_OPENING_CONFIG` is the built-in default configuration.

For compatibility, `OpeningGenerationProfile` is an alias of `FloorPlanOpeningsConfig` and `DEFAULT_OPENING_PROFILE` is an alias of `DEFAULT_OPENING_CONFIG`. New code should prefer the `Config` names and `OpeningGenerationRequest.config`.

#### Execution modes

- `ExecutionMode.PRODUCTION`: returns the normal result without collecting solver diagnostics.
- `ExecutionMode.DEBUG`: additionally collects analysis, candidate, solver, constraint, objective, and issue details.

### Outputs

The API returns `OpeningGenerationExecution`, an alias of `FeatureExecution[OpeningGenerationResult, OpeningDiagnostics]`.

- `result` always contains status, optional generated floor plan, configuration preset name in the compatibility field `profile_name`, and a message.
- `details` is `None` in `PRODUCTION`.
- In `DEBUG`, `details` contains solver statistics, analyzed wall counts, demand/candidate/selection counts, applied constraints, objective terms, and issues.
- `metadata` contains the execution mode and total duration.

`OpeningGenerationStatus` can be `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID`, `UNKNOWN`, or `INVALID_INPUT`.

### Errors and Expected Behaviour

Invalid floor-plan processing input returns `INVALID_INPUT`. Infeasible, model-invalid, and interrupted solver outcomes are represented as result statuses.

Invalid configuration or unsupported extension IDs can raise `OpeningConfigurationError`. Other feature errors derive from `OpeningGenerationError`.

The source `FloorPlan` is not mutated. A solved result contains a copied floor plan with generated openings.

### Extension Points

`OpeningFeatureRegistry` supports custom opening-demand features. Configuration selects feature IDs and built-in constraint IDs; callers should register any custom feature before enabling its ID.

## AI Instructions

- Keep this README synchronized with the public API and contracts.
- Keep processing input and configuration clearly separated.
- Keep wall analysis, OR-Tools models, and extraction private.
- Preserve the non-mutating API and structured statuses.
- Document changes to inputs, outputs, configuration, and DEBUG details.
- Do not document private implementation as supported API.
- Do not import another feature's internal modules.
