from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "fpg_core"
FORBIDDEN_ROOTS = {
    "app",
    "fastapi",
    "pydantic",
}


def _production_modules() -> tuple[Path, ...]:
    return tuple(PACKAGE_ROOT.rglob("*.py"))


def test_core_does_not_import_server_modules() -> None:
    violations: list[str] = []

    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported = (node.module,)

            for name in imported:
                root = name.split(".", maxsplit=1)[0]
                if root in FORBIDDEN_ROOTS:
                    violations.append(f"{path.relative_to(PACKAGE_ROOT)}: {name}")
                elif root == "fpg_server":
                    violations.append(f"{path.relative_to(PACKAGE_ROOT)}: {name}")

    assert not violations, "\n".join(violations)
