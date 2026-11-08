"""Validated Lab inputs shared by the UI, scripts, and services."""

from __future__ import annotations

from typing import Annotated

from fpg_core.domain import RoomType
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from fpg_lab.integrations.fpg_core.config_models import SystemConfigurationDocument


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


PositiveFinite = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]


class FloorLimits(StrictModel):
    max_width: PositiveFinite
    max_length: PositiveFinite


class RequestedRoom(StrictModel):
    room_type: RoomType
    id: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1)
    requested_size: str | None = Field(default=None, min_length=1)


class FloorPlanRequest(StrictModel):
    floor_limits: FloorLimits
    aspect_ratio: PositiveFinite | str
    rooms: list[RequestedRoom] = Field(min_length=1)


class ManualRoomHint(StrictModel):
    room_id: str = Field(min_length=1)
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class ManualHallwayHint(StrictModel):
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class ManualHints(StrictModel):
    rooms: list[ManualRoomHint] = Field(min_length=1)
    hallways: list[ManualHallwayHint] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_room_ids(self) -> ManualHints:
        ids = [item.room_id for item in self.rooms]
        if len(ids) != len(set(ids)):
            raise ValueError("room hint IDs must be unique")
        return self


class RunInput(StrictModel):
    floor_plan_request: FloorPlanRequest
    should_save: bool = True
    system_configuration_id: int | None = Field(default=None, gt=0)


class P01AInput(RunInput):
    trial_count: int = Field(default=100, ge=1, le=100_000)


class P01BInput(StrictModel):
    preset_id: int = Field(gt=0)
    disable_hints: bool = False
    refinement_rounds: int = Field(default=0, ge=0, le=5, strict=True)
    iterations: int = Field(default=1, ge=1, le=100, strict=True)
    initial_time_limit: PositiveFinite
    system_configuration_id: int | None = Field(default=None, gt=0)


P01CInput = P01AInput


class FloorPlanTemplateCreate(StrictModel):
    name: Name
    description: Description | None = None
    template_data: FloorPlanRequest
    schema_version: str = "1"


FloorPlanTemplateUpdate = FloorPlanTemplateCreate


class SystemConfigurationCreate(StrictModel):
    name: Name
    description: Description | None = None
    configuration_data: SystemConfigurationDocument
    schema_version: str = "6"


SystemConfigurationUpdate = SystemConfigurationCreate
