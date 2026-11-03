from __future__ import annotations

import ast
import importlib
from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from fpg_lab.core.settings import ROOT, get_settings
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec, CoreConfigurationError
from scripts.verify_fpg_core import verify_local_core


def test_core_origin_and_public_import_boundaries() -> None:
    verify_local_core()
    modules = {}
    for directory in (ROOT / "fpg_lab", ROOT / "scripts"):
        for path in directory.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    imports = [(alias.name, []) for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imports = [(node.module or "", [alias.name for alias in node.names])]
                else:
                    continue
                for name, symbols in imports:
                    parts = name.split(".")
                    if parts[0] != "fpg_core":
                        continue
                    assert len(parts) <= 2 or (len(parts) == 3 and parts[-1] == "api"), (path, name)
                    public_name = name.removesuffix(".api")
                    if public_name not in modules:
                        modules[public_name] = importlib.import_module(public_name)
                    public = modules[public_name]
                    assert all(symbol in public.__all__ for symbol in symbols), (
                        path,
                        name,
                        symbols,
                    )


@pytest.mark.parametrize("schema", [2, 3, 4, 5])
def test_old_lab_profiles_are_rejected_without_mutating_input(schema: int) -> None:
    codec = CoreConfigCodec()
    payload = codec.default_configuration().payload
    payload["schema_version"] = schema
    original = deepcopy(payload)
    with pytest.raises(CoreConfigurationError, match="schema_version"):
        codec.validate_payload(payload)
    assert payload == original


def test_settings_paths_do_not_depend_on_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Control environment inputs; loading still uses Lab's explicit .env path.
    monkeypatch.setenv("FPG_LAB_DATABASE_URL", "sqlite:///./data/path-check.db")
    get_settings.cache_clear()
    try:
        from_lab = get_settings()
        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()
        assert get_settings() == from_lab
        assert Path(make_url(from_lab.database_url).database) == ROOT / "data/path-check.db"
    finally:
        get_settings.cache_clear()
