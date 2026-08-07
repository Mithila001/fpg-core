# Server Integration

Consumer applications install `fpg-core`, construct shared domain inputs, and call feature-level APIs. They remain responsible for transport mapping, persistence, jobs, progress reporting, retries, and cancellation.

## Floor-plan execution contracts

The solver, final scoring, post-processing, and openings entry points return `FeatureExecution` and accept a keyword-only shared `ExecutionMode`:

```python
from fpg_core.domain import ExecutionMode

execution = feature_operation(feature_input, mode=ExecutionMode.PRODUCTION)
result = execution.result
```

Use PRODUCTION for normal server requests. It returns `details=None` and avoids retaining R&D diagnostics. Use DEBUG only for explicit diagnostic or laboratory workflows; feature-specific detail types are returned through `execution.details`. Every successful call includes execution mode and duration in `execution.metadata`.

## Breaking migration

- Read the former raw result through `execution.result`.
- Read former solver/opening diagnostics through `execution.details` in DEBUG.
- Read post-processing processor executions through `execution.details.executions` in DEBUG.
- Construct `FloorPlanScoringInput` instead of passing floor plan, specification, and profile as separate arguments.
- Read floor-plan scoring group and evaluator data through `execution.details` in DEBUG.

Expected algorithm outcomes such as infeasibility and invalid opening input remain structured result statuses. Exceptions still represent invalid configuration, contracts, or unsupported extensions.
