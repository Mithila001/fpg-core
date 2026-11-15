from __future__ import annotations

from typing import Any

from ..model import ModelContext, RoomVariables


def _and(context: ModelContext, parts: list[Any]) -> Any:
    result = context.model.NewBoolVar(context.new_name("exposure_and"))
    context.model.AddBoolAnd(parts).OnlyEnforceIf(result)
    context.model.AddBoolOr([part.Not() for part in parts]).OnlyEnforceIf(result.Not())
    return result


def _or(context: ModelContext, parts: list[Any]) -> Any:
    result = context.model.NewBoolVar(context.new_name("exposure_or"))
    context.model.AddBoolOr(parts).OnlyEnforceIf(result)
    context.model.AddBoolAnd([part.Not() for part in parts]).OnlyEnforceIf(result.Not())
    return result


def _le(context: ModelContext, left: Any, right: Any) -> Any:
    result = context.model.NewBoolVar(context.new_name("exposure_le"))
    context.model.Add(left <= right).OnlyEnforceIf(result)
    context.model.Add(left >= right + 1).OnlyEnforceIf(result.Not())
    return result


def exposure_literal(
    context: ModelContext, room: RoomVariables, side: str, minimum: int | None = None
) -> Any:
    """Exactly reify full-wall or continuous-segment outward exposure."""
    key = (room.room.id_key, side, minimum)
    if key in context.exposure_cache:
        return context.exposure_cache[key]
    horizontal = side in ("front", "back")
    if side not in ("front", "back", "left", "right"):
        raise ValueError(f"Unknown exposure side: {side}")
    start, end = (room.x, room.x_end) if horizontal else (room.y, room.y_end)
    blockers = []
    for other in context.room_variables.values():
        if other is room:
            continue
        blocker_key = (room.room.id_key, other.room.id_key, side)
        cached = context.exposure_blocker_cache.get(blocker_key)
        if cached is not None:
            blockers.append(cached)
            continue
        a, b = (other.x, other.x_end) if horizontal else (other.y, other.y_end)
        before, after = {
            "front": (other.y_end, room.y),
            "back": (room.y_end, other.y),
            "left": (other.x_end, room.x),
            "right": (room.x_end, other.x),
        }[side]
        outward = _and(context, [other.present, _le(context, before, after)])
        blocker = (a, b, outward)
        context.exposure_blocker_cache[blocker_key] = blocker
        blockers.append(blocker)
    # ponytail: O(n²) candidates for partial walls; use a sweep formulation if room counts grow.
    starts = [start] if minimum is None else [start] + [b for _, b, _ in blockers]
    candidates = []
    for candidate in starts:
        segment_end = end if minimum is None else candidate + minimum
        parts = [room.present]
        if minimum is not None:
            parts.extend(
                [_le(context, start, candidate), _le(context, segment_end, end)]
            )
        for a, b, outward in blockers:
            if minimum is not None and candidate is b:
                continue
            parts.append(
                _or(
                    context,
                    [
                        outward.Not(),
                        _le(context, b, candidate),
                        _le(context, segment_end, a),
                    ],
                )
            )
        candidates.append(_and(context, parts))
    result = _or(context, candidates)
    context.exposure_cache[key] = result
    return result
