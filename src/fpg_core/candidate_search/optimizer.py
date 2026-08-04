from __future__ import annotations

import math
from collections.abc import Mapping
from time import perf_counter
from typing import Any, cast

import optuna

from ..domain import (
    CandidateMap,
    CandidatePoint,
    ExecutionMetadata,
    ExecutionMode,
    FeatureExecution,
    ResolvedCandidateGrid,
)
from .exceptions import CandidateSearchStateError
from .grid import build_candidate_grid
from .models import (
    CandidateSearchDetails,
    CandidateSearchInput,
    CandidateSearchResult,
    CandidateSearchSettings,
    CandidateSearchTarget,
    CandidateSuggestion,
    CandidateTrialResult,
)


class CandidateSearchSession:
    """Incremental Optuna-backed adaptive-grid candidate search."""

    def __init__(self, search_input: CandidateSearchInput) -> None:
        if not isinstance(search_input, CandidateSearchInput):
            raise TypeError("search_input must be a CandidateSearchInput instance.")

        self._input = search_input
        self._grid = build_candidate_grid(
            search_input.settings.floor,
            long_axis_node_count=search_input.settings.long_axis_node_count,
            max_grid_node_count=search_input.settings.max_grid_node_count,
        )
        self._study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(
                seed=search_input.settings.random_seed,
            ),
        )
        self._completed_trials = 0
        self._overlap_rejection_count = 0
        self._pending_trial: optuna.Trial | None = None
        self._pending_suggestion: CandidateSuggestion | None = None

    @property
    def search_input(self) -> CandidateSearchInput:
        return self._input

    @property
    def grid(self) -> ResolvedCandidateGrid:
        return self._grid

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

    @property
    def overlap_rejection_count(self) -> int:
        return self._overlap_rejection_count

    @property
    def optuna_trial_count(self) -> int:
        return len(self._study.trials)

    def ask_next_trial(self) -> CandidateSuggestion:
        """Generate one valid unscored candidate, rejecting overlaps internally."""

        if self.has_pending_trial:
            raise CandidateSearchStateError(
                "The current candidate trial must be scored or failed before "
                "requesting another trial."
            )
        if not self.has_remaining_trials:
            raise CandidateSearchStateError(
                "Candidate search session has no remaining trials."
            )

        for _ in range(self._input.settings.max_internal_sampling_attempts):
            trial = self._study.ask()
            try:
                candidate = _sample_candidate_map(
                    trial=trial,
                    targets=self._input.targets,
                    settings=self._input.settings,
                    grid=self._grid,
                )
            except Exception:
                self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
                raise

            if candidate is None:
                self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
                self._overlap_rejection_count += 1
                continue

            suggestion = CandidateSuggestion(
                trial_number=trial.number,
                candidate=candidate,
            )
            self._pending_trial = trial
            self._pending_suggestion = suggestion
            return suggestion

        raise CandidateSearchStateError(
            "Candidate Search could not generate a non-overlapping candidate within "
            f"max_internal_sampling_attempts="
            f"{self._input.settings.max_internal_sampling_attempts}."
        )

    def record_score(
        self,
        suggestion: CandidateSuggestion,
        score: float,
    ) -> CandidateTrialResult:
        """Record the score for the currently pending candidate trial."""

        pending_trial = self._pending_trial
        pending_suggestion = self._pending_suggestion
        if pending_trial is None or pending_suggestion is None:
            raise CandidateSearchStateError(
                "Candidate search session has no pending trial."
            )
        if suggestion != pending_suggestion:
            raise ValueError("The supplied suggestion is not the pending trial.")

        numeric_score = _validate_evaluator_score(score)
        self._study.tell(pending_trial, numeric_score)
        self._completed_trials += 1
        self._pending_trial = None
        self._pending_suggestion = None

        return CandidateTrialResult(
            trial_number=suggestion.trial_number,
            candidate=suggestion.candidate,
            score=numeric_score,
            completed_trials=self._completed_trials,
        )

    def fail_pending_trial(self) -> None:
        """Mark the current externally evaluated trial as failed."""

        if self._pending_trial is None:
            return
        self._study.tell(
            self._pending_trial,
            state=optuna.trial.TrialState.FAIL,
        )
        self._pending_trial = None
        self._pending_suggestion = None

    def run_next_trial(self) -> CandidateTrialResult:
        """Evaluate one valid candidate using the configured callback."""

        suggestion = self.ask_next_trial()
        try:
            score = self._input.evaluator(suggestion.candidate)
            return self.record_score(suggestion, score)
        except Exception:
            self.fail_pending_trial()
            raise

    def best_result(self) -> CandidateSearchResult:
        """Return the highest-scoring completed candidate."""

        if self._completed_trials <= 0:
            raise CandidateSearchStateError(
                "Candidate search session has no completed trials."
            )
        best_trial = self._study.best_trial
        if best_trial.value is None:
            raise CandidateSearchStateError(
                "The best Optuna trial does not contain a score."
            )

        return CandidateSearchResult(
            candidate=_candidate_from_trial_parameters(
                targets=self._input.targets,
                settings=self._input.settings,
                parameters=best_trial.params,
                grid=self._grid,
            ),
            score=float(best_trial.value),
            completed_trials=self._completed_trials,
        )

    def debug_details(self) -> CandidateSearchDetails:
        return CandidateSearchDetails(
            grid=self._grid,
            overlap_rejection_count=self._overlap_rejection_count,
            optuna_trial_count=self.optuna_trial_count,
            completed_trial_count=self._completed_trials,
        )


