# Land preparation: buildable and usable areas

## Buildable land (`fpg_core.buildable_land`)

Call `calculate_buildable_land(BuildableLandInput(request=..., config=...), mode=...)`.

- `request` is `BuildableSpaceRequestData`: parcel boundary and exactly one main-entry road attachment.
- `BuildableLandConfig` supplies setback profile and geometric validation limits; no municipal policy is hard-coded as universally correct.
- The pipeline validates a convex parcel, normalizes its boundary, classifies front/back/left/right from the entry road, applies setbacks, and constructs the clipped buildable polygon.
- `execution.result.buildable_land` and `execution.result.normalized_land` are both required downstream. Do not discard normalized road orientation.
- `DEBUG` exposes edge classifications; production details are absent. Invalid geometry, road references, and setbacks that eliminate the usable area raise `BuildableLandError`.

Sources: `buildable_land/pipeline.py`, `classification.py`, `setbacks.py`, `validation.py`, `config.py`.

## Usable land (`fpg_core.usable_land`)

Call `find_usable_land(UsableLandInput(buildable_land=..., land=normalized_land, config=...), mode=...)`.

- `UsableLandConfig` controls `minimum_width`, `minimum_length`, `search_resolution`, and `maximum_sweep_lines` (a bounded search).
- The result is a road-aligned rectangle inside the buildable polygon: boundary, area, width, length, alignment, and entry-road edge index. It is not an arbitrary convex floor footprint.
- `DEBUG` adds evaluated rectangle pairs and local road-aligned geometry/transform. Normal search failures raise `UsableLandError`.
- Both stages are deterministic for identical validated inputs; maintain consistent project units and do not import internals from the other feature.

Sources: `usable_land/search.py`, `transform.py`, `pipeline.py`, `config.py`.
