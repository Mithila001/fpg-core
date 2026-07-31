# Shared Domain Contracts

`fpg_core.domain` is the canonical type layer shared by FPG Core features. It contains geometry, buildable-space, floor-plan, and generation-specification contracts.

## Guide

Import shared contracts from the package:

```python
from fpg_core.domain import FloorPlan, FloorPlanGenerationSpec, Point, Polygon
```

Features may depend on these contracts. This folder must not depend on feature implementations.

### Main Contract Groups

- `geometry.py`: `Point`, `Segment`, and `Polygon`.
- `buildable_space.py`: land requests, normalized land, setbacks, buildable land, and usable land.
- `floor_plan_spec.py`: room requirements, floor size, relations, and generation specifications.
- `floor_plan.py`: generated rooms, openings, metadata, and completed floor plans.

### Units

Geometry uses project units. The package-wide configuration records the conversion; the current project convention is 10 project units per meter.

### Stability

These types cross feature boundaries and should be treated as public contracts. Identity fields, enum values, and field meanings must remain stable unless a breaking migration is intentional.

## AI Instructions

- Add a type here only when multiple features genuinely share the same domain concept.
- Do not move feature-specific execution, diagnostics, evaluator, processor, or solver types here.
- Check all feature imports and consumers before changing a shared field or enum value.
- Keep this README synchronized with shared contract changes.
