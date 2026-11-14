from __future__ import annotations

from .h_aspect_ratio import AspectRatioConstraint
from .h_back_exposure import BackExposureConstraint
from .h_boundary_placement import BoundaryPlacementConstraint
from .h_front_anchor import FrontAnchorConstraint
from .h_minimum_coverage import MinimumCoverageConstraint
from .h_room_relations import HardRoomRelationsConstraint
from .h_room_size_hierarchy import RoomSizeHierarchyConstraint
from .registry import ConstraintRegistry
from .room_specific.h_attached_bathroom_pairing import AttachedBathroomPairingConstraint
from .room_specific.h_bathroom_hallway_shared_wall import (
    BathroomHallwaySharedWallConstraint,
)
from .room_specific.h_garage_placement import GaragePlacementConstraint
from .room_specific.h_hallway_connectivity import HallwayConnectivityConstraint
from .room_specific.h_hallway_dimensions import HallwayDimensionsConstraint
from .room_specific.h_hallway_shared_wall import HallwaySharedWallConstraint
from .room_specific.s_bathroom_depth import BathroomDepthConstraint
from .room_specific.s_hallway_efficiency import HallwayEfficiencyConstraint
from .room_specific.s_kitchen_back_exposure import KitchenBackExposureConstraint
from .s_dead_space import DeadSpaceConstraint
from .s_floor_cluster_position import FloorClusterPositionConstraint
from .s_room_center_line import RoomCenterLineConstraint
from .s_room_relations import SoftRoomRelationsConstraint
from .s_room_size_relations import RoomSizeRelationsConstraint
from .s_seed_stability import SeedStabilityConstraint


def build_default_registry() -> ConstraintRegistry:
    registry = ConstraintRegistry()

    registry.register_hard(BathroomHallwaySharedWallConstraint())
    registry.register_hard(AspectRatioConstraint())
    registry.register_hard(AttachedBathroomPairingConstraint())
    registry.register_hard(BackExposureConstraint())
    registry.register_hard(HardRoomRelationsConstraint())
    registry.register_hard(MinimumCoverageConstraint())
    registry.register_hard(HallwayConnectivityConstraint())
    registry.register_hard(HallwayDimensionsConstraint())
    registry.register_hard(HallwaySharedWallConstraint())
    registry.register_hard(FrontAnchorConstraint())
    registry.register_hard(GaragePlacementConstraint())
    registry.register_hard(BoundaryPlacementConstraint())
    registry.register_hard(RoomSizeHierarchyConstraint())

    registry.register_soft(SoftRoomRelationsConstraint())
    registry.register_soft(RoomSizeRelationsConstraint())
    registry.register_soft(FloorClusterPositionConstraint())
    registry.register_soft(RoomCenterLineConstraint())
    registry.register_soft(DeadSpaceConstraint())
    registry.register_soft(HallwayEfficiencyConstraint())
    registry.register_soft(KitchenBackExposureConstraint())
    registry.register_soft(SeedStabilityConstraint())
    registry.register_soft(BathroomDepthConstraint())

    return registry
