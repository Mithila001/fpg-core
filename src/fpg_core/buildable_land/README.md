# Buildable Land

Validates a convex land parcel, classifies its sides, applies the active setback profile, and returns the remaining buildable polygon.

## Guide

### Public API

```python
from fpg_core.buildable_land.api import (
    calculate_buildable_land,
    normalize_land_request,
)

normalized_land = normalize_land_request(request, buildable_space_config)
buildable_land = calculate_buildable_land(
    normalized_land,
    buildable_space_config.active_profile,
)
```

### Inputs

- `BuildableSpaceRequestData`: land boundary plus exactly one main-entry road attachment.
- `BuildableSpaceConfig`: active setback profile and validation limits.
- `NormalizedLand`: validated counter-clockwise convex polygon, normalized edges, and the entry-road attachment.
- `SetbackProfile`: base setbacks and road-specific adjustments by land side.

Shared contracts come from `fpg_core.domain`. Coordinates and setbacks use project units.

### Outputs

`calculate_buildable_land` returns `BuildableLand` containing:

- `boundary`: the clipped buildable polygon.
- `area`: buildable area in squared project units.
- `edge_setbacks`: resolved setback information for every source edge.

### Errors and Expected Behaviour

Both public operations raise `BuildableLandError`. The exception exposes `code` and `message`.

Expected failures include invalid or non-convex boundaries, unsupported roads, invalid road-edge references, setbacks eliminating all buildable area, and geometry validation failures.

The feature has no external side effects and does not mutate its inputs.

## AI Instructions

- Keep public operations in `api.py`.
- Keep validation and geometry implementation private to this feature.
- Do not import another feature's internal modules.
- Update this README when input rules, error codes, setback behaviour, or return contracts change.
- Keep feature tests under `tests/buildable_land/test_end_to_end.py` unless extra tests are explicitly justified.
