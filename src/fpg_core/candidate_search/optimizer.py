from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

import optuna

from .exceptions import CandidateSearchStateError
from .models import (
    CandidatePoint,
    CandidateSearchInput,
    CandidateSearchResult,
    CandidateSearchSettings,
    CandidateSearchTarget,
    CandidateSuggestion,
    CandidateTrialResult,
)


class CandidateSearchSession:
    """
    Incremental Optuna-backed candidate search.

    Every required non-hallway target always receives exactly one candidate
    point. For each target explicitly typed as RoomType.HALLWAY, Optuna first
    selects a hint count inside the configured range, then samples exactly that
    many hallway coordinates for the trial.

    The pipeline can ask for one unscored candidate, score it through the
    separate candidate-scoring module, record that score, temporarily run the
    floor-plan solver, and later resume this same Optuna study.
    """

    def __init__(self, search_input: CandidateSearchInput) -> None:
        if not isinstance(search_input, CandidateSearchInput):
            raise TypeError("search_input must be a CandidateSearchInput instance.")

        self._input = search_input
        self._study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(
                seed=search_input.settings.random_seed,
            ),
        )
        self._completed_trials = 0
        self._pending_trial: optuna.Trial | None = None
        self._pending_suggestion: CandidateSuggestion | None = None

    @property
    def search_input(self) -> CandidateSearchInput:
        return self._input

    @property
    def completed_trials(self) -> int:
        return self._completed_trials

    @property
    def remaining_trials(self) -> int:
        return self._input.settings.trial_count - self._completed_trials

    @property
    def has_remaining_trials(self) -> bool:
        return self.remaining_trials > 0

    @property
    def has_pending_trial(self) -> bool:
        return self._pending_trial is not None

    def ask_next_trial(self) -> CandidateSuggestion:
        """Generate exactly one unscored candidate from the current study."""

        if self.has_pending_trial:
            raise CandidateSearchStateError(
                "The current candidate trial must be scored or failed before "
                "requesting another trial."
            )
        if not self.has_remaining_trials:
            raise CandidateSearchStateError("Candidate search session has no remaining trials.")

        trial = self._study.ask()
        try:
            points = _sample_candidate_points(
                trial=trial,
                targets=self._input.targets,
                settings=self._input.settings,
            )
        except Exception:
            self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
            raise

        suggestion = CandidateSuggestion(
            trial_number=trial.number,
            points=points,
        )
        self._pending_trial = trial
        self._pending_suggestion = suggestion
        return suggestion

    def record_score(
        self,
        suggestion: CandidateSuggestion,
        score: float,
    ) -> CandidateTrialResult:
        """Record the score for the currently pending candidate trial."""

        pending_trial = self._pending_trial
        pending_suggestion = self._pending_suggestion
        if pending_trial is None or pending_suggestion is None:
            raise CandidateSearchStateError("Candidate search session has no pending trial.")
        if suggestion != pending_suggestion:
            raise ValueError("The supplied suggestion is not the pending trial.")

        numeric_score = _validate_evaluator_score(score)
        self._study.tell(pending_trial, numeric_score)
        self._completed_trials += 1
        self._pending_trial = None
        self._pending_suggestion = None

        result = CandidateTrialResult(
            trial_number=suggestion.trial_number,
            points=suggestion.points,
            score=numeric_score,
            completed_trials=self._completed_trials,
        )
        return result

    def fail_pending_trial(self) -> None:
        """Mark the current trial failed so the study is left in a valid state."""

        if self._pending_trial is None:
            return

        self._study.tell(
            self._pending_trial,
            state=optuna.trial.TrialState.FAIL,
        )
        self._pending_trial = None
        self._pending_suggestion = None

    def run_next_trial(self) -> CandidateTrialResult:
        """Convenience method using the evaluator stored in CandidateSearchInput."""

        suggestion = self.ask_next_trial()
        try:
            score = self._input.evaluator(suggestion.points)
            return self.record_score(suggestion, score)
        except Exception:
            self.fail_pending_trial()
            raise

    def best_result(self) -> CandidateSearchResult:
        """Return the highest-scoring completed trial seen by this session."""

        if self._completed_trials <= 0:
            raise CandidateSearchStateError("Candidate search session has no completed trials.")

        best_trial = self._study.best_trial
        if best_trial.value is None:
            raise CandidateSearchStateError("The best Optuna trial does not contain a score.")

        return CandidateSearchResult(
            points=_points_from_trial_parameters(
                targets=self._input.targets,
                settings=self._input.settings,
                parameters=best_trial.params,
            ),
            score=float(best_trial.value),
            completed_trials=self._completed_trials,
        )


