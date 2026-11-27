"""Shared preparation for refinement from an existing floor plan."""

from dataclasses import replace

from fpg_core.floor_plan_solver import SeedSource


def refinement_profile(config):
    profile = config.floor_plan_solver.refinement_a
    return replace(profile, seed=replace(
        profile.seed, source=SeedSource.EXISTING_FLOOR_PLAN, require_source=True
    ))
