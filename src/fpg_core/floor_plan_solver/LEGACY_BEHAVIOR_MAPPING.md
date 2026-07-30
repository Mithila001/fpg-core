# Legacy Behavior Mapping

This file records how the old `fpg_rooms` behavior maps to the clean solver
package. It is not a compatibility promise; it is a migration checklist.

| Legacy behavior | New location | Status |
|---|---|---|
| Room coordinate, size, end, interval, and area variables | `model.py` | Implemented |
| Room containment | `model.py` core invariants | Implemented |
| Global non-overlap | `model.py` core invariants | Implemented |
| Mandatory room activation | `model.py` | Implemented; optional rooms removed |
| Aspect-ratio bounds | `constraints/hard/aspect_ratio.py` | Implemented and profile-configurable |
| Hard AND/OR adjacency | `constraints/hard/room_relations.py` | Implemented using room IDs |
| Soft adjacency | `constraints/soft/room_relations.py` | Implemented and connected to objective |
| Minimum floor coverage | `constraints/hard/minimum_coverage.py` | Implemented |
| Hallway-to-living and hallway-to-destination contact | `constraints/hard/hallway_connectivity.py` | Implemented |
| Living/veranda front ordering | `constraints/hard/front_anchor.py` | Implemented generically |
| Veranda front-boundary pinning | `constraints/hard/boundary_placement.py` | Implemented generically |
| Room size hierarchy | `constraints/hard/room_size_hierarchy.py` | Implemented; ratios must be configured |
| Candidate point hints | `preparation.py` + `model.py` | Implemented by room ID |
| Existing-layout hints and bounded refinement | `preparation.py` + `model.py` | Implemented |
| Center/front compactness | `constraints/soft/center_proximity.py` | Implemented |
| Bounding-box dead space | `constraints/soft/dead_space.py` | Implemented |
| Bathroom depth preference | `constraints/soft/bathroom_depth.py` | Implemented |
| Seed movement/size stability | `constraints/soft/seed_stability.py` | Implemented |
| Generation/refinement control panels | `profiles.py` | Replaced by immutable generation profiles |
| Solver execution and status mapping | `runner.py` | Implemented |
| `list[dict]` output | `extractor.py` | Replaced by shared `FloorPlan` |
| Automatic living-room creation | Specification-building layer | Intentionally outside solver |
| Automatic hallway creation | Specification-building layer | Intentionally outside solver |
| Extender activation and wall attachment | Not included | Deferred; current usage should be confirmed first |
| Veranda auxiliary outdoor-space room | Not included | Deferred; behavior is too domain-specific to copy implicitly |
| Garage frontage/access path logic | Not included | Deferred pending confirmed desired rule |
| Envelope staircase/setback behavior | Not included | Deferred pending confirmed desired rule and data contract |
| Shared-wall count by room type | Not included | Deferred pending rule calibration |
| Kitchen/hallway back-wall setback | Not included | Deferred pending confirmed business requirement |
| Seed facade depth/alignment penalties | Not included | Deferred; refinement scoring behavior needs confirmation |
| Recessed facade penalty | Not included | Deferred; refinement scoring behavior needs confirmation |

Before deleting the old package, add and validate any deferred rule that remains
part of the active generation behavior. Each should be introduced as one
independent registered constraint with profile-owned configuration.