def search_candidates(search_input: CandidateSearchInput) -> CandidateSearchResult:
    """
    Run the full configured candidate search and return its best result.

    This batch API remains backward compatible. New orchestration that needs to
    pause and resume should use CandidateSearchSession directly.
    """

    session = CandidateSearchSession(search_input)
    while session.has_remaining_trials:
        session.run_next_trial()
    return session.best_result()


def _sample_candidate_points(
    trial: optuna.Trial,
    targets: tuple[CandidateSearchTarget, ...],
    settings: CandidateSearchSettings,
) -> tuple[CandidatePoint, ...]:
    max_x_index = _maximum_grid_index(
        minimum=settings.min_x,
        maximum=settings.max_x,
        resolution=settings.grid_resolution,
    )
    max_y_index = _maximum_grid_index(
        minimum=settings.min_y,
        maximum=settings.max_y,
        resolution=settings.grid_resolution,
    )

    points: list[CandidatePoint] = []
    for target_index, target in enumerate(targets):
        hint_count = _sample_target_hint_count(
            trial=trial,
            target_index=target_index,
            target=target,
            settings=settings,
        )

        for zero_based_hint_index in range(hint_count):
            hint_index = zero_based_hint_index + 1
            x_index = trial.suggest_int(
                name=_x_parameter_name(
                    target_index=target_index,
                    hint_index=hint_index,
                    is_hallway=target.is_hallway,
                ),
                low=0,
                high=max_x_index,
            )
            y_index = trial.suggest_int(
                name=_y_parameter_name(
                    target_index=target_index,
                    hint_index=hint_index,
                    is_hallway=target.is_hallway,
                ),
                low=0,
                high=max_y_index,
            )
            points.append(
                CandidatePoint(
                    room_id=target.room_id,
                    room_type=target.room_type,
                    hint_index=hint_index,
                    x=_grid_value(
                        minimum=settings.min_x,
                        index=x_index,
                        resolution=settings.grid_resolution,
                    ),
                    y=_grid_value(
                        minimum=settings.min_y,
                        index=y_index,
                        resolution=settings.grid_resolution,
                    ),
                )
            )

    return tuple(points)


def _sample_target_hint_count(
    *,
    trial: optuna.Trial,
    target_index: int,
    target: CandidateSearchTarget,
    settings: CandidateSearchSettings,
) -> int:
    if not target.is_hallway:
        return 1

    return trial.suggest_int(
        name=_hallway_count_parameter_name(target_index),
        low=settings.min_hallway_hint_count,
        high=settings.max_hallway_hint_count,
    )


