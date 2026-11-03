from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fpg_lab.integrations.fpg_core.config_codec import ResolvedSystemConfiguration


class FpgCoreAdapterError(RuntimeError):
    pass


class FpgCoreCandidateRejected(FpgCoreAdapterError):
    """Expected candidate-level rejection that should be recorded with score 0."""

    def __init__(self, message: str, *, cause_type: str) -> None:
        self.cause_type = cause_type
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class RecordedSearchResult:
    trial_number: int | None
    points: tuple[Any, ...]
    score: float
    completed_trials: int


@dataclass(slots=True)
class SearchTrial:
    trial_no: int
    suggestion: Any
    candidate: Any
    core_trial_no: int | None = None
    result: RecordedSearchResult | None = None

    @property
    def points(self) -> tuple[Any, ...]:
        return tuple(self.candidate.points)

    @property
    def grid(self) -> Any:
        return self.candidate.grid


class IncrementalCandidateSearch:
    def __init__(self, session: Any) -> None:
        self._session = session
        self._issued = 0
        self._recorded = 0
        self._has_pending = False

    @property
    def has_remaining_trials(self) -> bool:
        return int(self._session.remaining_trials) > 0

    def ask(self) -> SearchTrial:
        suggestion = self._session.ask_next_trial()
        self._issued += 1
        self._has_pending = True
        core_trial_no = getattr(suggestion, "trial_number", None)
        return SearchTrial(
            trial_no=self._issued,
            suggestion=suggestion,
            candidate=suggestion.candidate,
            core_trial_no=int(core_trial_no) if core_trial_no is not None else None,
        )

    def record_score(self, trial: SearchTrial, score: float) -> SearchTrial:
        self._session.record_score(trial.suggestion, score)
        self._recorded += 1
        trial.result = RecordedSearchResult(
            trial_number=trial.core_trial_no,
            points=trial.points,
            score=float(score),
            completed_trials=self._recorded,
        )
        self._has_pending = False
        return trial

    def fail_pending(self) -> None:
        if not self._has_pending:
            return
        self._session.fail_pending_trial()
        self._has_pending = False


