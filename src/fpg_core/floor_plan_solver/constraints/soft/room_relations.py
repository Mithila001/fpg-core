from __future__ import annotations

from ...model import ModelContext
from ..base import ConstraintSettings, PenaltyTerm
from ..geometry import (
    adjacency_literal,
    exact_or_literal,
    violation_when_present,
)


class SoftRoomRelationsConstraint:
    key = "room_relations"

    def build_penalties(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> tuple[PenaltyTerm, ...]:
        minimum_overlap = max(
            1,
            context.problem.scale.minimum_length(
                float(settings.get("minimum_overlap", 0.6))
            ),
        )
        penalties: list[PenaltyTerm] = []

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

            if relation.match_policy == "and":
                for target_id, adjacent in zip(relation.target_id_keys, options):
                    violation = violation_when_present(
                        context,
                        adjacent,
                        source.present,
                        f"soft_relation_violation_{relation_index}_{target_id}",
                    )
                    penalties.append(
                        PenaltyTerm(
                            name=(
                                f"soft_relation:{relation.source_id_key}->{target_id}"
                            ),
                            expression=violation,
                        )
                    )
            else:
                satisfied = exact_or_literal(
                    context,
                    options,
                    f"soft_relation_satisfied_{relation_index}",
                )
                violation = violation_when_present(
                    context,
                    satisfied,
                    source.present,
                    f"soft_relation_violation_{relation_index}",
                )
                penalties.append(
                    PenaltyTerm(
                        name=f"soft_relation:{relation.source_id_key}->any",
                        expression=violation,
                    )
                )

        return tuple(penalties)
