from __future__ import annotations

from typing import Protocol

from ..domain import OpeningDemand, PreparedFloorPlan
from ..profiles import OpeningGenerationProfile


class OpeningFeature(Protocol):
    feature_id: str

    def build_demands(
        self,
        prepared: PreparedFloorPlan,
        profile: OpeningGenerationProfile,
    ) -> tuple[OpeningDemand, ...]: ...
