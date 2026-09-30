from __future__ import annotations

import ast
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "src" / "fpg_core"
MANIFEST_PATH = PROJECT_ROOT / "docs" / "_generated" / "public_api_manifest.json"
REFERENCE_PATH = PROJECT_ROOT / "docs" / "PACKAGE_FEATURE_REFERENCE.md"


def _coverage_section(reference: str, module_name: str) -> str:
    marker = f"### `{module_name}` exports"
    start = reference.find(marker)
    assert start >= 0, f"missing coverage section for {module_name}"
    next_section = reference.find("\n### `", start + len(marker))
    return reference[start:] if next_section < 0 else reference[start:next_section]


def _definitions(module_name: str) -> dict[str, tuple[str, tuple[str, ...]]]:
    package_path = PACKAGE_ROOT / module_name.removeprefix("fpg_core.").replace(".", "/")
    if module_name == "fpg_core":
        paths = list(PACKAGE_ROOT.glob("*.py"))
    elif package_path.is_dir():
        paths = list(package_path.rglob("*.py"))
    else:
        return {}

    found: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                decorators = {
                    decorator.id
                    for decorator in node.decorator_list
                    if isinstance(decorator, ast.Name)
                }
                decorators.update(
                    decorator.func.id
                    for decorator in node.decorator_list
                    if isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Name)
                )
                if "dataclass" in decorators:
                    fields = tuple(
                        item.target.id
                        for item in node.body
                        if isinstance(item, ast.AnnAssign)
                        and isinstance(item.target, ast.Name)
                    )
                    found.setdefault(node.name, []).append(("dataclass", fields))
                    continue

                is_enum = any(
                    isinstance(base, ast.Name) and base.id.endswith("Enum")
                    for base in node.bases
                )
                if is_enum:
                    members = tuple(
                        item.targets[0].id
                        for item in node.body
                        if isinstance(item, ast.Assign)
                        and len(item.targets) == 1
                        and isinstance(item.targets[0], ast.Name)
                    )
                    found.setdefault(node.name, []).append(("enum", members))

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                arguments = tuple(
                    arg.arg
                    for arg in (
                        *node.args.posonlyargs,
                        *node.args.args,
                        *node.args.kwonlyargs,
                    )
                )
                found.setdefault(node.name, []).append(("function", arguments))

    return {name: values[0] for name, values in found.items() if len(values) == 1}


def test_documented_public_contract_rows_include_current_fields_and_arguments() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    reference = REFERENCE_PATH.read_text(encoding="utf-8")
    failures: list[str] = []

    for module_name, module in manifest["modules"].items():
        definitions = _definitions(module_name)
        section = _coverage_section(reference, module_name)
        for export in module["exports"]:
            definition = definitions.get(export)
            if definition is None:
                continue
            kind, names = definition
            row = next(
                (
                    line
                    for line in section.splitlines()
                    if line.startswith(f"| `{export}` |")
                ),
                "",
            )
            if not row:
                continue
            for name in names:
                if name not in row:
                    failures.append(f"{module_name}.{export}: missing {kind} item {name!r}")

    assert not failures, "documentation contract rows are stale:\n" + "\n".join(failures)
