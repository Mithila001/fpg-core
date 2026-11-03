from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fpg_lab.core.settings import ROOT
from fpg_lab.integrations.fpg_core.config_codec import (
    CoreConfigCodec,
    CoreConfigurationError,
)


def verify_local_core() -> None:
    import fpg_core

    expected = (ROOT.parent / "src/fpg_core/__init__.py").resolve()
    actual = Path(fpg_core.__file__).resolve()
    if actual != expected:
        raise CoreConfigurationError(
            f"Lab requires this repository's Core at {expected}; imported {actual}. "
            "Rerun the Lab setup script."
        )


def read_configuration_document(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        raise CoreConfigurationError(f"Configuration file was not found: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CoreConfigurationError(
            f"Configuration file is not valid JSON: {path}: {exc.msg}"
        ) from exc
    if not isinstance(document, dict):
        raise CoreConfigurationError(f"{path} must contain a JSON object")

    payload = document.get("configuration_data", document)
    if not isinstance(payload, Mapping):
        raise CoreConfigurationError("configuration_data must be a JSON object")

    envelope_version = document.get("schema_version")
    return dict(payload), None if envelope_version is None else str(envelope_version)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the documented fpg-core public API and configuration mapping used by this Lab."
        )
    )
    parser.add_argument(
        "--system-config",
        type=Path,
        default=ROOT / "seed/system_configuration.default.json",
    )
    args = parser.parse_args()

    try:
        verify_local_core()
        payload, envelope_version = read_configuration_document(args.system_config)
        validated = CoreConfigCodec().validate_payload(payload)
        configuration_version = str(validated.payload["schema_version"])
        if envelope_version is not None and envelope_version != configuration_version:
            raise CoreConfigurationError(
                "The record schema_version must match "
                "configuration_data.schema_version: "
                f"{envelope_version!r} != {configuration_version!r}"
            )

        from fpg_core.candidate_circulation import (
            CandidateCirculationConfig,
            CandidateCirculationError,
            CandidateCirculationInput,
            CirculationRouteRule,
            CirculationTrafficClass,
            DestinationSelection,
            RoutingCostProfile,
            refine_candidate_circulation,
        )
        from fpg_core.candidate_scoring import (
            RELATIONSHIP_QUALITY_KEY,
            CandidateScoringInput,
            EvaluatorCategory,
            EvaluatorRule,
            RelationshipQualityConfig,
            create_default_config,
            create_default_registry,
            evaluate_candidate,
        )
        from fpg_core.candidate_search import (
            CandidateSearchConfig,
            CandidateSearchInput,
            CandidateSearchSession,
            build_candidate_search_targets,
        )
        from fpg_core.domain import ExecutionMode, GridRoutingCostProfile, RoomType
        from fpg_core.floor_plan_openings import OpeningGenerationRequest, generate_openings
        from fpg_core.floor_plan_post_processing import (
            PostProcessingRequest,
            post_process_floor_plan,
        )
        from fpg_core.floor_plan_preprocessing import (
            FloorLimits,
            PreprocessingInput,
            PreprocessingRequest,
            RequestedRoom,
            prepare_generation_input,
        )
        from fpg_core.floor_plan_scoring import FloorPlanScoringInput, score_floor_plan
        from fpg_core.floor_plan_solver import (
            FloorPlanSolveRequest,
            RoomPlacementHint,
            generate_floor_plan,
        )

        for flow in ("p01a", "p01b", "p01c"):
            CoreConfigCodec().decode_for_flow(validated.payload, flow)
    except (CoreConfigurationError, ImportError) as exc:
        print(f"FPG Core verification failed:\n{exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    checked = (
        CandidateSearchInput,
        CandidateSearchSession,
        CandidateSearchConfig,
        build_candidate_search_targets,
        CandidateCirculationConfig,
        CandidateCirculationError,
        CandidateCirculationInput,
        CirculationRouteRule,
        CirculationTrafficClass,
        DestinationSelection,
        RoutingCostProfile,
        refine_candidate_circulation,
        CandidateScoringInput,
        EvaluatorCategory,
        EvaluatorRule,
        RelationshipQualityConfig,
        RELATIONSHIP_QUALITY_KEY,
        create_default_config,
        create_default_registry,
        evaluate_candidate,
        ExecutionMode,
        GridRoutingCostProfile,
        RoomType,
        FloorLimits,
        PreprocessingInput,
        PreprocessingRequest,
        RequestedRoom,
        prepare_generation_input,
        FloorPlanSolveRequest,
        RoomPlacementHint,
        generate_floor_plan,
        PostProcessingRequest,
        post_process_floor_plan,
        OpeningGenerationRequest,
        generate_openings,
        FloorPlanScoringInput,
        score_floor_plan,
    )
    assert all(item is not None for item in checked)

    print(f"FPG Core version: {validated.fpg_core_version}")
    print(f"Configuration schema: {configuration_version}")
    print(f"Configuration hash: {validated.config_hash}")
    print("Configuration mapping and validation: OK")
    print("Required public P01A/P01B/P01C API imports and configuration mappings: OK")


if __name__ == "__main__":
    main()
