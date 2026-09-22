from __future__ import annotations

from time import perf_counter

from ..domain import ExecutionMetadata, ExecutionMode, FeatureExecution
from .contracts import PreprocessingExecution, PreprocessingInput
from .pipeline import run_pipeline

__all__ = [
    "prepare_generation_input",
]


def prepare_generation_input(
    input: PreprocessingInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> PreprocessingExecution:
    """Prepare one trusted generation specification without external side effects.

    PRODUCTION returns only the normal result. DEBUG additionally returns the
    feature-specific preprocessing report through ``execution.details``.
    """

    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance")

    started_at = perf_counter()
    result, details = run_pipeline(
        input,
        collect_details=mode is ExecutionMode.DEBUG,
    )
    duration_seconds = perf_counter() - started_at

    return FeatureExecution(
        result=result,
        details=details,
        metadata=ExecutionMetadata(
            mode=mode,
            duration_seconds=duration_seconds,
        ),
    )
