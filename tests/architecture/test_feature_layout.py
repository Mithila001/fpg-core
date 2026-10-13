from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "fpg_core"
REQUIRED_FEATURE_FILES = {"README.md", "__init__.py", "api.py", "exceptions.py"}


def test_feature_packages_have_consistent_public_boundary() -> None:
    missing: list[str] = []
    for path in sorted(PACKAGE_ROOT.iterdir()):
        if not path.is_dir() or path.name == "domain" or not (path / "__init__.py").is_file():
            continue
        names = {item.name for item in path.iterdir() if item.is_file()}
        for required in sorted(REQUIRED_FEATURE_FILES - names):
            missing.append(f"{path.name}/{required}")

    assert not missing, "missing feature boundary files:\n" + "\n".join(missing)


def test_package_source_contains_no_repository_instruction_templates() -> None:
    forbidden = {"FEATURE_TEMPLATE.md", "Package_Documentation_Template.md"}
    present = [name for name in forbidden if (PACKAGE_ROOT / name).exists()]
    assert not present, f"move repository guidance out of src/fpg_core: {present}"
