from __future__ import annotations

from ..domain import (
    EdgeClassification,
    EdgeSetback,
    NormalizedLand,
    SetbackCalculationMode,
    SetbackProfile,
)


def resolve_setbacks(
    land: NormalizedLand,
    classifications: tuple[EdgeClassification, ...],
    profile: SetbackProfile,
) -> tuple[EdgeSetback, ...]:
    if profile.calculation_mode is not SetbackCalculationMode.BASE_PLUS_ROAD_ADJUSTMENT:
        raise ValueError("Unsupported setback calculation mode.")

    road = land.main_entry_road
    results: list[EdgeSetback] = []
    for classification in classifications:
        base = profile.base_setbacks[classification.side]
        attached = classification.edge_index == road.boundary_edge_index
        adjustment = (
            profile.road_adjustments[road.road_type][classification.side]
            if attached
            else 0
        )
        results.append(
            EdgeSetback(
                edge_index=classification.edge_index,
                side=classification.side,
                base_setback=base,
                road_adjustment=adjustment,
                final_setback=base + adjustment,
                road_type=road.road_type if attached else None,
            )
        )
    return tuple(results)
