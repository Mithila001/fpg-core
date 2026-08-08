from __future__ import annotations

from dataclasses import dataclass

from ..domain import (
    LandSide,
    SetbackCalculationMode,
    SetbackProfile,
    ValidationLimits,
)


@dataclass(frozen=True, slots=True)
class BuildableLandConfig:
    """Reusable validation and setback policy for buildable-land calculation."""

    setback_profile: SetbackProfile
    validation_limits: ValidationLimits

    def __post_init__(self) -> None:
        if not isinstance(self.setback_profile, SetbackProfile):
            raise TypeError("setback_profile must be a SetbackProfile instance.")
        if not isinstance(self.validation_limits, ValidationLimits):
            raise TypeError("validation_limits must be a ValidationLimits instance.")

        limits = self.validation_limits
        for name, value in (
            ("minimum_vertex_count", limits.minimum_vertex_count),
            ("maximum_vertex_count", limits.maximum_vertex_count),
            ("maximum_absolute_coordinate", limits.maximum_absolute_coordinate),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"validation_limits.{name} must be an integer.")

        if limits.minimum_vertex_count < 3:
            raise ValueError("minimum_vertex_count must be at least 3.")
        if limits.maximum_vertex_count < limits.minimum_vertex_count:
            raise ValueError(
                "maximum_vertex_count must be greater than or equal to "
                "minimum_vertex_count."
            )
        if limits.maximum_absolute_coordinate <= 0:
            raise ValueError("maximum_absolute_coordinate must be greater than zero.")

        profile = self.setback_profile
        if profile.calculation_mode is not SetbackCalculationMode.BASE_PLUS_ROAD_ADJUSTMENT:
            raise ValueError("Unsupported setback calculation mode.")

        missing_sides = tuple(side for side in LandSide if side not in profile.base_setbacks)
        if missing_sides:
            names = ", ".join(side.value for side in missing_sides)
            raise ValueError(f"setback_profile.base_setbacks is missing: {names}.")

        for side, value in profile.base_setbacks.items():
            _validate_non_negative_distance(
                value,
                f"setback_profile.base_setbacks[{side.value!r}]",
            )

        for road_type, adjustments in profile.road_adjustments.items():
            if LandSide.FRONT not in adjustments:
                raise ValueError(
                    "setback_profile.road_adjustments"
                    f"[{road_type.value!r}] must define the front adjustment."
                )
            for side, value in adjustments.items():
                _validate_non_negative_distance(
                    value,
                    "setback_profile.road_adjustments"
                    f"[{road_type.value!r}][{side.value!r}]",
                )


def _validate_non_negative_distance(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer project-unit distance.")
    if value < 0:
        raise ValueError(f"{name} cannot be negative.")


__all__ = ["BuildableLandConfig"]
