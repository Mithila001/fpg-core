from __future__ import annotations

__all__ = [
    "evaluate_candidate",
]

from ..domain import ExecutionMode
from .config import ScoringConfig
from .context import ScoringContextFactory
from .manager import CandidateScoreManager
from .registry import EvaluatorRegistry
from .types import CandidateScoringInput, ScoringResult


def evaluate_candidate(
    scoring_input: CandidateScoringInput,
    *,
    registry: EvaluatorRegistry,
    config: ScoringConfig,
    context_factory: ScoringContextFactory | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> ScoringResult:
    """Public one-shot API for candidate scoring."""

    manager = CandidateScoreManager(
        registry=registry,
        config=config,
        context_factory=context_factory,
    )
    return manager.score(scoring_input, mode=mode)
