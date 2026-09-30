from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "fpg_core"
FEATURE_NAMES = {
    path.name
    for path in PACKAGE_ROOT.iterdir()
    if path.is_dir() and (path / "__init__.py").is_file() and path.name != "domain"
}


def _private_cross_feature_imports(feature: str, path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if len(parts) < 2 or parts[0] != "fpg_core":
                    continue
                target = parts[1]
                if target not in FEATURE_NAMES or target == feature:
                    continue
                if len(parts) > 2 and parts[2:] != ["api"]:
                    violations.append(alias.name)

        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue

        if node.level == 0:
            parts = node.module.split(".")
            if len(parts) < 2 or parts[0] != "fpg_core":
                continue
            target = parts[1]
            suffix = parts[2:]
        elif node.level >= 2:
            parts = node.module.split(".")
            target = parts[0]
            suffix = parts[1:]
        else:
            continue

        if target not in FEATURE_NAMES or target == feature:
            continue
        if suffix and suffix != ["api"]:
            violations.append(node.module)

    return violations


def test_features_do_not_import_other_feature_internals() -> None:
    failures: list[str] = []
    for feature in sorted(FEATURE_NAMES):
        for path in sorted((PACKAGE_ROOT / feature).rglob("*.py")):
            for imported in _private_cross_feature_imports(feature, path):
                failures.append(
                    f"{path.relative_to(PACKAGE_ROOT)} imports private cross-feature module {imported!r}"
                )

    assert not failures, "\n".join(failures)
