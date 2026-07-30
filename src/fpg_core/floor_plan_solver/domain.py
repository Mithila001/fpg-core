"""Project-domain import seam for the CP-SAT floor-plan solver.

Only this module should import the application's shared floor-plan types. If the
shared types are moved or re-exported differently, update this file and leave
the solver internals unchanged.
"""

from ..types.floor_plan import (
    FloorPlan,
    FloorPlanRoom,
    Point,
    Polygon,
)
from ..types.floor_plan_spec import (
    ConstraintStrength,
    FloorPlanGenerationSpec,
    MatchPolicy,
    RoomId,
    RoomRelationSpec,
    RoomSpec,
    RoomType,
    RoomWidthAxis,
)

__all__ = [
    "ConstraintStrength",
    "FloorPlan",
    "FloorPlanGenerationSpec",
    "FloorPlanRoom",
    "MatchPolicy",
    "Point",
    "Polygon",
    "RoomId",
    "RoomRelationSpec",
    "RoomSpec",
    "RoomType",
    "RoomWidthAxis",
]
