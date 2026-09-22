# Shared Domain Contracts

`fpg_core.domain` is the canonical type layer shared by FPG Core features. Feature implementations may depend on these contracts; the domain package must not import feature modules.

## Main candidate contracts

### `CandidateSearchSpace`

Describes the centered divisible rectangle used while preprocessing prepares the
exact grid:

```python
CandidateSearchSpace(
    origin_x=0.5,
    origin_y=2.5,
    width=120,
    length=78,
    grid_spacing=6,
)
```

Width and length are exact spacing multiples. Origins may use half project units when an odd-sized floor is trimmed equally from both sides.

New feature-to-feature flow should pass the resulting `ResolvedCandidateGrid`
instead of asking Candidate Search to resolve this rectangle again.

### `HallwayRoomCountRange`

Defines the number of distinct hallway rooms Candidate Search may activate in one trial:

```python
HallwayRoomCountRange(maximum=3)
```

The minimum is always `1`.

### `ResolvedCandidateGrid`

Contains the exact X/Y nodes prepared by Floor Plan Preprocessing, uniform
spacing, coordinate/index conversion, row-major flat-node conversion, edge-node
checks, and non-edge hint-node indexes.

### `CandidatePoint`

Represents one room hint coordinate. Current Candidate Search creates one point per room and uses `hint_index=1`.

### `CandidateMap`

Couples candidate points to the resolved grid and rejects off-grid, overlapping,
or outer-edge hint points.

## Other contract groups

- `circulation.py`: routing grids, rules, traffic enums, classifications, and route detail primitives.
- `execution.py`: `FeatureExecution`, `ExecutionMetadata`, and `ExecutionMode`.
- `geometry.py`: `Point`, `Segment`, and `Polygon`.
- `buildable_space.py`: land, setback, buildable-land, and usable-land contracts.
- `floor_plan_spec.py`: room requirements, floor size, relations, and generation specifications.
- `floor_plan.py`: generated rooms, openings, metadata, and completed floor plans.

## Units

The current convention is:

- `10` project units = `1` meter
- `1` project unit = `10` centimeters

Intermediate geometry and centered search origins may use floating-point values.

## Stability

These types cross feature boundaries and are public contracts. Identity fields, enum values, and field meanings should change only through an intentional migration.
