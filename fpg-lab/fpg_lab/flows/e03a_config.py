"""Configuration boundary for the standalone room-sizing experiment."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from math import ceil, floor
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Annotated, Literal

from fpg_core.domain import RoomSizeSpec, RoomType, RoomWidthAxis
from pydantic import BaseModel, ConfigDict, Field, model_validator

from fpg_lab.core.settings import ROOT

CONFIG_PATH = ROOT / "experiments" / "e03a" / "config.json"
E02A_PATH = ROOT / "experiments" / "e02a" / "config.json"
ROOM_TYPES = tuple(room for room in RoomType if room is not RoomType.HALLWAY)
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Count = Annotated[int, Field(strict=True, ge=0)]
# ponytail: serializes saves within one Lab process; use a file lock for cross-process writers.
_SAVE_LOCK = Lock()


def room_label(room: str) -> str:
    return room.replace("_", " ").title()


def width_axis(room: RoomType) -> RoomWidthAxis:
    return RoomWidthAxis.X if room in (RoomType.GARAGE, RoomType.VERANDA) else RoomWidthAxis.ANY


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Aspect(Document):
    min_ratio: Positive
    max_ratio: Positive

    @model_validator(mode="after")
    def ordered(self) -> Aspect:
        if self.min_ratio > self.max_ratio:
            raise ValueError("Minimum aspect ratio exceeds maximum")
        return self


class Room(Document):
    min_width: Positive
    max_width: Positive
    min_area: Positive
    max_area: Positive
    minimum_count: Count
    maximum_count: Count
    count: Count
    aspect: Aspect | Literal["inherit"] | None = "inherit"

    @model_validator(mode="after")
    def ordered(self) -> Room:
        if self.min_width > self.max_width or self.min_area > self.max_area:
            raise ValueError("Room width and area minimums must be at most their maximums")
        if not self.minimum_count <= self.count <= self.maximum_count:
            raise ValueError("Selected count is outside its room count limits")
        return self

    def size_spec(self, room: RoomType) -> RoomSizeSpec:
        return RoomSizeSpec(
            ceil(self.min_width),
            floor(self.max_width),
            ceil(self.min_area),
            floor(self.max_area),
            width_axis(room),
        )


class CrossRule(Document):
    compared_type: RoomType
    reference_type: RoomType
    min_ratio: Positive | None = None
    max_ratio: Positive | None = None

    @model_validator(mode="after")
    def ordered(self) -> CrossRule:
        if self.min_ratio is None and self.max_ratio is None:
            raise ValueError("Enter a minimum or maximum area ratio")
        if (
            self.min_ratio is not None
            and self.max_ratio is not None
            and self.min_ratio > self.max_ratio
        ):
            raise ValueError("Minimum area ratio exceeds maximum")
        if self.compared_type == self.reference_type:
            raise ValueError("Use a same-type tolerance on the diagonal")
        return self


class SameRule(Document):
    room_type: RoomType
    maximum_spread_ratio: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class Configuration(Document):
    schema_version: Literal[1] = 1
    project_units_per_meter: Literal[10] = 10
    aspect_precision: Annotated[int, Field(strict=True, gt=0)] = 1000
    default_aspect: Aspect | None
    limit_attached_bathrooms: Annotated[bool, Field(strict=True)]
    rooms: dict[RoomType, Room]
    cross_type_rules: tuple[CrossRule, ...] = ()
    same_type_rules: tuple[SameRule, ...] = ()

    @model_validator(mode="after")
    def valid_scenario(self) -> Configuration:
        if set(self.rooms) != set(ROOM_TYPES):
            raise ValueError("Define each of the eight regular room types exactly once")
        bedrooms = self.rooms[RoomType.BEDROOM].count
        attached = self.rooms[RoomType.ATTACHED_BATHROOM].count
        if self.limit_attached_bathrooms and attached > bedrooms:
            raise ValueError("Attached bathroom count cannot exceed bedroom count")
        cross = {(rule.compared_type, rule.reference_type) for rule in self.cross_type_rules}
        same = {rule.room_type for rule in self.same_type_rules}
        if len(cross) != len(self.cross_type_rules) or len(same) != len(self.same_type_rules):
            raise ValueError("Each matrix cell can contain only one rule")
        if any(a not in self.rooms or b not in self.rooms for a, b in cross) or not same <= set(
            self.rooms
        ):
            raise ValueError("Relationships require regular room types")
        return self

    def aspect_for(self, room: RoomType) -> Aspect | None:
        override = self.rooms[room].aspect
        return self.default_aspect if override == "inherit" else override


def _unique_fields(items: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(items)
    if len(items) != len(result):
        raise ValueError("JSON objects must have unique field names")
    return result


def parse(contents: bytes) -> Configuration:
    return Configuration.model_validate(
        json.loads(
            contents.decode("utf-8-sig"), parse_float=Decimal, object_pairs_hook=_unique_fields
        )
    )


def export(config: Configuration) -> bytes:
    return (config.model_dump_json(indent=2) + "\n").encode("utf-8")


def save(config: Configuration, expected: bytes | None, path: Path = CONFIG_PATH) -> bytes:
    content = export(Configuration.model_validate(config.model_dump()))
    with _SAVE_LOCK:
        current = path.read_bytes() if path.exists() else None
        if current != expected:
            raise ValueError(
                "The saved file changed. Export your draft or reset to load the latest file."
            )
        temporary = None
        try:
            with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return content


def import_e02a(draft: dict, path: Path = E02A_PATH) -> Configuration:
    """Read only settings the experiment uses. Leave the source and draft untouched."""
    try:
        source = json.loads(
            path.read_text(encoding="utf-8-sig"),
            parse_float=Decimal,
            object_pairs_hook=_unique_fields,
        )["configuration"]
        pre = source["preprocessing"]
        stage = source["floor_plan_solver"]["initial"]
        aspect_rules = [
            rule["settings"] for rule in stage["hard_constraints"] if rule["key"] == "aspect_ratio"
        ]
        if len(aspect_rules) > 1:
            raise ValueError("E02A has duplicate initial room aspect rules")
        aspect = aspect_rules[0] if aspect_rules else None
        defaults = (
            {"min_ratio": aspect.get("min_ratio", 0.35), "max_ratio": aspect.get("max_ratio", 2.85)}
            if aspect is not None
            else None
        )
        overrides = aspect.get("overrides", {}) if aspect is not None else {}
        exclusions = (
            set(aspect.get("excluded_room_types", ()))
            | set(aspect.get("hallway_room_types", ("hallway",)))
            if aspect is not None
            else set()
        )
        for name in exclusions | overrides.keys():
            RoomType(name)
        mandatory = {RoomType(name) for name in pre["mandatory_room_types"]}
        policy = pre["excess_attached_bathrooms"]
        if policy not in ("reject", "remove"):
            raise ValueError("Unknown attached bathroom count policy")
        rooms = {}
        for room_type in ROOM_TYPES:
            (size,) = [
                row
                for row in pre["room_sizes"]
                if row["room_type"] == room_type and row["size"] == pre["default_room_size"]
            ]
            (rule,) = [row for row in pre["room_count_rules"] if row["room_type"] == room_type]
            low = max(CountModel(value=rule["minimum"]).value, int(room_type in mandatory))
            high = CountModel(value=rule["maximum"]).value
            selectable = rule.get("client_selectable", True)
            if type(selectable) is not bool or low > high or (not selectable and low):
                raise ValueError(f"Invalid count rule for {room_type.value}")
            if not selectable:
                high = 0
            old = draft.get("rooms", {}).get(room_type.value, {}).get("count", low)
            try:
                old = CountModel(value=old).value
            except ValueError:
                old = low
            bounds: str | dict | None = "inherit"
            if room_type in exclusions:
                bounds = None
            elif room_type in overrides:
                bounds = {**(defaults or {}), **overrides[room_type]}
            rooms[room_type.value] = {
                **{key: size[key] for key in ("min_width", "max_width", "min_area", "max_area")},
                "minimum_count": low,
                "maximum_count": high,
                "count": min(max(old, low), high),
                "aspect": bounds,
            }

        if policy == "reject":
            attached = rooms["attached_bathroom"]
            bedroom = rooms["bedroom"]
            bedroom["count"] = max(bedroom["count"], attached["minimum_count"])
            attached["count"] = min(attached["count"], bedroom["count"])

        return Configuration.model_validate(
            {
                "project_units_per_meter": source["project_units_per_meter"],
                "aspect_precision": aspect.get("precision", 1000) if aspect is not None else 1000,
                "default_aspect": defaults,
                "limit_attached_bathrooms": policy == "reject",
                "rooms": rooms,
                "cross_type_rules": draft.get("cross_type_rules", ()),
                "same_type_rules": draft.get("same_type_rules", ()),
            }
        )
    except (OSError, KeyError, ValueError, TypeError, AttributeError, ArithmeticError) as exc:
        raise ValueError(f"Cannot import E02A: {exc}") from exc


class CountModel(Document):
    value: Count
