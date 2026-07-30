# Legacy Opening Behavior Mapping

This mapping records how active `fpg_opening_v2` behavior informs the clean
opening module. It is a migration aid, not a promise to preserve legacy bugs.

| Legacy behavior | Clean implementation | Status |
|---|---|---|
| Interior candidates require 10 units of shared wall | Profile-owned minimum applied to analyzed shared spans | Preserved |
| Preferred door width is 8 units | Typed dimension configuration | Preserved |
| Windows require a full 16-unit wall span | Typed dimension configuration | Preserved |
| Hallway relationships and configured room pairs are eligible | Interior-door feature using `RoomType` and room IDs | Preserved |
| Attached bathrooms connect only to bedrooms | Feature eligibility plus one-to-one model constraint | Preserved |
| Bedroom has one social door or two with an attached bathroom | Conditional room-incidence constraint | Preserved |
| Attached-bathroom, bathroom/hallway, and hallway access are prioritized | Bounded objective tiers | Preserved |
| Living/veranda door becomes the main entrance | Two-room opening with `MAIN_ENTRANCE` purpose | Preserved |
| Otherwise main entrance prefers living room and south/east/north/west | Exterior-door options and preference rank | Preserved |
| Secondary entrance prefers kitchen, hallway, then north/lateral/south | Exterior-door options and preference rank | Preserved |
| One window is attempted for bedroom, living, kitchen, and dining rooms | One optional window demand per eligible room | Preserved |
| Effective window order is east/north/south/west | Profile-owned side priority | Preserved |
| Windows keep 5 units from doors/windows | Shared physical-wall spacing constraint | Preserved and generalized |
| Missing openings disappear silently | Structured `no_candidate` or `not_selected` issue | Corrected |
| Features run sequentially | All feature decisions share one CP-SAT model | Replaced |
| Openings are always centered | Centering is a low-priority preference; positions may move to share wall capacity | Improved |
| Exterior detection means “no overlapping room edge” | Exterior spans must overlap the real floor boundary | Corrected |
| Any overlap makes an entire edge interior | Edges are noded and classified as atomic/merged spans | Corrected |
| Door-door conflicts can survive sequential selection | Global wall non-overlap is structural | Corrected |
| Rooms and connections use names | Stable `RoomId` references | Replaced |
| Main-door promotion mutates an existing opening | Purpose is assigned before model construction | Corrected |
| Result holds the original room objects | Successful output is a deep copy | Corrected |
| `FpgRequirements` is accepted but unused | Not part of the typed opening API | Removed |
| Exterior doors shrink to short non-zero wall spans | Preserved with an `undersized_exterior_door` diagnostic | Preserved for first version |
| Existing openings may be ignored or conflicted | Non-empty input openings are rejected clearly | Deferred preservation support |
| Runtime service returns legacy `OpeningData` | No runtime adapter or integration in this task | Deferred |

Before removing `fpg_opening_v2`, the future pipeline migration must add the
new stage after clean post-processing, update scoring/serialization consumers,
compare representative plans, and then delete legacy imports and payloads.
