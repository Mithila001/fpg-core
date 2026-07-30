from __future__ import annotations

from .contracts import PreparedGenerationInput, PreprocessingInput
from .pipeline import run_pipeline


def prepare_generation_input(
    input: PreprocessingInput,
) -> PreparedGenerationInput:
    """Prepare one trusted generation specification without external side effects."""

    return run_pipeline(input)
