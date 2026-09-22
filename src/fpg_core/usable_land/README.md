# Usable Land

Finds the best road-aligned rectangular floor area inside calculated buildable land while enforcing configured minimum dimensions and bounded search limits.

## Guide

### Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.usable_land import (
    UsableLandConfig,
    UsableLandInput,
    find_usable_land,
)

execution = find_usable_land(
    UsableLandInput(
        buildable_land=buildable_land,
        land=normalized_land,
        config=UsableLandConfig(
            minimum_width=80,
            minimum_length=100,
            search_resolution=1,
            maximum_sweep_lines=500,
        ),
    ),
    mode=ExecutionMode.PRODUCTION,
)

usable_land = execution.result
```

### Inputs

`UsableLandInput` clearly separates processing data from reusable configuration:

```text
UsableLandInput
├── buildable_land: BuildableLand   # processing input
├── land: NormalizedLand            # processing input / road orientation
└── config: UsableLandConfig        # search configuration
```

`UsableLandConfig` contains:

- `minimum_width`: minimum accepted floor width;
- `minimum_length`: minimum accepted floor length;
- `search_resolution`: spacing between road-aligned sweep rows;
- `maximum_sweep_lines`: synchronous search safety limit.

All dimensions use project units. All configuration values must be positive integers.

For migration from the older shared domain contract:

```python
config = UsableLandConfig.from_constraints(old_usable_land_constraints)
```

### Outputs

Returns:

```text
FeatureExecution[UsableLand, UsableLandDetails]
```

`result` is always the normal `UsableLand` result containing:

- world-coordinate rectangular `boundary`;
- `width`, `length`, and `area`;
- floor-width alignment relative to the entry road;
- source entry-road edge index.

In `PRODUCTION`, `details` is `None`.

In `DEBUG`, details include:

- number of evaluated rectangle row-pairs;
- buildable polygon in road-aligned local coordinates;
- selected rectangle in local coordinates;
- road-aligned transform origin and axes.

`metadata` contains the execution mode and duration.

### Errors and Expected Behaviour

Raises `UsableLandError` with `code`, `message`, and optional `details`.

Common failures include no rectangle satisfying minimum dimensions, search limits being exceeded, invalid transforms, and final geometry validation failure.

The search is deterministic for identical inputs and does not mutate its inputs.

### Extension Points

There are currently no registries or plug-in extension points. Search behaviour is controlled by `UsableLandConfig`.

## AI Instructions

- Keep this README synchronized with public behaviour.
- Keep configuration in `config.py` and processing/debug contracts in `contracts.py`.
- Keep public operations and supported types exposed through `api.py`.
- Keep the feature independent from `buildable_land` internals; communicate through shared domain values only.
- Update documentation if ranking, search limits, alignment rules, or return fields change.
- Keep feature tests under `tests/usable_land/test_end_to_end.py` unless extra tests are explicitly justified.
