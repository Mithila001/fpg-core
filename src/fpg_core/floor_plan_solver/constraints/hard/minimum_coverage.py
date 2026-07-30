from __future__ import annotations

import math

from ...exceptions import InvalidProfileError
from ...model import ModelContext
from ..base import ConstraintSettings


class MinimumCoverageConstraint:
    key = "minimum_coverage"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        ratio = float(settings.get("ratio", 0.0))
        if not 0 <= ratio <= 1:
            raise InvalidProfileError("minimum_coverage.ratio must be in [0, 1]")
        if ratio == 0:
            return

        required_area = int(math.ceil(context.problem.floor.area * ratio))
        context.model.Add(
            sum(room.area for room in context.room_variables.values())
            >= required_area
        )
