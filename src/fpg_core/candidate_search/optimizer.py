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
    HallwayRoomCountRange,
    ResolvedCandidateGrid,
)
from .exceptions import CandidateSearchStateError
from .grid import build_candidate_grid
from .models import (
    CandidateSearchDetails,
    CandidateSearchInput,
    CandidateSearchResult,
    CandidateSearchTarget,
    CandidateSuggestion,
    CandidateTrialResult,
)

_HALLWAY_ROOM_COUNT_PARAMETER = "hallway_room_count"


class CandidateSearchSession:
    """Incremental Optuna-backed uniform-grid candidate search."""

    def __init__(self, search_input: CandidateSearchInput) -> None:
        if not isinstance(search_input, CandidateSearchInput):
            raise TypeError("search_input must be a CandidateSearchInput instance.")

        self._input = search_input
        self._grid = build_candidate_grid(
            grid=search_input.grid,
            max_grid_node_count=search_input.config.max_grid_node_count,
        )
        self._study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(
                seed=search_input.config.random_seed,
            ),
        )
        self._completed_trials = 0
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
        return self._input.config.trial_count - self._completed_trials

    @property
    def has_remaining_trials(self) -> bool:
        return self.remaining_trials > 0

    @property
    def has_pending_trial(self) -> bool:
        return self._pending_trial is not None

    @property
    def optuna_trial_count(self) -> int:
        return len(self._study.trials)

    def ask_next_trial(self) -> CandidateSuggestion:
        """Generate one unscored candidate using sampling without replacement."""

        if self.has_pending_trial:
            raise CandidateSearchStateError(
                "The current candidate trial must be scored or failed before "
                "requesting another trial."
            )
        if not self.has_remaining_trials:
            raise CandidateSearchStateError(
                "Candidate search session has no remaining trials."
            )

        trial = self._study.ask()
        try:
            candidate = _sample_candidate_map(
                trial=trial,
                targets=self._input.targets,
                hallway_room_count_range=self._input.hallway_room_count_range,
                grid=self._grid,
            )
        except Exception:
            self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
            raise

        suggestion = CandidateSuggestion(
            trial_number=trial.number,
            candidate=candidate,
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
        """Evaluate one candidate using the configured callback."""

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
                hallway_room_count_range=self._input.hallway_room_count_range,
                parameters=best_trial.params,
                grid=self._grid,
            ),
            score=float(best_trial.value),
            completed_trials=self._completed_trials,
        )

    def debug_details(self) -> CandidateSearchDetails:
        return CandidateSearchDetails(
            grid=self._grid,
            optuna_trial_count=self.optuna_trial_count,
            completed_trial_count=self._completed_trials,
        )


def search_candidates(
    search_input: CandidateSearchInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[CandidateSearchResult, CandidateSearchDetails]:
    """Run the complete uniform-grid candidate search."""

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
    hallway_room_count_range: HallwayRoomCountRange,
    grid: ResolvedCandidateGrid,
) -> CandidateMap:
    hallway_room_count = trial.suggest_int(
        name=_HALLWAY_ROOM_COUNT_PARAMETER,
        low=hallway_room_count_range.minimum,
        high=hallway_room_count_range.maximum,
    )
    active_targets = _active_targets(
        targets=targets,
        hallway_room_count=hallway_room_count,
    )
    available_flat_node_indexes = list(grid.interior_flat_node_indexes())
    points: list[CandidatePoint] = []

    for target_index, target in active_targets:
        selection_rank = trial.suggest_int(
            name=_node_rank_parameter_name(target_index),
            low=0,
            high=len(available_flat_node_indexes) - 1,
        )
        flat_node_index = available_flat_node_indexes.pop(selection_rank)
        x_index, y_index = grid.indexes_from_flat_node_index(flat_node_index)
        x, y = grid.coordinates(x_index, y_index)
        points.append(
            CandidatePoint(
                room_id=target.room_id,
                room_type=target.room_type,
                hint_index=1,
                x=x,
                y=y,
            )
        )

    return CandidateMap(grid=grid, points=tuple(points))


def _candidate_from_trial_parameters(
    *,
    targets: tuple[CandidateSearchTarget, ...],
    hallway_room_count_range: HallwayRoomCountRange,
    parameters: Mapping[str, int | float],
    grid: ResolvedCandidateGrid,
) -> CandidateMap:
    if _HALLWAY_ROOM_COUNT_PARAMETER not in parameters:
        raise CandidateSearchStateError(
            "Best trial is missing the global hallway room count."
        )
    hallway_room_count = _validated_parameter_index(
        parameter_name=_HALLWAY_ROOM_COUNT_PARAMETER,
        value=parameters[_HALLWAY_ROOM_COUNT_PARAMETER],
    )
    if not (
        hallway_room_count_range.minimum
        <= hallway_room_count
        <= hallway_room_count_range.maximum
    ):
        raise CandidateSearchStateError(
            "The best trial hallway room count is outside the prepared range."
        )

    active_targets = _active_targets(
        targets=targets,
        hallway_room_count=hallway_room_count,
    )
    available_flat_node_indexes = list(grid.interior_flat_node_indexes())
    points: list[CandidatePoint] = []

    for target_index, target in active_targets:
        parameter_name = _node_rank_parameter_name(target_index)
        if parameter_name not in parameters:
            raise CandidateSearchStateError(
                "Best trial is missing the remaining-node rank for "
                f"room '{target.room_id}'."
            )
        selection_rank = _validated_parameter_index(
            parameter_name=parameter_name,
            value=parameters[parameter_name],
        )
        if selection_rank >= len(available_flat_node_indexes):
            raise CandidateSearchStateError(
                f"Trial parameter '{parameter_name}' is outside the remaining "
                "candidate-node pool."
            )
        flat_node_index = available_flat_node_indexes.pop(selection_rank)
        x_index, y_index = grid.indexes_from_flat_node_index(flat_node_index)
        x, y = grid.coordinates(x_index, y_index)
        points.append(
            CandidatePoint(
                room_id=target.room_id,
                room_type=target.room_type,
                hint_index=1,
                x=x,
                y=y,
            )
        )

    return CandidateMap(grid=grid, points=tuple(points))


def _active_targets(
    *,
    targets: tuple[CandidateSearchTarget, ...],
    hallway_room_count: int,
) -> tuple[tuple[int, CandidateSearchTarget], ...]:
    active: list[tuple[int, CandidateSearchTarget]] = []
    selected_hallways = 0

    for target_index, target in enumerate(targets):
        if not target.is_hallway:
            active.append((target_index, target))
            continue
        if selected_hallways < hallway_room_count:
            active.append((target_index, target))
            selected_hallways += 1

    if selected_hallways != hallway_room_count:
        raise CandidateSearchStateError(
            "Candidate Search could not activate the requested number of hallway "
            "room targets."
        )
    return tuple(active)


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


def _node_rank_parameter_name(target_index: int) -> str:
    return f"candidate_{target_index}_remaining_node_rank"