def _points_from_trial_parameters(
    targets: tuple[CandidateSearchTarget, ...],
    settings: CandidateSearchSettings,
    parameters: Mapping[str, int | float],
) -> tuple[CandidatePoint, ...]:
    points: list[CandidatePoint] = []

    for target_index, target in enumerate(targets):
        hint_count = _hint_count_from_trial_parameters(
            target_index=target_index,
            target=target,
            settings=settings,
            parameters=parameters,
        )

        for zero_based_hint_index in range(hint_count):
            hint_index = zero_based_hint_index + 1
            x_parameter_name = _x_parameter_name(
                target_index=target_index,
                hint_index=hint_index,
                is_hallway=target.is_hallway,
            )
            y_parameter_name = _y_parameter_name(
                target_index=target_index,
                hint_index=hint_index,
                is_hallway=target.is_hallway,
            )

            if x_parameter_name not in parameters:
                raise CandidateSearchStateError(
                    "Best trial is missing the X parameter for "
                    f"room '{target.room_id}', hint {hint_index}."
                )
            if y_parameter_name not in parameters:
                raise CandidateSearchStateError(
                    "Best trial is missing the Y parameter for "
                    f"room '{target.room_id}', hint {hint_index}."
                )

            x_index = _validated_parameter_index(
                parameter_name=x_parameter_name,
                value=parameters[x_parameter_name],
            )
            y_index = _validated_parameter_index(
                parameter_name=y_parameter_name,
                value=parameters[y_parameter_name],
            )

            points.append(
                CandidatePoint(
                    room_id=target.room_id,
                    room_type=target.room_type,
                    hint_index=hint_index,
                    x=_grid_value(
                        minimum=settings.min_x,
                        index=x_index,
                        resolution=settings.grid_resolution,
                    ),
                    y=_grid_value(
                        minimum=settings.min_y,
                        index=y_index,
                        resolution=settings.grid_resolution,
                    ),
                )
            )

    return tuple(points)


def _hint_count_from_trial_parameters(
    *,
    target_index: int,
    target: CandidateSearchTarget,
    settings: CandidateSearchSettings,
    parameters: Mapping[str, int | float],
) -> int:
    if not target.is_hallway:
        return 1

    parameter_name = _hallway_count_parameter_name(target_index)
    if parameter_name not in parameters:
        raise CandidateSearchStateError(
            f"Best trial is missing the hallway hint count for room '{target.room_id}'."
        )

    hint_count = _validated_parameter_index(
        parameter_name=parameter_name,
        value=parameters[parameter_name],
    )
    if not (
        settings.min_hallway_hint_count
        <= hint_count
        <= settings.max_hallway_hint_count
    ):
        raise CandidateSearchStateError(
            f"Trial parameter '{parameter_name}' is outside the configured "
            "hallway hint-count range."
        )

    return hint_count


def _validate_evaluator_score(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("Candidate evaluator must return a numeric score, not boolean.")

    try:
        numeric_score = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise TypeError("Candidate evaluator must return a numeric score.") from exc

    if not math.isfinite(numeric_score):
        raise ValueError("Candidate evaluator returned a non-finite score.")

    return numeric_score


def _validated_parameter_index(parameter_name: str, value: int | float) -> int:
    if isinstance(value, bool):
        raise CandidateSearchStateError(
            f"Trial parameter '{parameter_name}' contains a boolean value."
        )

    numeric_value = float(value)
    if not numeric_value.is_integer():
        raise CandidateSearchStateError(
            f"Trial parameter '{parameter_name}' is not an integer index."
        )

    index = int(numeric_value)
    if index < 0:
        raise CandidateSearchStateError(
            f"Trial parameter '{parameter_name}' contains a negative index."
        )

    return index


def _maximum_grid_index(minimum: float, maximum: float, resolution: float) -> int:
    minimum_decimal = Decimal(str(minimum))
    maximum_decimal = Decimal(str(maximum))
    resolution_decimal = Decimal(str(resolution))
    return int((maximum_decimal - minimum_decimal) // resolution_decimal)


def _grid_value(minimum: float, index: int, resolution: float) -> float:
    minimum_decimal = Decimal(str(minimum))
    resolution_decimal = Decimal(str(resolution))
    return float(minimum_decimal + Decimal(index) * resolution_decimal)


def _hallway_count_parameter_name(target_index: int) -> str:
    return f"candidate_{target_index}_hallway_hint_count"


def _x_parameter_name(
    *,
    target_index: int,
    hint_index: int,
    is_hallway: bool,
) -> str:
    if is_hallway:
        return f"candidate_{target_index}_hallway_{hint_index}_x_index"
    return f"candidate_{target_index}_x_index"


def _y_parameter_name(
    *,
    target_index: int,
    hint_index: int,
    is_hallway: bool,
) -> str:
    if is_hallway:
        return f"candidate_{target_index}_hallway_{hint_index}_y_index"
    return f"candidate_{target_index}_y_index"
