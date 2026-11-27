# Geometry Analysis

This feature measures physical geometry without scoring policy, a generation specification, or post-processing. Scoring consumes it; post-processing can use it independently when selecting its own physical rooms, including solver placeholders. The caller retains room IDs and chooses the polygons included in each operation. No input floor plan is modified and there is no cache.

## Public API

Import the following from `fpg_core.geometry_analysis`:

- `room_polygon(points)` constructs a Shapely `Polygon` from an iterable of `(x, y)` coordinates. For a canonical domain polygon use `((p.x, p.y) for p in room.boundary.points)`. Its `.area` and `.centroid` provide the room measurements.
- `occupied_footprint(polygons)` unions the supplied Shapely geometries.
- `shared_boundary(first, second)` returns the intersection of the two boundaries; its `.length` distinguishes wall contact from zero-length corner contact. It also measures contact between a region and a room. `boundary_distance(first, second)` measures the distance between their boundaries.
- `is_rectilinear(points, tolerance)` checks successive coordinate pairs, including the closing edge.
- `detect_voids(footprint)` returns a tuple of Shapely polygons for interior rings, with area available as `.area`; it applies no scoring threshold.
- `exterior_profile(footprint, direction)` measures the exact outward silhouette of a rectilinear footprint for `front` (negative y), `back` (positive y), `left` (negative x), or `right` (positive x). It returns an `ExteriorProfile` with `segments` and transitions in `steps`; empty intervals are not bridged. Segment coordinates are projected onto x for front/back and y for left/right. A step contains its location, depth, geometry and neighboring segments. The caller decides whether a step is undesirable.
- `directional_exposure(room, others, direction)` measures the room's outward-visible silhouette, subtracting projected obstructions even at a distance. `others` maps room ID strings to polygons and must exclude the room itself. Its `DirectionalExposure` reports total and longest continuous exposed lengths, exposed and obstructed line segments, blocking IDs, and full exposure. Continuous segments must occupy the same physical straight wall, even when separate walls project to adjacent intervals. The input polygons must be non-overlapping and rectilinear; the routine does not validate them.
- `measure_room_shape(polygon)` returns `RoomShapeMeasurements`: bounding width and height, boundary edge lengths, horizontal and vertical cross-section lengths at each vertex interval, and the concave-corner count. It assumes a simple rectilinear room polygon without holes. These are measurements, not suitability decisions.
- `detect_recesses(footprint, tolerance, *, include_section_entrances=False)` returns a tuple of `Recess` objects. It uses the existing orthogonal directional sweep, treating interior rings as voids. Set `include_section_entrances=True` to compute section entrances independently of scoring mode.
- `polygons(geometry)` and `lines(geometry)` recursively extract polygon and line components.

`Recess` exposes `polygon`, `entrance`, `direction`, `depth`, `sections`, and `branch_count`. `Section` exposes `polygon`, `width`, `depth`, `level`, `parents` (indices into the recess sections), `direction`, and `entrance` (possibly `None`). Region area and entrance width are available on the Shapely geometries. Results are mutable dataclasses and must be treated as caller-owned.

The API intentionally exposes Shapely geometries: inputs and outputs use the caller's consistent project units, lengths and tolerances use those units, and areas use square units. No unit conversion or validity repair is performed. Invalid inputs and Shapely operation failures propagate to the caller; do not interpret a failure as a zero measurement. The sweep is intended for rectilinear footprints.

## Usage example

```python
from fpg_core.geometry_analysis import occupied_footprint, room_polygon, detect_voids

room = room_polygon(((0, 0), (10, 0), (10, 10), (0, 10)))
footprint = occupied_footprint([room])
voids = detect_voids(footprint)
```

## Public export inventory

### `fpg_core.geometry_analysis` exports (19)

| Export | Contract |
| --- | --- |
| `DirectionalExposure` | `exposed_length`, `longest_exposed_segment`, `exposed`, `obstructed`, `obstructing_room_ids`, `full_exposure` |
| `ExteriorProfile` | `direction`, `segments`, `steps` |
| `ExteriorWallSegment` | `start`, `end`, `position`, `geometry`, `length` |
| `ExteriorWallStep` | `location`, `depth`, `geometry`, `before`, `after` |
| `exterior_profile` | `footprint`, `direction` |
| `Recess` | `polygon`, `entrance`, `direction`, `depth`, `sections`, `branch_count` |
| `RoomShapeMeasurements` | `width`, `height`, `edge_lengths`, `horizontal_widths`, `vertical_widths`, `concave_corners` |
| `Section` | `polygon`, `width`, `depth`, `level`, `parents`, `direction`, `entrance` |
| `boundary_distance` | `first`, `second` |
| `detect_recesses` | `footprint`, `tolerance`, `include_section_entrances` |
| `detect_voids` | `footprint` |
| `directional_exposure` | `room`, `others`, `direction` |
| `is_rectilinear` | `points`, `tolerance` |
| `lines` | `geometry` |
| `measure_room_shape` | `polygon` |
| `occupied_footprint` | `polygons` |
| `polygons` | `geometry` |
| `room_polygon` | `points` |
| `shared_boundary` | `first`, `second` |
