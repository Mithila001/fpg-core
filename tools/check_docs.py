#!/usr/bin/env python3
"""Check canonical Markdown placement and local links without extra packages."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")
SKIP_DIRS = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".pytest_cache"}


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    )


def active_lines(path: Path):
    """Skip fenced examples; local path checks concern ordinary Markdown links."""
    in_fence = False
    fence_char = ""
    fence_length = 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if not in_fence:
                in_fence = True
                fence_char = token[0]
                fence_length = len(token)
            elif token[0] == fence_char and len(token) >= fence_length:
                in_fence = False
            continue
        if not in_fence:
            yield number, line


def check() -> list[str]:
    issues: list[str] = []
    files = markdown_files()
    agents = [p for p in files if p.name.lower() in {"agent.md", "agents.md"}]
    if agents != [ROOT / "AGENTS.md"]:
        issues.append("Expected exactly one repository agent file: AGENTS.md at root")

    for path in files:
        relative = path.relative_to(ROOT)
        if path.name not in {"README.md", "AGENTS.md"} and relative.parts[0] != "docs":
            issues.append(f"{relative}: non-README Markdown belongs under docs/")
        if relative.parts[:2] == ("docs", "personal"):
            continue  # Intentionally unmanaged user notes.
        for line_number, line in active_lines(path):
            for match in LINK_PATTERN.finditer(line):
                destination = match.group(1).strip().split(maxsplit=1)[0].strip("<>\"'")
                if not destination or destination.startswith("#"):
                    continue
                parsed = urlsplit(destination)
                if parsed.scheme or parsed.netloc:
                    continue  # Web and mail links are not part of this check.
                target_path = unquote(parsed.path)
                if target_path.startswith("/"):
                    issues.append(f"{relative}:{line_number}: local link must be relative: {destination}")
                    continue
                target = path.parent / target_path
                if not target.exists():
                    issues.append(f"{relative}:{line_number}: missing link target: {destination}")
    return issues


def main() -> int:
    issues = check()
    if issues:
        print("Documentation check failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Documentation placement and relative links are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
