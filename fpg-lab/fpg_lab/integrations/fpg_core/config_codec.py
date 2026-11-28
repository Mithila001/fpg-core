from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fpg_lab.core.settings import ROOT
from fpg_lab.integrations.fpg_core.config_models import (
    FloorPlanScoringDocument,
    SystemConfigurationDocument,
)


class CoreConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedSystemConfiguration:
    document: SystemConfigurationDocument
    buildable_space: Any
    preprocessing: Any | None
    candidate_search: Any | None
    candidate_circulation: Any | None
    candidate_scoring: Any | None
    floor_plan_solver: Any | None
    post_processing: Any | None
    openings: Any | None
    floor_plan_scoring: Any | None


@dataclass(frozen=True, slots=True)
class ValidatedCoreConfiguration:
    config: ResolvedSystemConfiguration
    payload: dict[str, Any]
    config_hash: str
    fpg_core_version: str


FLOW_REQUIRED_SECTIONS = {
    "p01a": ("preprocessing", "candidate_search", "candidate_circulation", "candidate_scoring"),
    "p01b": ("floor_plan_solver", "post_processing", "floor_plan_scoring"),
    "p01c": ("floor_plan_solver", "post_processing", "openings", "floor_plan_scoring"),
    "p01_preview": ("preprocessing",),
    "e02a": ("floor_plan_solver", "post_processing", "floor_plan_scoring"),
    "e02b": ("floor_plan_scoring",),
    "e02c": ("openings",),
    "e03a": (),
    "e03a_refresh": ("preprocessing", "floor_plan_solver"),
}
COMPLETE_SECTIONS = (
    "buildable_space",
    *dict.fromkeys(section for sections in FLOW_REQUIRED_SECTIONS.values() for section in sections),
)


