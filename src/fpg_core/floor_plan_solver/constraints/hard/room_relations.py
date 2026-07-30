from __future__ import annotations

from ...model import ModelContext
from ..base import ConstraintSettings
from ..geometry import adjacency_literal


class HardRoomRelationsConstraint:
    key = "room_relations"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        overlap_value = float(settings.get("minimum_overlap", 0.6))
        minimum_overlap = max(
            1, context.problem.scale.minimum_length(overlap_value)
        )

        for relation in context.problem.relations:
            if relation.strength != "hard":
                continue

            source = context.variables_for(relation.source_id_key)
            adjacency_options = [
                adjacency_literal(
                    context,
                    source,
                    context.variables_for(target_id),
                    minimum_overlap,
                )
                for target_id in relation.target_id_keys
            ]

            if relation.match_policy == "and":
                for adjacent in adjacency_options:
                    context.model.Add(adjacent == 1).OnlyEnforceIf(source.present)
            else:
                context.model.AddBoolOr(
                    adjacency_options + [source.present.Not()]
                )
