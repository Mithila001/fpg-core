"""Candidate-flow scenario shared with the full-flow experiment."""

import importlib.util
from pathlib import Path

FULL_FLOW = Path(__file__).resolve().parents[1] / "full_flow"
SPEC = importlib.util.spec_from_file_location(
    "full_flow_scenario", FULL_FLOW / "scenario.py"
)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Cannot load shared scenario from {FULL_FLOW}")
_scenario = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(_scenario)

build_candidate_circulation_config = _scenario.build_candidate_circulation_config
build_candidate_scoring_config = _scenario.build_candidate_scoring_config
build_candidate_search_config = _scenario.build_candidate_search_config
build_preprocessing_config = _scenario.build_preprocessing_config
build_preprocessing_request = _scenario.build_preprocessing_request

__all__ = [
    "build_candidate_circulation_config",
    "build_candidate_scoring_config",
    "build_candidate_search_config",
    "build_preprocessing_config",
    "build_preprocessing_request",
]
