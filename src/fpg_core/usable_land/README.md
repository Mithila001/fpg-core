# Usable Land

Finds the best road-aligned rectangular floor area that fits inside calculated buildable land and satisfies minimum dimension constraints.

## Guide

### Public API

```python
from fpg_core.usable_land.api import find_usable_land

usable_land = find_usable_land(
    buildable_land=buildable_land,
    land=normalized_land,
    constraints=usable_land_constraints,
)
```

### Inputs

- `BuildableLand`: output from the buildable-land feature.
- `NormalizedLand`: provides entry-road orientation and source-edge identity.
- `UsableLandConstraints`: minimum width, minimum length, search resolution, and maximum sweep-line limit.

All dimensions use project units.

### Outputs

Returns `UsableLand` with:

- rectangular world-coordinate `boundary`;
- `width`, `length`, and `area`;
- width alignment relative to the entry road;
- the source entry-road edge index.

### Errors and Expected Behaviour

Raises `UsableLandError` with `code`, `message`, and optional `details`.

Common failures are no rectangle meeting minimum dimensions, search limits being exceeded, invalid transforms, or final geometry validation failure.

The search is deterministic for identical inputs and does not mutate its inputs.

## AI Instructions

- Keep the feature independent from `buildable_land` internals; communicate through shared domain results only.
- Keep the public operation in `api.py`.
- Update this README when ranking, search limits, alignment rules, or return fields change.
- Keep feature tests under `tests/usable_land/test_end_to_end.py` unless extra tests are explicitly justified.
