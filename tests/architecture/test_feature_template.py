from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "fpg_core"
FEATURES = {
    "buildable_land",
    "usable_land",
    "floor_plan_preprocessing",
    "candidate_search",
    "candidate_scoring",
    "floor_plan_solver",
    "floor_plan_post_processing",
    "floor_plan_openings",
    "floor_plan_scoring",
}
REQUIRED_FILES = {"README.md", "__init__.py", "api.py", "exceptions.py"}
REQUIRED_README_HEADINGS = {"## Guide", "## AI Instructions"}


def test_feature_roots_follow_required_structure() -> None:
    for feature in sorted(FEATURES):
        feature_root = PACKAGE_ROOT / feature
        assert feature_root.is_dir(), f"Missing feature folder: {feature}"

        existing = {path.name for path in feature_root.iterdir() if path.is_file()}
        missing = REQUIRED_FILES - existing
        assert not missing, f"{feature} is missing: {sorted(missing)}"

        readme = (feature_root / "README.md").read_text(encoding="utf-8")
        assert readme.startswith("# "), f"{feature}/README.md needs a title"
        for heading in REQUIRED_README_HEADINGS:
            assert heading in readme, f"{feature}/README.md is missing {heading!r}"


def test_features_do_not_import_other_feature_internals() -> None:
    for feature in sorted(FEATURES):
        feature_root = PACKAGE_ROOT / feature
        for source_file in feature_root.rglob("*.py"):
            module_name = _module_name(source_file)
            tree = ast.parse(source_file.read_text(encoding="utf-8"))

            for node in ast.walk(tree):
                imported_modules = _imported_modules(node, module_name)
                for imported_module in imported_modules:
                    imported_feature = _feature_from_module(imported_module)
                    if imported_feature is None or imported_feature == feature:
                        continue
                    if imported_module != f"fpg_core.{imported_feature}.api":
                        raise AssertionError(
                            f"{source_file.relative_to(PACKAGE_ROOT)} imports another "
                            f"feature's internal module: {imported_module}"
                        )


def _module_name(source_file: Path) -> str:
    relative = source_file.relative_to(PACKAGE_ROOT).with_suffix("")
    parts = ("fpg_core", *relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imported_modules(node: ast.AST, module_name: str) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)

    if not isinstance(node, ast.ImportFrom) or not node.module:
        return ()

    if node.level == 0:
        return (node.module,)

    current_package = module_name.rpartition(".")[0]
    relative_name = f"{'.' * node.level}{node.module}"
    return (resolve_name(relative_name, current_package),)


def _feature_from_module(module_name: str) -> str | None:
    parts = module_name.split(".")
    if len(parts) >= 2 and parts[0] == "fpg_core" and parts[1] in FEATURES:
        return parts[1]
    return None