def search_candidates(
    search_input: CandidateSearchInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[CandidateSearchResult, CandidateSearchDetails]:
    """Run the complete adaptive-grid candidate search."""

    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance.")

    started_at = perf_counter()
    session = CandidateSearchSession(search_input)
    while session.has_remaining_trials:
        session.run_next_trial()

    return FeatureExecution(
        result=session.best_result(),
        details=(session.debug_details() if mode is ExecutionMode.DEBUG else None),
        metadata=ExecutionMetadata(
            mode=mode,
            duration_seconds=perf_counter() - started_at,
        ),
    )


def _sample_candidate_map(
    *,
    trial: optuna.Trial,
    targets: tuple[CandidateSearchTarget, ...],
    settings: CandidateSearchSettings,
    grid: ResolvedCandidateGrid,
) -> CandidateMap | None:
    points: list[CandidatePoint] = []
    occupied_nodes: set[tuple[int, int]] = set()
    has_overlap = False

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
                high=grid.x_node_count - 1,
            )
            y_index = trial.suggest_int(
                name=_y_parameter_name(
                    target_index=target_index,
                    hint_index=hint_index,
                    is_hallway=target.is_hallway,
                ),
                low=0,
                high=grid.y_node_count - 1,
            )
            node = (x_index, y_index)
            if node in occupied_nodes:
                has_overlap = True
            occupied_nodes.add(node)
            x, y = grid.coordinates(x_index, y_index)
            points.append(
                CandidatePoint(
                    room_id=target.room_id,
                    room_type=target.room_type,
                    hint_index=hint_index,
                    x=x,
                    y=y,
                )
            )

    if has_overlap:
        return None
    return CandidateMap(grid=grid, points=tuple(points))


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


def _candidate_from_trial_parameters(
    *,
    targets: tuple[CandidateSearchTarget, ...],
    settings: CandidateSearchSettings,
    parameters: Mapping[str, int | float],
    grid: ResolvedCandidateGrid,
) -> CandidateMap:
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
            try:
                x, y = grid.coordinates(x_index, y_index)
            except IndexError as exc:
                raise CandidateSearchStateError(
                    "Best trial contains a candidate node outside the resolved grid."
                ) from exc
            points.append(
                CandidatePoint(
                    room_id=target.room_id,
                    room_type=target.room_type,
                    hint_index=hint_index,
                    x=x,
                    y=y,
                )
            )
    return CandidateMap(grid=grid, points=tuple(points))


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
