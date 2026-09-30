from __future__ import annotations

import ast
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _source_checkout_version() -> str:
    path = PROJECT_ROOT / "src" / "fpg_core" / "__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            values.append(node.value.value)
    assert len(values) == 1, "expected one literal source-checkout __version__ fallback"
    return values[0]


def test_package_versions_and_consumer_reference_stay_in_sync() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(pyproject["project"]["version"])
    reference = (PROJECT_ROOT / "docs" / "PACKAGE_FEATURE_REFERENCE.md").read_text(
        encoding="utf-8"
    )

    assert _source_checkout_version() == version
    assert f"Distribution name/version: `fpg-core` `{version}`" in reference