class FpgCoreAdapter:
    """Explicit adapter for the documented public fpg-core consumer API."""

    def __init__(self, configuration: ResolvedSystemConfiguration) -> None:
        self.configuration = configuration
        self.core_config = configuration
        self.config_document = configuration.document

    def _required(self, section: str) -> Any:
        value = getattr(self.core_config, section)
        if value is None:
            raise FpgCoreAdapterError(f"Required configuration section {section!r} is missing")
        return value

    @staticmethod
    def execution_mode(*, debug: bool) -> Any:
        from fpg_core.domain import ExecutionMode

        return ExecutionMode.DEBUG if debug else ExecutionMode.PRODUCTION

    def preprocess(
        self,
        floor_plan_request: dict[str, Any],
        *,
        debug: bool,
    ) -> Any:
        from fpg_core.domain import RoomType
        from fpg_core.floor_plan_preprocessing import (
            FloorLimits,
            PreprocessingInput,
            PreprocessingRequest,
            RequestedRoom,
            prepare_generation_input,
        )

        try:
            limits_payload = floor_plan_request["floor_limits"]
            rooms_payload = floor_plan_request["rooms"]
            aspect_ratio = floor_plan_request["aspect_ratio"]
        except KeyError as exc:
            raise FpgCoreAdapterError(
                f"floor_plan_request is missing required field {exc.args[0]!r}"
            ) from exc
        if not isinstance(limits_payload, dict):
            raise FpgCoreAdapterError("floor_limits must be a JSON object")
        if not isinstance(rooms_payload, list):
            raise FpgCoreAdapterError("rooms must be a JSON array")

        try:
            request = PreprocessingRequest(
                floor_limits=FloorLimits(
                    max_width=float(limits_payload["max_width"]),
                    max_length=float(limits_payload["max_length"]),
                ),
                aspect_ratio=aspect_ratio,
                rooms=tuple(
                    RequestedRoom(
                        room_type=RoomType(item["room_type"]),
                        id=item.get("id"),
                        name=item.get("name"),
                        requested_size=item.get("requested_size"),
                    )
                    for item in rooms_payload
                ),
            )
            return prepare_generation_input(
                PreprocessingInput(
                    request=request,
                    config=self._required("preprocessing"),
                ),
                mode=self.execution_mode(debug=debug),
            )
        except FpgCoreAdapterError:
            raise
        except Exception as exc:
            raise FpgCoreAdapterError(f"FPG Core preprocessing failed: {exc}") from exc

    @staticmethod
    def generation_specification(preprocessing_execution: Any) -> Any:
        try:
            return preprocessing_execution.result.generation_spec
        except AttributeError as exc:
            raise FpgCoreAdapterError(
                "Preprocessing did not return result.generation_spec"
            ) from exc

    def create_candidate_search(
        self,
        prepared: Any,
        *,
        trial_count: int,
    ) -> IncrementalCandidateSearch:
        from fpg_core.candidate_search import (
            CandidateSearchConfig,
            CandidateSearchInput,
            CandidateSearchSession,
            build_candidate_search_targets,
        )

        specification = prepared.generation_spec
        self._validate_route_rule_room_types(specification)
        search_config = self._required("candidate_search")

        search_input = CandidateSearchInput(
            targets=build_candidate_search_targets(specification),
            grid=prepared.candidate_grid,
            hallway_room_count_range=prepared.hallway_room_count_range,
            config=CandidateSearchConfig(
                max_grid_node_count=search_config.max_grid_node_count,
                trial_count=trial_count,
                random_seed=search_config.random_seed,
            ),
            # P01A scores externally so each stage can be persisted and cancelled.
            evaluator=lambda _candidate: 0.0,
        )
        return IncrementalCandidateSearch(CandidateSearchSession(search_input))

    def run_circulation(
        self,
        candidate: Any,
        *,
        debug: bool,
    ) -> Any:
        from fpg_core.candidate_circulation import (
            CandidateCirculationError,
            CandidateCirculationInput,
            refine_candidate_circulation,
        )

        try:
            return refine_candidate_circulation(
                CandidateCirculationInput(
                    candidate=candidate,
                    config=self._required("candidate_circulation"),
                ),
                mode=self.execution_mode(debug=debug),
            )
        except CandidateCirculationError as exc:
            raise FpgCoreCandidateRejected(
                str(exc),
                cause_type=type(exc).__name__,
            ) from exc
        except Exception as exc:
            raise FpgCoreAdapterError(f"FPG Core candidate circulation failed: {exc}") from exc

    def score_candidate(
        self,
        specification: Any,
        circulation_execution: Any,
        *,
        debug: bool,
    ) -> Any:
        from fpg_core.candidate_scoring import (
            CandidateScoringInput,
            create_default_registry,
            evaluate_candidate,
        )

        try:
            return evaluate_candidate(
                CandidateScoringInput(
                    specification=specification,
                    candidate=circulation_execution.result.candidate,
                    hallway_classifications=(circulation_execution.result.hallway_classifications),
                ),
                registry=create_default_registry(),
                config=self._required("candidate_scoring"),
                mode=self.execution_mode(debug=debug),
            )
        except Exception as exc:
            raise FpgCoreAdapterError(f"FPG Core candidate scoring failed: {exc}") from exc

    @staticmethod
    def final_score(scoring_result: Any) -> float:
        try:
            return float(scoring_result.total_score)
        except (AttributeError, TypeError, ValueError) as exc:
            raise FpgCoreAdapterError(
                "Candidate scoring did not return a numeric total_score"
            ) from exc

    @staticmethod
    def build_manual_candidate(prepared: Any, hint_points: dict[str, Any]) -> Any:
        from fpg_core.domain import CandidateMap, CandidatePoint, RoomType

        specification = prepared.generation_spec
        normal_rooms = [
            room for room in specification.rooms if room.room_type is not RoomType.HALLWAY
        ]
        hallway_rooms = [room for room in specification.rooms if room.room_type is RoomType.HALLWAY]
        supplied_rooms = hint_points.get("rooms", [])
        supplied_hallways = hint_points.get("hallways", [])
        expected = {str(room.id): room for room in normal_rooms}
        supplied = {str(item["room_id"]): item for item in supplied_rooms}
        missing = sorted(set(expected) - set(supplied))
        unknown = sorted(set(supplied) - set(expected))
        if missing or unknown or len(supplied) != len(supplied_rooms):
            raise FpgCoreAdapterError(
                f"Manual room hints do not match prepared rooms; missing={missing}, unknown={unknown}."
            )
        hallway_range = prepared.hallway_room_count_range
        if not hallway_range.minimum <= len(supplied_hallways) <= hallway_range.maximum:
            raise FpgCoreAdapterError(
                f"Manual hallway count must be between {hallway_range.minimum} and {hallway_range.maximum}."
            )
        points = [
            CandidatePoint(
                room_id=room.id,
                room_type=room.room_type,
                x=supplied[str(room.id)]["x"],
                y=supplied[str(room.id)]["y"],
            )
            for room in normal_rooms
        ]
        points.extend(
            CandidatePoint(
                room_id=room.id,
                room_type=room.room_type,
                x=item["x"],
                y=item["y"],
            )
            for room, item in zip(hallway_rooms, supplied_hallways, strict=False)
        )
        try:
            candidate = CandidateMap(grid=prepared.candidate_grid, points=tuple(points))
            prepared.generation_spec_for_candidate(candidate)
            return candidate
        except Exception as exc:
            raise FpgCoreAdapterError(f"Manual candidate validation failed: {exc}") from exc

    @staticmethod
    def generation_specification_for_candidate(prepared: Any, candidate: Any) -> Any:
        try:
            return prepared.generation_spec_for_candidate(candidate)
        except Exception as exc:
            raise FpgCoreAdapterError(
                f"Candidate-specific floor-plan specification failed: {exc}"
            ) from exc

    @staticmethod
    def candidate_hints(candidate: Any) -> tuple[Any, ...]:
        from fpg_core.floor_plan_solver import RoomPlacementHint

        return tuple(
            RoomPlacementHint(room_id=point.room_id, x=point.x, y=point.y)
            for point in candidate.points
        )

    def solve_initial_floor_plan(self, specification: Any, candidate: Any, *, debug: bool) -> Any:
        from fpg_core.floor_plan_solver import FloorPlanSolveRequest, generate_floor_plan

        return generate_floor_plan(
            FloorPlanSolveRequest(
                specification=specification,
                config=self._required("floor_plan_solver").initial,
                candidate_hints=self.candidate_hints(candidate),
            ),
            mode=self.execution_mode(debug=debug),
        )

    def refine_floor_plan(
        self, specification: Any, floor_plan: Any, *, profile: str, debug: bool
    ) -> Any:
        from fpg_core.floor_plan_solver import FloorPlanSolveRequest, generate_floor_plan

        config = getattr(self._required("floor_plan_solver"), profile)
        return generate_floor_plan(
            FloorPlanSolveRequest(
                specification=specification,
                config=config,
                existing_floor_plan=floor_plan,
            ),
            mode=self.execution_mode(debug=debug),
        )

    def post_process_floor_plan(self, specification: Any, floor_plan: Any, *, debug: bool) -> Any:
        from copy import deepcopy

        from fpg_core.floor_plan_post_processing import (
            PostProcessingRequest,
            post_process_floor_plan,
        )

        return post_process_floor_plan(
            PostProcessingRequest(
                floor_plan=deepcopy(floor_plan),
                config=self._required("post_processing"),
                specification=specification,
            ),
            mode=self.execution_mode(debug=debug),
        )

    def generate_floor_plan_openings(self, floor_plan: Any, *, debug: bool) -> Any:
        from fpg_core.floor_plan_openings import OpeningGenerationRequest, generate_openings

        return generate_openings(
            OpeningGenerationRequest(floor_plan=floor_plan, config=self._required("openings")),
            mode=self.execution_mode(debug=debug),
        )

    def score_completed_floor_plan(
        self, floor_plan: Any, specification: Any, *, debug: bool
    ) -> Any:
        from fpg_core.floor_plan_scoring import FloorPlanScoringInput, score_floor_plan

        return score_floor_plan(
            FloorPlanScoringInput(
                floor_plan=floor_plan,
                specification=specification,
                config=self._required("floor_plan_scoring"),
            ),
            mode=self.execution_mode(debug=debug),
        )

    def _validate_route_rule_room_types(self, specification: Any) -> None:
        available = {room.room_type.value for room in specification.rooms}
        missing: list[str] = []
        circulation = self.config_document.candidate_circulation
        if circulation is None:
            raise FpgCoreAdapterError(
                "Required configuration section 'candidate_circulation' is missing"
            )
        for rule in circulation.route_rules:
            if rule.source_room_type not in available:
                missing.append(f"rule {rule.id} source {rule.source_room_type!r} is absent")
            if rule.destination_room_type not in available:
                missing.append(
                    f"rule {rule.id} destination {rule.destination_room_type!r} is absent"
                )
        if missing:
            raise FpgCoreAdapterError(
                "Candidate circulation rules do not match the preprocessed room set: "
                + "; ".join(missing)
            )
