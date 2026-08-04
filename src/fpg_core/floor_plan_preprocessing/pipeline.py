from __future__ import annotations

from ..domain import FloorPlanGenerationSpec
from .business_rules import apply_business_rules
from .contracts import (
    FloorSelection,
    PreparedGenerationInput,
    PreprocessingInput,
    PreprocessingReport,
)
from .normalization import normalize_request, prepare_reference_data
from .preparation import build_preprocessing_context
from .validation import (
    validate_context,
    validate_input,
    validate_normalized_request,
    validate_output,
    validate_reference_data,
)


def run_pipeline(
    value: PreprocessingInput,
    *,
    collect_details: bool,
) -> tuple[PreparedGenerationInput, PreprocessingReport | None]:
    validate_input(value)
    normalized_request = normalize_request(
        value.request,
        value.policy,
        collect_details=collect_details,
    )
    validate_normalized_request(normalized_request, value.policy)
    reference_data = prepare_reference_data(value.reference_data)
    validate_reference_data(reference_data)
    ruled_request = apply_business_rules(
        normalized_request,
        value.policy,
        collect_details=collect_details,
    )
    context = build_preprocessing_context(
        ruled_request,
        reference_data,
        value.policy,
        collect_details=collect_details,
    )
    validate_context(context)

    specification = FloorPlanGenerationSpec(
        floor=context.floor,
        rooms=context.rooms,
        room_relations=context.relations,
    )
    validate_output(specification, value.policy)

    result = PreparedGenerationInput(generation_spec=specification)
    if not collect_details:
        return result, None

    details = PreprocessingReport(
        normalizations=context.request.normalizations,
        room_decisions=context.request.room_decisions,
        relation_decisions=context.relation_decisions,
        selected_room_size=context.request.selected_room_size,
        floor_selection=FloorSelection(
            requested_width=context.request.raw_max_width,
            requested_length=context.request.raw_max_length,
            normalized_max_width=context.request.max_width,
            normalized_max_length=context.request.max_length,
            selected_width=int(context.floor.width),
            selected_length=int(context.floor.length),
            requested_aspect_ratio=context.request.aspect_ratio,
            selected_aspect_ratio=context.floor.length / context.floor.width,
            aspect_residual_units=abs(
                context.floor.length
                - context.floor.width * context.request.aspect_ratio
            ),
            minimum_required_area=context.minimum_required_area,
            maximum_target_area=context.maximum_target_area,
            unused_limit_area=(
                context.request.max_width * context.request.max_length
                - context.floor.width * context.floor.length
            ),
        ),
        applied_defaults=context.request.applied_defaults,
    )
    return result, details
