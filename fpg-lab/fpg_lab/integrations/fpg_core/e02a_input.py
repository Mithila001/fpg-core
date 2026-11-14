"""Load E02A's portable hint maps without accessing saved Lab presets."""

import json
from pathlib import Path

from fpg_lab.core.settings import ROOT
from fpg_lab.integrations.fpg_core.p01b_input import validate_export


HINT_MAPS_PATH = ROOT / "experiments" / "e02a" / "hint_maps.json"


def load_hint_maps(path: Path = HINT_MAPS_PATH) -> dict:
    try:
        maps = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load hint maps from {path}: {exc}") from exc
    if not isinstance(maps, dict) or any(not isinstance(k, str) or not k.strip() or k == "__all__" for k in maps):
        raise ValueError("Hint maps must be an object with nonempty names")
    return maps


def select_hint_maps(maps: dict, name: str | None) -> dict:
    if name is None:
        if len(maps) != 4:
            raise ValueError("All maps requires exactly four hint maps")
        selected = maps
    elif name in maps:
        selected = {name: maps[name]}
    else:
        raise ValueError(f"Hint map {name!r} was not found")
    for map_name, document in selected.items():
        try:
            validate_export(document)
        except Exception as exc:
            raise ValueError(f"Invalid hint map {map_name!r}: {exc}") from exc
    return selected
