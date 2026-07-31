# Floor Plan Solver

Builds and solves a CP-SAT model from a canonical generation specification, generation profile, and optional candidate or floor-plan seed data.

## Guide

### Public API

```python
from fpg_core.floor_plan_solver.api import generate_floor_plan
from fpg_core.floor_plan_solver import (
    FloorPlanSolveRequest,
    INITIAL_GENERATION_PROFILE,
)

result = generate_floor_plan(
    FloorPlanSolveRequest(
        specification=generation_spec,
        profile=INITIAL_GENERATION_PROFILE,
        candidate_hints=room_hints,
    )
)
```

`FloorPlanSolver` is also public when a caller needs to provide and reuse a custom `ConstraintRegistry`.

### Inputs

- `FloorPlanGenerationSpec`: floor size, rooms, sizes, and relations.
- `GenerationProfile`: hard constraints, soft constraints, solver settings, coordinate preparation, and seed policy.
- `RoomPlacementHint`: optional room position and size hints.
- `existing_floor_plan`: optional refinement seed when required by the selected profile.

### Outputs

`FloorPlanSolveResult` contains status, optional `FloorPlan`, profile name, message, and `SolverDiagnostics`.

A result is solved when its status is `OPTIMAL` or `FEASIBLE` and `floor_plan` is present. Infeasibility and solver termination are returned as statuses rather than exceptions.

### Errors and Expected Behaviour

Invalid specifications, profiles, required seeds, or constraint IDs raise subclasses of `FloorPlanSolverError` before solving.

Solver limits, worker count, seed, logging, presolve, and gap limit come from the selected profile. Randomness should be controlled through the profile's solver seed where deterministic behaviour is required.

### Extension Points

Hard and soft constraints are registered through `ConstraintRegistry`. Custom profiles may select registered constraints without changing the solver API.

## AI Instructions

- Keep OR-Tools objects internal to this feature.
- Keep hard constraints separate from soft objective preferences.
- Do not move server progress, persistence, or job handling into this feature.
- Update this README when request/result contracts, statuses, profiles, seeds, or public constraints change.
- Keep feature tests under `tests/floor_plan_solver/test_end_to_end.py` unless extra tests are explicitly justified.
