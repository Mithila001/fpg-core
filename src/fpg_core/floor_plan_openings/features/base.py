from __future__ import annotations

from typing import Protocol

from ..config import FloorPlanOpeningsConfig
from ..domain import OpeningDemand, PreparedFloorPlan


class OpeningFeature(Protocol):
    feature_id: str

    def build_demands(
        self,
        prepared: PreparedFloorPlan,
        config: FloorPlanOpeningsConfig,
    ) -> tuple[OpeningDemand, ...]: ...
