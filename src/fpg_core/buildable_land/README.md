# Buildable Land

Validates a convex land parcel, normalizes its orientation, classifies boundary sides, applies setback configuration, and returns the remaining buildable polygon.

## Guide

### Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.buildable_land import (
    BuildableLandConfig,
    BuildableLandInput,
    calculate_buildable_land,
)

execution = calculate_buildable_land(
    BuildableLandInput(
        request=request,
        config=BuildableLandConfig(
            setback_profile=setback_profile,
            validation_limits=validation_limits,
        ),
    ),
    mode=ExecutionMode.PRODUCTION,
)

buildable_land = execution.result.buildable_land
normalized_land = execution.result.normalized_land
```

### Inputs

`BuildableLandInput` separates request data from reusable configuration:

```text
BuildableLandInput
├── request: BuildableSpaceRequestData   # processing input
└── config: BuildableLandConfig          # algorithm/reference configuration
```

`BuildableSpaceRequestData` contains the land boundary and exactly one main-entry road attachment.

`BuildableLandConfig` contains:

- `setback_profile`: base setbacks plus road-specific adjustments;
- `validation_limits`: allowed vertex count and coordinate limits.

Coordinates and setback distances use project units.

### Outputs

Returns:

```text
FeatureExecution[BuildableLandResult, BuildableLandDetails]
```

`result` is always available and contains:

- `buildable_land`: clipped `BuildableLand` geometry, area, and resolved edge setbacks;
- `normalized_land`: validated counter-clockwise land geometry used by later features such as `usable_land`.

In `PRODUCTION`, `details` is `None`.

In `DEBUG`, `details.edge_classifications` records the resolved FRONT/BACK/LEFT/RIGHT classification for each source boundary edge.

`metadata` contains the execution mode and duration.

### Errors and Expected Behaviour

Raises `BuildableLandError` with `code`, `message`, and optional `details`.

Expected failures include invalid or non-convex boundaries, unsupported road types, invalid road-edge references, invalid feature configuration, setbacks eliminating all buildable area, and geometry validation failures.

The feature is deterministic for identical inputs and does not mutate its inputs.

### Extension Points

There are currently no registries or plug-in extension points. Setback and validation behaviour is configured through `BuildableLandConfig`.

## AI Instructions

- Keep this README synchronized with public behaviour.
- Keep configuration in `config.py` and processing/result contracts in `contracts.py`.
- Keep public operations and supported types exposed through `api.py`.
- Do not import another feature's internal modules.
- Keep `NormalizedLand` in the production result because downstream land processing requires it.
- Keep feature tests under `tests/buildable_land/test_end_to_end.py` unless extra tests are explicitly justified.
