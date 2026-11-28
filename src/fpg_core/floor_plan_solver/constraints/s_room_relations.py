from __future__ import annotations

import math

from ..exceptions import InvalidProfileError
from ..model import ModelContext
from .base import PENALTY_MAX, ConstraintSettings, ceil_ratio
from .geometry import (
    adjacency_literal,
    exact_or_literal,
    violation_when_present,
)


class SoftRoomRelationsConstraint:
    key = "room_relations"

    def build_penalty(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ):
        overlap = settings.get("minimum_overlap", 0.6)
        if (
            type(overlap) not in (float, int)
            or overlap <= 0
            or not math.isfinite(overlap)
        ):
            raise InvalidProfileError(
                "room_relations.minimum_overlap must be positive and finite"
            )
        minimum_overlap = max(1, context.problem.scale.minimum_length(overlap))
        penalties = []

        for relation_index, relation in enumerate(context.problem.relations):
            if relation.strength != "soft":
                continue

            source = context.variables_for(relation.source_id_key)
            options = [
                adjacency_literal(
                    context,
                    source,
                    context.variables_for(target_id),
                    minimum_overlap,
                )
                for target_id in relation.target_id_keys
            ]

            name = f"soft_relation_{relation_index}"
            if relation.match_policy == "and":
                satisfied = exact_or_literal(
                    context, [option.Not() for option in options], name
                ).Not()
            else:
                satisfied = exact_or_literal(context, options, name)
            penalties.append(
                violation_when_present(
                    context,
                    satisfied,
                    source.present,
                    f"soft_relation_miss_{relation_index}",
                )
            )
        if not penalties:
            return 0
        return ceil_ratio(
            context, PENALTY_MAX * sum(penalties), len(penalties), PENALTY_MAX
        )
