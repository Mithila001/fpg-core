from __future__ import annotations

from ....domain import RoomType
from ...model import ModelContext
from ..base import ConstraintSettings, require_room_types
from .h_hallway_shared_wall import _interval_overlap


class HallwayParallelOverlapConstraint:
    """Cap projected overlap of parallel hallway pairs, including offset pairs."""

    key = "hallway_parallel_overlap"

    def apply(self, context: ModelContext, settings: ConstraintSettings) -> None:
        types = set(require_room_types(settings.get("hallway_room_types", (RoomType.HALLWAY,)), "hallway_parallel_overlap.hallway_room_types"))
        horizontal_cap = context.problem.scale.maximum_length(float(settings.get("horizontal_max_overlap", 40)))
        vertical_cap = context.problem.scale.maximum_length(float(settings.get("vertical_max_overlap", 30)))
        hallways = [r for r in context.room_variables.values() if r.room.room_type in types]
        for i, first in enumerate(hallways):
            for second in hallways[i + 1:]:
                fh = context.model.NewBoolVar(context.new_name("horizontal", first.room.id_key))
                sh = context.model.NewBoolVar(context.new_name("horizontal", second.room.id_key))
                context.model.Add(first.width >= first.length).OnlyEnforceIf(fh)
                context.model.Add(first.width < first.length).OnlyEnforceIf(fh.Not())
                context.model.Add(second.width >= second.length).OnlyEnforceIf(sh)
                context.model.Add(second.width < second.length).OnlyEnforceIf(sh.Not())
                horizontal_pair = context.model.NewBoolVar(context.new_name("horizontal_pair"))
                context.model.AddBoolAnd([fh, sh]).OnlyEnforceIf(horizontal_pair)
                context.model.AddBoolOr([fh.Not(), sh.Not()]).OnlyEnforceIf(horizontal_pair.Not())
                vertical_pair = context.model.NewBoolVar(context.new_name("vertical_pair"))
                context.model.AddBoolAnd([fh.Not(), sh.Not()]).OnlyEnforceIf(vertical_pair)
                context.model.AddBoolOr([fh, sh]).OnlyEnforceIf(vertical_pair.Not())
                ox = _interval_overlap(context, first.x, first.x_end, second.x, second.x_end, context.problem.floor.width, "parallel_x_overlap", first, second)
                oy = _interval_overlap(context, first.y, first.y_end, second.y, second.y_end, context.problem.floor.length, "parallel_y_overlap", first, second)
                context.model.Add(ox <= horizontal_cap).OnlyEnforceIf(horizontal_pair)
                context.model.Add(ox <= horizontal_cap).OnlyEnforceIf(horizontal_pair)
                context.model.Add(oy <= vertical_cap).OnlyEnforceIf(vertical_pair)
                context.model.Add(oy <= vertical_cap).OnlyEnforceIf(vertical_pair)
