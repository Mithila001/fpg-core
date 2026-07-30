from __future__ import annotations

from .hard import (
    AspectRatioConstraint,
    AttachedBathroomPairingConstraint,
    BackExposureConstraint,
    BoundaryPlacementConstraint,
    FrontAnchorConstraint,
    GaragePlacementConstraint,
    HallwayConnectivityConstraint,
    HallwayDimensionsConstraint,
    HardRoomRelationsConstraint,
    MinimumCoverageConstraint,
    RoomSizeHierarchyConstraint,
)
from .registry import ConstraintRegistry
from .soft import (
    BathroomDepthConstraint,
    DeadSpaceConstraint,
    FloorClusterPositionConstraint,
    KitchenBackExposureConstraint,
    SeedStabilityConstraint,
    SoftRoomRelationsConstraint,
)


def build_default_registry() -> ConstraintRegistry:
    registry = ConstraintRegistry()

    registry.register_hard(AspectRatioConstraint())
    registry.register_hard(AttachedBathroomPairingConstraint())
    registry.register_hard(BackExposureConstraint())
    registry.register_hard(HardRoomRelationsConstraint())
    registry.register_hard(MinimumCoverageConstraint())
    registry.register_hard(HallwayConnectivityConstraint())
    registry.register_hard(HallwayDimensionsConstraint())
    registry.register_hard(FrontAnchorConstraint())
    registry.register_hard(GaragePlacementConstraint())
    registry.register_hard(BoundaryPlacementConstraint())
    registry.register_hard(RoomSizeHierarchyConstraint())

    registry.register_soft(SoftRoomRelationsConstraint())
    registry.register_soft(FloorClusterPositionConstraint())
    registry.register_soft(DeadSpaceConstraint())
    registry.register_soft(KitchenBackExposureConstraint())
    registry.register_soft(SeedStabilityConstraint())
    registry.register_soft(BathroomDepthConstraint())

    return registry
