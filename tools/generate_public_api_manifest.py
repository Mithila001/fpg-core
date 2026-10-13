#!/usr/bin/env python3
"""Generate a static manifest of supported package-root exports.

The script parses ``__all__`` declarations without importing fpg-core, so it is safe
to run before heavyweight runtime dependencies such as OR-Tools are available.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "src" / "fpg_core"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "_generated" / "public_api_manifest.json"


def _read_all(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        value = node.value
        if not isinstance(value, (ast.List, ast.Tuple)):
            raise ValueError(f"{path}: __all__ must be a literal list/tuple for manifest generation")
        exports: list[str] = []
        for item in value.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                raise ValueError(f"{path}: __all__ contains a non-literal export")
            exports.append(item.value)
        if len(exports) != len(set(exports)):
            raise ValueError(f"{path}: __all__ contains duplicate exports")
        return exports
    raise ValueError(f"{path}: missing __all__")


def _project_version() -> str:
    data = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def build_manifest() -> dict[str, Any]:
    modules: dict[str, dict[str, Any]] = {}

    module_paths: list[tuple[str, Path]] = [("fpg_core", PACKAGE_ROOT / "__init__.py")]
    for child in sorted(PACKAGE_ROOT.iterdir(), key=lambda path: path.name):
        init_path = child / "__init__.py"
        if child.is_dir() and init_path.is_file():
            module_paths.append((f"fpg_core.{child.name}", init_path))

    for module_name, init_path in module_paths:
        exports = _read_all(init_path)
        modules[module_name] = {
            "source": init_path.relative_to(PROJECT_ROOT).as_posix(),
            "export_count": len(exports),
            "exports": exports,
        }

    feature_modules = [
        name for name in modules if name not in {"fpg_core", "fpg_core.domain"}
    ]
    return {
        "schema_version": 1,
        "package_version": _project_version(),
        "feature_modules": feature_modules,
        "modules": modules,
    }


def render_manifest() -> str:
    return json.dumps(build_manifest(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the committed manifest does not match current exports",
    )
    args = parser.parse_args()

    rendered = render_manifest()
    if args.check:
        if not OUTPUT_PATH.is_file():
            print(f"missing public API manifest: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
            return 1
        if OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            print("public API manifest is stale; run tools/generate_public_api_manifest.py")
            return 1
        print("public API manifest is current")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
