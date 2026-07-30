from __future__ import annotations

from typing import Any, Iterable

from ..model import ModelContext, RoomVariables


def adjacency_literal(
    context: ModelContext,
    first: RoomVariables,
    second: RoomVariables,
    minimum_overlap: int,
) -> Any:
    """Return a reusable literal meaning that two rooms share a wall segment.

    The literal is intentionally one-way reified: when true, valid contact is
    enforced. Hard constraints force it true; soft objectives are incentivized
    to make it true. This avoids unnecessary reverse-reification complexity.
    """

    if first.room.id_key == second.room.id_key:
        raise ValueError("A room cannot be adjacent to itself")

    pair = tuple(sorted((first.room.id_key, second.room.id_key)))
    key = (pair[0], pair[1], minimum_overlap)
    cached = context.adjacency_cache.get(key)
    if cached is not None:
        return cached

    model = context.model
    adjacent = model.NewBoolVar(context.new_name("adjacent", pair[0], pair[1]))
    model.AddImplication(adjacent, first.present)
    model.AddImplication(adjacent, second.present)

    side_literals = []

    first_right = model.NewBoolVar(context.new_name("touch_right", *pair))
    model.Add(first.x_end == second.x).OnlyEnforceIf(first_right)
    model.Add(first.y + minimum_overlap <= second.y_end).OnlyEnforceIf(first_right)
    model.Add(second.y + minimum_overlap <= first.y_end).OnlyEnforceIf(first_right)
    side_literals.append(first_right)

    first_left = model.NewBoolVar(context.new_name("touch_left", *pair))
    model.Add(first.x == second.x_end).OnlyEnforceIf(first_left)
    model.Add(first.y + minimum_overlap <= second.y_end).OnlyEnforceIf(first_left)
    model.Add(second.y + minimum_overlap <= first.y_end).OnlyEnforceIf(first_left)
    side_literals.append(first_left)

    first_back = model.NewBoolVar(context.new_name("touch_back", *pair))
    model.Add(first.y_end == second.y).OnlyEnforceIf(first_back)
    model.Add(first.x + minimum_overlap <= second.x_end).OnlyEnforceIf(first_back)
    model.Add(second.x + minimum_overlap <= first.x_end).OnlyEnforceIf(first_back)
    side_literals.append(first_back)

    first_front = model.NewBoolVar(context.new_name("touch_front", *pair))
    model.Add(first.y == second.y_end).OnlyEnforceIf(first_front)
    model.Add(first.x + minimum_overlap <= second.x_end).OnlyEnforceIf(first_front)
    model.Add(second.x + minimum_overlap <= first.x_end).OnlyEnforceIf(first_front)
    side_literals.append(first_front)

    for side in side_literals:
        model.AddImplication(side, adjacent)
    model.AddBoolOr(side_literals).OnlyEnforceIf(adjacent)

    context.adjacency_cache[key] = adjacent
    return adjacent


def exact_or_literal(
    context: ModelContext,
    literals: Iterable[Any],
    name: str,
) -> Any:
    options = tuple(literals)
    result = context.model.NewBoolVar(context.new_name(name))
    if not options:
        context.model.Add(result == 0)
        return result

    context.model.AddBoolOr(list(options)).OnlyEnforceIf(result)
    for option in options:
        context.model.AddImplication(option, result)
    return result


def violation_when_present(
    context: ModelContext,
    satisfied: Any,
    present: Any,
    name: str,
) -> Any:
    violation = context.model.NewBoolVar(context.new_name(name))
    context.model.Add(violation + satisfied == 1).OnlyEnforceIf(present)
    context.model.Add(violation == 0).OnlyEnforceIf(present.Not())
    return violation


def active_linear_penalty(
    context: ModelContext,
    expression: Any,
    upper_bound: int,
    present: Any,
    name: str,
) -> Any:
    penalty = context.model.NewIntVar(
        0, max(0, upper_bound), context.new_name(name)
    )
    context.model.Add(penalty == expression).OnlyEnforceIf(present)
    context.model.Add(penalty == 0).OnlyEnforceIf(present.Not())
    return penalty


def priority_selection_literals(
    context: ModelContext,
    candidates: Iterable[RoomVariables],
    name: str,
) -> tuple[tuple[RoomVariables, Any], ...]:
    """Select the first present room from an ordered candidate sequence."""

    selected: list[tuple[RoomVariables, Any]] = []
    prior: list[RoomVariables] = []
    for candidate in candidates:
        literal = context.model.NewBoolVar(
            context.new_name(name, candidate.room.id_key)
        )
        context.model.Add(literal <= candidate.present)
        for previous in prior:
            context.model.Add(literal + previous.present <= 1)

        if prior:
            context.model.Add(
                literal >= candidate.present - sum(item.present for item in prior)
            )
        else:
            context.model.Add(literal == candidate.present)

        selected.append((candidate, literal))
        prior.append(candidate)

    return tuple(selected)
