# Floor Plan Preprocessing

Version 0.2.0 returns whole-project-unit floor dimensions.

- Request maximum width and length are floored: `100.9 -> 100`.
- Floor selection evaluates integer width/length values.
- `max_aspect_residual_units` controls `abs(length - width * requested_ratio)`.
- Minimum/maximum target area and room minimum widths remain enforced.
- Preprocessing does not shrink the floor to match a Candidate Search scale.

```python
config = PreprocessingConfig(
    ...,
    max_aspect_residual_units=20,
)

execution = prepare_generation_input(input, mode=ExecutionMode.DEBUG)
spec = execution.result.generation_spec
report = execution.details
```

DEBUG `FloorSelection` reports raw limits, normalized limits, selected dimensions, selected ratio, aspect residual, area bounds, and unused limit area.