class CoreConfigCodec:
    """Map Lab-owned JSON profiles to documented public fpg-core contracts."""

    @property
    def fpg_core_version(self) -> str:
        try:
            import fpg_core

            package_version = getattr(fpg_core, "__version__", None)
            if package_version:
                return str(package_version)
        except ImportError:
            pass
        try:
            return version("fpg-core")
        except PackageNotFoundError:
            return "not-installed"

    def validate_payload(self, payload: Mapping[str, Any]) -> ValidatedCoreConfiguration:
        return self._validate(payload, COMPLETE_SECTIONS, full=True)

    def validate_for_flow(
        self, payload: Mapping[str, Any], flow_type: str
    ) -> ValidatedCoreConfiguration:
        if flow_type not in FLOW_REQUIRED_SECTIONS:
            raise CoreConfigurationError(f"Unknown experiment flow {flow_type!r}")
        return self._validate(payload, FLOW_REQUIRED_SECTIONS[flow_type], flow=flow_type)

    def _validate(self, payload, required, *, full=False, flow=None):
        if not isinstance(payload, Mapping):
            raise CoreConfigurationError("configuration_data must be a JSON object")
        if type(payload.get("schema_version")) is not int or payload["schema_version"] != 7:
            raise CoreConfigurationError("schema_version: expected Lab configuration version 7")
        missing = [name for name in required if payload.get(name) is None]
        if missing:
            raise CoreConfigurationError(f"Missing configuration sections: {', '.join(missing)}")
        try:
            document_data = payload
            if not full:
                document_data = {
                    key: payload[key]
                    for key in ("schema_version", "project_units_per_meter", *required)
                }
                experiment_key = {
                    "p01b": "p01b_refinement",
                    "p01c": "p01b_refinement",
                    "e03a": "e03a",
                }.get(flow)
                if experiment_key:
                    settings = payload.get("experiments") or {}
                    document_data["experiments"] = {experiment_key: settings.get(experiment_key)}
            document = SystemConfigurationDocument.model_validate(document_data)
            if (full or flow == "e03a") and document.experiments.e03a is None:
                raise CoreConfigurationError("experiments.e03a: configuration is required")
            resolved = self._build_resolved_config(document)
            if full:
                self._validate_resolved_config(resolved)
            override = document.experiments.p01b_refinement
            if override is not None:
                solver = document.floor_plan_solver
                assert solver is not None
                effective = self._build_solver(solver.model_copy(update={"refinement_a": override}))
                if full:
                    self._validate_resolved_config(replace(resolved, floor_plan_solver=effective))
                elif flow in ("p01b", "p01c"):
                    resolved = replace(resolved, floor_plan_solver=effective)
            if not full and resolved.candidate_scoring is not None:
                from fpg_core.candidate_scoring import (
                    CandidateScoreManager,
                    create_default_registry,
                )

                CandidateScoreManager(create_default_registry(), resolved.candidate_scoring)
            if not full and resolved.floor_plan_scoring is not None:
                from fpg_core.floor_plan_scoring import validate_scoring_config

                validate_scoring_config(resolved.floor_plan_scoring)
        except ValidationError as exc:
            raise CoreConfigurationError(
                "The system-configuration JSON is invalid: " + self._format_validation_error(exc)
            ) from exc
        except CoreConfigurationError:
            raise
        except Exception as exc:
            raise CoreConfigurationError(
                f"fpg-core rejected the mapped configuration: {exc}"
            ) from exc
        normalized = document.model_dump(mode="json")
        if not full:
            normalized = {key: normalized[key] for key in document_data}
        return ValidatedCoreConfiguration(
            config=resolved,
            payload=normalized,
            config_hash=self.hash_payload(normalized),
            fpg_core_version=self.fpg_core_version,
        )

    def decode_floor_scoring(self, payload: Mapping[str, Any]) -> Any:
        from fpg_core.floor_plan_scoring import validate_scoring_config

        config = self.build_floor_scoring(FloorPlanScoringDocument.model_validate(payload))
        assert config is not None
        validate_scoring_config(config)
        return config

    def decode(self, payload: Mapping[str, Any]) -> ResolvedSystemConfiguration:
        return self.validate_payload(payload).config

    def decode_for_flow(
        self, payload: Mapping[str, Any], flow_type: str
    ) -> ResolvedSystemConfiguration:
        return self.validate_for_flow(payload, flow_type).config

    def validate_file(self, path: Path) -> ValidatedCoreConfiguration:
        if not path.exists():
            raise CoreConfigurationError(f"Configuration file was not found: {path}")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CoreConfigurationError(
                f"Configuration file is not valid JSON: {path}: {exc.msg}"
            ) from exc
        payload = (
            document.get("configuration_data", document) if isinstance(document, dict) else document
        )
        if not isinstance(payload, Mapping):
            raise CoreConfigurationError("configuration_data must be a JSON object")
        return self.validate_payload(payload)

    def default_configuration(self) -> ValidatedCoreConfiguration:
        return self.validate_file(ROOT / "seed/system_configuration.default.json")

    def configuration_schema(self) -> dict[str, Any]:
        return {
            "config_type": "fpg_lab.integrations.fpg_core.config_models.SystemConfigurationDocument",
            "fpg_core_version": self.fpg_core_version,
            "schema": SystemConfigurationDocument.model_json_schema(),
        }

    @staticmethod
    def hash_payload(payload: Mapping[str, Any]) -> str:
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def _build_resolved_config(
        self, document: SystemConfigurationDocument
    ) -> ResolvedSystemConfiguration:
        from fpg_core import BuildableSpaceConfig
        from fpg_core.domain import (
            LandSide,
            RoadType,
            SetbackCalculationMode,
            SetbackProfile,
            UsableLandConstraints,
            ValidationLimits,
        )

        source = document.buildable_space
        buildable = None
        if source is not None:
            setback = source.active_profile
            buildable = BuildableSpaceConfig(
                active_profile=SetbackProfile(
                    name=setback.name,
                    status=setback.status,
                    description=setback.description,
                    calculation_mode=SetbackCalculationMode(setback.calculation_mode),
                    base_setbacks={LandSide(k): v for k, v in setback.base_setbacks.items()},
                    road_adjustments={
                        RoadType(k): {LandSide(side): value for side, value in values.items()}
                        for k, values in setback.road_adjustments.items()
                    },
                ),
                usable_land_constraints=UsableLandConstraints(
                    **source.usable_land_constraints.model_dump()
                ),
                validation_limits=ValidationLimits(**source.validation_limits.model_dump()),
            )
        return ResolvedSystemConfiguration(
            document=document,
            buildable_space=buildable,
            preprocessing=self._build_preprocessing(document.preprocessing),
            candidate_search=self._build_candidate_search(document.candidate_search),
            candidate_circulation=self._build_circulation(document.candidate_circulation),
            candidate_scoring=self._build_candidate_scoring(document.candidate_scoring),
            floor_plan_solver=self._build_solver(document.floor_plan_solver),
            post_processing=self._build_post_processing(document.post_processing),
            openings=self._build_openings(document.openings),
            floor_plan_scoring=self.build_floor_scoring(document.floor_plan_scoring),
        )

    @staticmethod
    def _build_preprocessing(source: Any | None) -> Any | None:
        if source is None:
            return None
        from fpg_core.domain import ConstraintStrength, MatchPolicy, RoomType
        from fpg_core.floor_plan_preprocessing import (
            AspectRatioRule,
            ExcessAttachedBathroomPolicy,
            PreprocessingConfig,
            RoomCountRule,
            RoomRelationReference,
            RoomSizeReference,
            RoomSizeSelectionStrategy,
        )

        return PreprocessingConfig(
            room_count_rules=tuple(
                RoomCountRule(
                    room_type=RoomType(x.room_type),
                    minimum=x.minimum,
                    maximum=x.maximum,
                    client_selectable=x.client_selectable,
                )
                for x in source.room_count_rules
            ),
            supported_aspect_ratios=tuple(
                AspectRatioRule(label=x.label, canonical_value=x.canonical_value)
                for x in source.supported_aspect_ratios
            ),
            room_sizes=tuple(
                RoomSizeReference(
                    room_type=RoomType(x.room_type),
                    size=x.size,
                    min_width=x.min_width,
                    max_width=x.max_width,
                    min_area=x.min_area,
                    max_area=x.max_area,
                )
                for x in source.room_sizes
            ),
            room_relations=tuple(
                RoomRelationReference(
                    source_room_type=RoomType(x.source_room_type),
                    target_room_types=tuple(RoomType(v) for v in x.target_room_types),
                    match_policy=MatchPolicy(x.match_policy),
                    strength=ConstraintStrength(x.strength),
                    required=x.required,
                )
                for x in source.room_relations
            ),
            mandatory_room_types=tuple(RoomType(v) for v in source.mandatory_room_types),
            floor_area_buffer=source.floor_area_buffer,
            hallway_area_buffer=source.hallway_area_buffer,
            max_hallway_room_count=source.max_hallway_room_count,
            hallway_min_width=source.hallway_min_width,
            candidate_search_grid_spacing=source.candidate_search_grid_spacing,
            default_room_size=source.default_room_size,
            max_aspect_residual_units=source.max_aspect_residual_units,
            min_aspect_ratio=source.min_aspect_ratio,
            max_aspect_ratio=source.max_aspect_ratio,
            room_size_strategy=RoomSizeSelectionStrategy(source.room_size_strategy),
            size_normalization_exclusions=tuple(
                RoomType(v) for v in source.size_normalization_exclusions
            ),
            excess_attached_bathrooms=ExcessAttachedBathroomPolicy(
                source.excess_attached_bathrooms
            ),
        )

    @staticmethod
    def _build_candidate_search(source: Any | None) -> Any | None:
        if source is None:
            return None
        from fpg_core import CandidateSearchConfig

        return CandidateSearchConfig(
            trial_count=1,
            max_grid_node_count=source.max_grid_node_count,
            random_seed=source.random_seed,
        )

    @classmethod
    def _route_rules(cls, rules: Any) -> tuple[Any, ...]:
        from fpg_core.domain import (
            CirculationRouteRule,
            CirculationTrafficClass,
            DestinationSelection,
            RoomType,
        )

        return tuple(
            CirculationRouteRule(
                id=x.id,
                name=x.name,
                source_room_type=RoomType(x.source_room_type),
                destination_room_type=RoomType(x.destination_room_type),
                destination_selection=DestinationSelection(x.destination_selection),
                traffic_class=CirculationTrafficClass(x.traffic_class),
                allowed_transit_room_types=tuple(RoomType(v) for v in x.allowed_transit_room_types),
                required_transit_room_types=tuple(
                    RoomType(v) for v in x.required_transit_room_types
                ),
                importance_weight=x.importance_weight,
            )
            for x in rules
        )

    @classmethod
    def _build_circulation(cls, source: Any | None) -> Any | None:
        if source is None:
            return None
        from fpg_core.candidate_circulation import CandidateCirculationConfig, RoutingCostProfile
        from fpg_core.domain import RoomType

        return CandidateCirculationConfig(
            costs=RoutingCostProfile(**source.costs.model_dump()),
            route_rules=cls._route_rules(source.route_rules),
            always_traversable_room_types=tuple(
                RoomType(v) for v in source.always_traversable_room_types
            ),
            max_routing_passes=source.max_routing_passes,
        )

    @classmethod
    def _build_candidate_scoring(cls, source: Any | None) -> Any | None:
        if source is None:
            return None
        from fpg_core.candidate_scoring import (
            EvaluatorCategory,
            EvaluatorKey,
            EvaluatorRule,
            ExteriorClearanceRule,
            ScoringConfig,
            ZoneSuitabilityConfig,
        )
        from fpg_core.domain import LandSide, RoomType

        rules = []
        for item in source.evaluator_rules:
            settings: dict[str, Any]
            if item.key == "zone_suitability":
                settings = {
                    "zone_config": ZoneSuitabilityConfig(
                        zone_count_per_axis=item.settings.zone_count_per_axis,
                        falloff_multiplier=item.settings.falloff_multiplier,
                        valid_zones={
                            RoomType(k): tuple(v) for k, v in item.settings.valid_zones.items()
                        },
                    )
                }
            elif item.key == "exterior_clearance":
                settings = {
                    "rules": tuple(
                        ExteriorClearanceRule(
                            room_types=tuple(RoomType(v) for v in rule.room_types),
                            required_clear_room_count=rule.required_clear_room_count,
                            clearance_width=rule.clearance_width,
                            direction=LandSide(rule.direction),
                        )
                        for rule in item.settings.rules
                    )
                }
            else:
                settings = item.settings.model_dump()
            rules.append(
                EvaluatorRule(
                    key=EvaluatorKey(item.key),
                    category=EvaluatorCategory(item.category),
                    enabled=item.enabled,
                    order=item.order,
                    weight=item.weight,
                    minimum_score=item.minimum_score,
                    settings=settings,
                )
            )
        config = ScoringConfig(
            evaluator_rules=tuple(rules),
            fail_fast_on_critical_failure=source.fail_fast_on_critical_failure,
        )
        return config

    @staticmethod
    def _build_solver(source: Any | None) -> Any | None:
        if source is None:
            return None
        from fpg_core.domain import RoomType
        from fpg_core.floor_plan_solver import (
            FloorPlanSolver,
            FloorPlanSolverConfig,
            HardConstraintUse,
            PreparationConfig,
            ProfileCatalog,
            SeedPolicy,
            SeedSource,
            SoftConstraintUse,
            SolverConfig,
        )

        def room_type(value: Any, path: str) -> RoomType:
            try:
                return RoomType(value)
            except ValueError as exc:
                raise CoreConfigurationError(f"{path} has an invalid room type: {value!r}") from exc

        def settings(value: Any, path: str, key: str | None = None) -> Any:
            if key is not None and (key == "room_types" or key.endswith("_room_types")):
                if not isinstance(value, (list, tuple)):
                    raise CoreConfigurationError(f"{path} must be a room-type list")
                return tuple(
                    room_type(item, f"{path}[{index}]") for index, item in enumerate(value)
                )
            if key in {"room_type", "compared_type", "reference_type"}:
                return room_type(value, path)
            if key == "overrides":
                return {
                    room_type(item_key, path): settings(item_value, f"{path}.{item_key}")
                    for item_key, item_value in value.items()
                }
            if isinstance(value, dict):
                return {
                    item_key: settings(item_value, f"{path}.{item_key}", item_key)
                    for item_key, item_value in value.items()
                }
            if isinstance(value, list):
                return tuple(settings(item, f"{path}[{index}]") for index, item in enumerate(value))
            return value

        registry = FloorPlanSolver().registry

        def stage(item: Any) -> Any:
            config = FloorPlanSolverConfig(
                name=item.name,
                hard_constraints=tuple(
                    HardConstraintUse(x.key, settings(x.settings, x.key))
                    for x in item.hard_constraints
                ),
                soft_constraints=tuple(
                    SoftConstraintUse(x.key, x.weight, settings(x.settings, x.key))
                    for x in item.soft_constraints
                ),
                solver=SolverConfig(**item.solver.model_dump()),
                preparation=PreparationConfig(**item.preparation.model_dump()),
                seed=SeedPolicy(
                    source=SeedSource(item.seed.source),
                    require_source=item.seed.require_source,
                    apply_hints=item.seed.apply_hints,
                    position_tolerance=item.seed.position_tolerance,
                    size_tolerance=item.seed.size_tolerance,
                ),
            )
            registry.validate_config(config)
            return config

        return ProfileCatalog(
            initial=stage(source.initial),
            refinement_a=stage(source.refinement_a),
            refinement_b=stage(source.refinement_b),
        )

    @staticmethod
    def _build_post_processing(source: Any | None) -> Any | None:
        if source is None:
            return None
        from fpg_core.domain import RoomType
        from fpg_core.floor_plan_post_processing import (
            ExteriorStepPolicy,
            FloorPlanPostProcessingConfig,
            GridSnapConfig,
            HallwayMergeConfig,
            NumericPolicy,
            PlaceholderRemovalConfig,
            ProcessorUse,
            RectilinearSimplificationConfig,
            WallExtensionConfig,
            WallExtensionRule,
        )

        constructors = {
            "wall_extension": lambda c: WallExtensionConfig(
                rules=tuple(
                    WallExtensionRule(
                        room_type=RoomType(x.room_type),
                        max_distance=x.max_distance,
                    )
                    for x in c.rules
                ),
                exterior_steps=tuple(
                    ExteriorStepPolicy(**x.model_dump()) for x in c.exterior_steps
                ),
                **c.model_dump(exclude={"rules", "exterior_steps"}),
            ),
            "remove_placeholder_rooms": lambda c: PlaceholderRemovalConfig(),
            "hallway_merge": lambda c: HallwayMergeConfig(**c.model_dump()),
            "grid_snap": lambda c: GridSnapConfig(**c.model_dump()),
            "rectilinear_simplification": lambda c: RectilinearSimplificationConfig(),
        }
        return FloorPlanPostProcessingConfig(
            name=source.name,
            processors=tuple(
                ProcessorUse(
                    x.processor_id,
                    constructors[x.processor_id](x.config),
                    required=x.required,
                    validate_after=x.validate_after,
                )
                for x in source.processors
            ),
            numeric=NumericPolicy(**source.numeric.model_dump()),
            reject_existing_openings=source.reject_existing_openings,
        )

    @staticmethod
    def _build_openings(source: Any | None) -> Any | None:
        if source is None:
            return None
        from fpg_core.domain import RoomType
        from fpg_core.floor_plan_openings import (
            DimensionConfig,
            FeaturePolicy,
            FloorPlanOpeningsConfig,
            GeometryConfig,
            InteriorDoorConfig,
            InteriorDoorPolicy,
            ObjectiveConfig,
            SolverConfig,
            WindowPolicy,
        )

        policy = source.policy
        return FloorPlanOpeningsConfig(
            name=source.name,
            enabled_features=tuple(source.enabled_features),
            enabled_constraints=tuple(source.enabled_constraints),
            geometry=GeometryConfig(**source.geometry.model_dump()),
            dimensions=DimensionConfig(**source.dimensions.model_dump()),
            interior_doors=InteriorDoorConfig(
                default=InteriorDoorPolicy(**source.interior_doors.default.model_dump()),
                overrides=tuple((RoomType(item.room_type), InteriorDoorPolicy(**item.policy.model_dump())) for item in source.interior_doors.overrides),
            ),
            policy=FeaturePolicy(
                allowed_room_pairs=tuple(
                    (RoomType(x.first), RoomType(x.second)) for x in policy.allowed_room_pairs
                ),
                room_door_caps=tuple(
                    (RoomType(x.room_type), x.maximum) for x in policy.room_door_caps
                ),
                secondary_room_priority=tuple(RoomType(v) for v in policy.secondary_room_priority),
                window_room_types=tuple(RoomType(v) for v in policy.window_room_types),
                window_policies=tuple((RoomType(v.room_type), WindowPolicy(**v.policy.model_dump())) for v in policy.window_policies),
                normal_connection_caps=tuple((RoomType(v.room_type), v.maximum) for v in policy.normal_connection_caps),
                prevent_duplicate_connections=policy.prevent_duplicate_connections,
                main_side_priority=tuple(policy.main_side_priority),
                secondary_side_priority=tuple(policy.secondary_side_priority),
                window_side_priority=tuple(policy.window_side_priority),
                required_access_room_types=tuple(
                    RoomType(v) for v in policy.required_access_room_types
                ),
                door_placement_priority=tuple(
                    (RoomType(v.room_type), v.priority) for v in policy.door_placement_priority
                ),
            ),
            objective=ObjectiveConfig(tier_order=tuple(source.objective.tier_order)),
            solver=SolverConfig(**source.solver.model_dump()),
        )

    @staticmethod
    def build_floor_scoring(source: Any | None) -> Any | None:
        if source is None:
            return None
        from fpg_core.floor_plan_scoring import (
            BedroomQualitySettings,
            EnclosedVoidsSettings,
            EvaluatorKey,
            EvaluatorRule,
            FloorPlanScoringConfig,
            GeometryIntegritySettings,
            GroupKey,
            InwardRecessSettings,
            LivingRoomBalanceSettings,
            ScoringGroupRule,
        )

        setting_types = {
            "geometry_integrity": GeometryIntegritySettings,
            "enclosed_voids": EnclosedVoidsSettings,
            "inward_recess": InwardRecessSettings,
            "living_room_balance": LivingRoomBalanceSettings,
            "bedroom_quality": BedroomQualitySettings,
        }
        config = FloorPlanScoringConfig(
            groups=tuple(
                ScoringGroupRule(
                    key=GroupKey(x.key), enabled=x.enabled, order=x.order, weight=x.weight
                )
                for x in source.groups
            ),
            evaluators=tuple(
                EvaluatorRule(
                    key=EvaluatorKey(x.key),
                    group_key=GroupKey(x.group_key),
                    settings=x.settings
                    if x.key in {"room_size_consistency", "room_relationship_quality"}
                    else setting_types[x.key](**x.settings.model_dump()),
                    enabled=x.enabled,
                    order=x.order,
                    weight=x.weight,
                    minimum_score=x.minimum_score,
                )
                for x in source.evaluators
            ),
        )
        return config

    @staticmethod
    def _validate_resolved_config(config: ResolvedSystemConfiguration) -> None:
        from fpg_core import FpgCoreConfig, validate_fpg_core_config

        assert config.preprocessing is not None
        assert config.candidate_search is not None
        assert config.candidate_scoring is not None
        assert config.floor_plan_solver is not None
        assert config.post_processing is not None
        assert config.openings is not None
        assert config.floor_plan_scoring is not None
        validate_fpg_core_config(
            FpgCoreConfig(
                schema_version=2,
                project_units_per_meter=config.document.project_units_per_meter,
                buildable_space=config.buildable_space,
                preprocessing=config.preprocessing,
                candidate_search=config.candidate_search,
                candidate_scoring=config.candidate_scoring,
                floor_plan_solver=config.floor_plan_solver,
                post_processing=config.post_processing,
                openings=config.openings,
                floor_plan_scoring=config.floor_plan_scoring,
            )
        )

    @staticmethod
    def _format_validation_error(exc: ValidationError) -> str:
        return "; ".join(
            f"{'.'.join(str(p) for p in item.get('loc', ()))}: {item.get('msg', 'invalid value')}"
            for item in exc.errors(include_url=False)
        )
