# Floor Plan Preprocessing

This package converts an API-independent room request and caller-supplied
reference data into a trusted `FloorPlanGenerationSpec`.

It owns representation normalization, preprocessing validation, compatibility
business rules, room-size resolution, room-relation expansion, and selection of
the rectangular generation floor. It does not load a database, know about API
models, choose a solver profile, run Candidate Search, or invoke generation.
The active production pipeline intentionally does not call this package yet.

## Public contract

```text
PreprocessingInput
    -> prepare_generation_input()
    -> PreparedGenerationInput(generation_spec, report)
```

`PreprocessingInput` contains a `PreprocessingRequest`, source-neutral
`PreprocessingReferenceData`, and an immutable `PreprocessingPolicy`. The
report records normalization, derived or removed rooms, relation expansion,
defaults, and floor selection. Downstream algorithms depend only on the
generation specification.

## Pipeline

```text
structural validation -> normalization -> normalized validation
-> reference validation -> business rules -> context preparation
-> final invariant validation
```

Expected failures derive from `FloorPlanPreprocessingError`; callers can map
them to HTTP responses later. The core performs no I/O, logging, database
fallback, progress emission, or mutation of input values.

## Fixture example

```python
from fpg_core.floor_plan_preprocessing import (
    FloorLimits, PreprocessingInput, PreprocessingReferenceData,
    PreprocessingRequest, RequestedRoom, RoomSizeReference,
    prepare_generation_input,
)

request = PreprocessingRequest(
    floor_limits=FloorLimits(max_width=120, max_length=100),
    aspect_ratio="1:1",
    rooms=(
        RequestedRoom("bedroom", "bedroom_1", requested_size="regular"),
        RequestedRoom("kitchen", "kitchen_1", requested_size="regular"),
        RequestedRoom("bathroom", "bathroom_1", requested_size="regular"),
        RequestedRoom("veranda", "veranda_1", requested_size="regular"),
    ),
)

# Tests normally construct the complete tuple from fixture data.
references = PreprocessingReferenceData(room_sizes=(
    RoomSizeReference("bedroom", "regular", 10, 20, 100, 400),
    RoomSizeReference("kitchen", "regular", 10, 20, 100, 400),
    RoomSizeReference("bathroom", "regular", 10, 20, 100, 400),
    RoomSizeReference("veranda", "regular", 10, 20, 100, 400),
    RoomSizeReference("livingRoom", "regular", 10, 25, 100, 625),
))

prepared = prepare_generation_input(PreprocessingInput(request, references))
```
