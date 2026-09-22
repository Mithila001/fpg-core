from __future__ import annotations

from typing import TypeAlias

from .config import FloorPlanOpeningsConfig

# Backward-compatible name. A profile is a named opening configuration preset.
OpeningGenerationProfile: TypeAlias = FloorPlanOpeningsConfig

DEFAULT_OPENING_CONFIG = FloorPlanOpeningsConfig(name="default_openings")

# Backward-compatible preset name.
DEFAULT_OPENING_PROFILE = DEFAULT_OPENING_CONFIG
