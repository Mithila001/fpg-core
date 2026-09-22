from __future__ import annotations

from ..domain import ResolvedCandidateGrid


def build_candidate_grid(
    *,
    grid: ResolvedCandidateGrid,
    max_grid_node_count: int,
) -> ResolvedCandidateGrid:
    """Validate and return the exact grid prepared by preprocessing.

    The historical function name is retained for API stability. Candidate Search
    no longer creates X/Y positions from dimensions or spacing.
    """

    if not isinstance(grid, ResolvedCandidateGrid):
        raise TypeError("grid must be a ResolvedCandidateGrid instance.")
    if isinstance(max_grid_node_count, bool) or not isinstance(
        max_grid_node_count, int
    ):
        raise TypeError("max_grid_node_count must be an integer.")
    if max_grid_node_count < 9:
        raise ValueError("max_grid_node_count must be at least 9.")

    if grid.node_count > max_grid_node_count:
        raise ValueError(
            "Prepared candidate grid contains "
            f"{grid.node_count} nodes, exceeding max_grid_node_count="
            f"{max_grid_node_count}."
        )
    if grid.interior_node_count < 1:
        raise ValueError(
            "Prepared candidate grid must contain at least one non-edge "
            "hint-point node."
        )
    return grid
