from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from tools import check_docs
from tools.check_distribution import check_archive


def test_documentation_roots_skills_and_local_artifact_exclusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    for name in (
        "AGENTS.md",
        "fpg-lab/AGENTS.md",
        "fpg-lab/docs/guide.md",
        ".agents/skills/example/SKILL.md",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Guide\n", encoding="utf-8")
    local = tmp_path / "fpg-lab/.venv/irrelevant.md"
    local.parent.mkdir(parents=True)
    local.write_text("[ignored](missing.md)", encoding="utf-8")
    assert check_docs.check() == []
    (tmp_path / "fpg-lab/docs/guide.md").write_text(
        "[broken](missing.md)", encoding="utf-8"
    )
    assert any("missing link target" in issue for issue in check_docs.check())


def test_distribution_checker_rejects_lab_content_and_dependencies(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "fpg_core-0.2.0-py3-none-any.whl"
    for extra, requires, valid in (
        (None, "optuna>=3.6", True),
        ("fpg_lab/main.py", "optuna", False),
        (None, "nicegui", False),
    ):
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("fpg_core/py.typed", "")
            archive.writestr(
                "fpg_core-0.2.0.dist-info/METADATA",
                f"Name: fpg-core\nRequires-Dist: {requires}\n",
            )
            if extra:
                archive.writestr(extra, "")
        if valid:
            check_archive(wheel)
        else:
            with pytest.raises(AssertionError):
                check_archive(wheel)
