# Floor Plan Solver

Builds and solves a CP-SAT model from a canonical generation specification, a generation profile, and optional seed geometry.

## Guide

### Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_solver import INITIAL_GENERATION_PROFILE
from fpg_core.floor_plan_solver.api import FloorPlanSolveRequest, generate_floor_plan

execution = generate_floor_plan(
    FloorPlanSolveRequest(
        specification=generation_spec,
        profile=INITIAL_GENERATION_PROFILE,
        candidate_hints=room_hints,
    ),
    mode=ExecutionMode.DEBUG,
)
floor_plan = execution.result.floor_plan
```

`FloorPlanSolver` is public when a caller needs to reuse a custom `ConstraintRegistry`.

### Inputs

- `FloorPlanSolveRequest` contains the shared `FloorPlanGenerationSpec`, generation profile, optional candidate hints, and optional existing floor plan.
- `ExecutionMode.PRODUCTION` is the default; `ExecutionMode.DEBUG` enables solver diagnostics.
- Solver limits, seed, worker count, logging, presolve, and gap limit come from the selected profile.

### Outputs

The API returns `FloorPlanSolveExecution`, an alias of `FeatureExecution[FloorPlanSolveResult, SolverDiagnostics]`.

- `result` always contains the status, optional floor plan, profile name, and status message.
- `details` is `None` in PRODUCTION. In DEBUG it contains raw solver status, timing, objective information, search statistics, applied constraints, and penalty terms.
- `metadata` contains the execution mode and total duration.

### Errors and Expected Behaviour

Invalid specifications, profiles, required seeds, or constraint IDs raise `FloorPlanSolverError` subclasses before solving. Infeasible and interrupted solver outcomes are returned as statuses. Randomness is controlled by the selected profile's solver seed.

### Extension Points

Hard and soft constraints are selected through profiles and registered through `ConstraintRegistry`.

## AI Instructions

- Keep OR-Tools objects and implementation modules private.
- Keep hard constraints separate from soft objective preferences.
- Keep this README synchronized with public contracts and DEBUG details.
- Do not import another feature's internal modules.
