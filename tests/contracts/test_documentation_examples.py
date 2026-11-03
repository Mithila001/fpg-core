"""Execute consumer examples with their documented prerequisites."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[2] / "docs"
FEATURES = sorted(
    path
    for path in (DOCS / "feature_documentations").glob("*.md")
    if path.name != "README.md"
)


def _example(document: Path, heading: str) -> str:
    text = document.read_text(encoding="utf-8")
    section = re.search(
        r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", text, re.M | re.S
    )
    assert section, f"missing {heading}: {document}"
    blocks = re.findall(r"```python\n(.*?)```", section[1], re.S)
    assert blocks, f"missing Python example: {document}"
    return "\n".join(blocks)


@pytest.mark.parametrize("document", FEATURES, ids=lambda path: path.stem)
def test_public_feature_usage_example(document: Path) -> None:
    namespace: dict[str, object] = {}
    fixtures = _example(DOCS / "API_GUIDE.md", "Reusable Example Fixtures")
    exec(compile(fixtures, "API_GUIDE.md", "exec"), namespace)
    if document.stem == "usable_land":
        prerequisite = _example(
            document.with_name("buildable_land.md"), "Usage example"
        )
        exec(compile(prerequisite, "buildable_land.md", "exec"), namespace)
    exec(compile(_example(document, "Usage example"), document.name, "exec"), namespace)
