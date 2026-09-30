from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "docs" / "_generated" / "public_api_manifest.json"
REFERENCE_PATH = PROJECT_ROOT / "docs" / "PACKAGE_FEATURE_REFERENCE.md"


def test_public_api_manifest_is_current() -> None:
    result = subprocess.run(
        [sys.executable, "tools/generate_public_api_manifest.py", "--check"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _coverage_section(reference: str, module_name: str) -> str:
    marker = f"### `{module_name}` exports"
    start = reference.find(marker)
    assert start >= 0, f"missing coverage section for {module_name}"
    next_section = reference.find("\n### `", start + len(marker))
    return reference[start:] if next_section < 0 else reference[start:next_section]


def test_consumer_reference_covers_every_public_export() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    reference = REFERENCE_PATH.read_text(encoding="utf-8")

    missing: list[str] = []
    for module_name, module in manifest["modules"].items():
        section = _coverage_section(reference, module_name)
        for export in module["exports"]:
            if f"| `{export}` |" not in section:
                missing.append(f"{module_name}.{export}")

    assert not missing, "consumer reference is missing public exports:\n" + "\n".join(missing)
