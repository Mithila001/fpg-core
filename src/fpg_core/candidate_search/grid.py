from __future__ import annotations

from ..domain import CandidateSearchSpace, ResolvedCandidateGrid


def build_candidate_grid(
    *,
    search_space: CandidateSearchSpace,
    max_grid_node_count: int,
) -> ResolvedCandidateGrid:
    """Build the exact centered grid prepared by preprocessing."""

    if not isinstance(search_space, CandidateSearchSpace):
        raise TypeError("search_space must be a CandidateSearchSpace instance.")
    if isinstance(max_grid_node_count, bool) or not isinstance(
        max_grid_node_count, int
    ):
        raise TypeError("max_grid_node_count must be an integer.")
    if max_grid_node_count < 9:
        raise ValueError("max_grid_node_count must be at least 9.")

    grid = ResolvedCandidateGrid(
        x_positions=search_space.x_positions(),
        y_positions=search_space.y_positions(),
    )
    if grid.node_count > max_grid_node_count:
        raise ValueError(
            "Resolved candidate grid contains "
            f"{grid.node_count} nodes, exceeding max_grid_node_count="
            f"{max_grid_node_count}."
        )
    return grid
