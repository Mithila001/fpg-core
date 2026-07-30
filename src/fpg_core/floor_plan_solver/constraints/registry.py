from __future__ import annotations

from dataclasses import dataclass, field

from ..exceptions import InvalidProfileError, UnknownConstraintError
from ..profiles import GenerationProfile
from .base import HardConstraint, SoftConstraint


@dataclass(slots=True)
class ConstraintRegistry:
    """Runtime collection of available hard and soft constraints."""

    hard: dict[str, HardConstraint] = field(default_factory=dict)
    soft: dict[str, SoftConstraint] = field(default_factory=dict)

    def register_hard(self, constraint: HardConstraint) -> ConstraintRegistry:
        if constraint.key in self.hard:
            raise InvalidProfileError(
                f"Hard constraint '{constraint.key}' is already registered"
            )
        self.hard[constraint.key] = constraint
        return self

    def register_soft(self, constraint: SoftConstraint) -> ConstraintRegistry:
        if constraint.key in self.soft:
            raise InvalidProfileError(
                f"Soft constraint '{constraint.key}' is already registered"
            )
        self.soft[constraint.key] = constraint
        return self

    def get_hard(self, key: str) -> HardConstraint:
        try:
            return self.hard[key]
        except KeyError as exc:
            raise UnknownConstraintError(
                f"Unknown hard constraint '{key}'"
            ) from exc

    def get_soft(self, key: str) -> SoftConstraint:
        try:
            return self.soft[key]
        except KeyError as exc:
            raise UnknownConstraintError(
                f"Unknown soft constraint '{key}'"
            ) from exc

    def validate_profile(self, profile: GenerationProfile) -> None:
        for hard_use in profile.hard_constraints:
            self.get_hard(hard_use.key)
        for soft_use in profile.soft_constraints:
            self.get_soft(soft_use.key)
