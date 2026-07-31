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


def run_pipeline(value: PreprocessingInput) -> PreparedGenerationInput:
    validate_input(value)
    normalized_request = normalize_request(value.request, value.policy)
    validate_normalized_request(normalized_request, value.policy)
    reference_data = prepare_reference_data(value.reference_data)
    validate_reference_data(reference_data)
    ruled_request = apply_business_rules(normalized_request, value.policy)
    context = build_preprocessing_context(
        ruled_request, reference_data, value.policy
    )
    validate_context(context)

    specification = FloorPlanGenerationSpec(
        floor=context.floor,
        rooms=context.rooms,
        room_relations=context.relations,
    )
    validate_output(specification, value.policy)
    report = PreprocessingReport(
        normalizations=context.request.normalizations,
        room_decisions=context.request.room_decisions,
        relation_decisions=context.relation_decisions,
        selected_room_size=context.request.selected_room_size,
        floor_selection=FloorSelection(
            requested_width=context.request.max_width,
            requested_length=context.request.max_length,
            selected_width=context.floor.width,
            selected_length=context.floor.length,
            aspect_ratio=context.request.aspect_ratio,
            minimum_required_area=context.minimum_required_area,
            maximum_target_area=context.maximum_target_area,
        ),
        applied_defaults=context.request.applied_defaults,
    )
    return PreparedGenerationInput(generation_spec=specification, report=report)
