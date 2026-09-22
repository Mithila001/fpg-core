#!/usr/bin/env python3
# python generate_project_context.py

"""
AI-Optimized Python Project Structure Generator

Generates:
1. project_structure.txt
   - Flat relative path list of the repository
   - Designed for AI agents to quickly understand the project layout

Folders listed in INCLUDE_FOLDER_ONLY are included in the output, but their
contents are not scanned.

Run from the project root:

    python generate_project_context.py
"""

from __future__ import annotations

from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path

OUTPUT_STRUCTURE_FILE = "project_structure.txt"


# Files and folders that should be excluded completely.
#
# Both exact names and wildcard patterns are supported.
# Examples:
#   ".venv"      -> ignores an item named exactly ".venv"
#   "*.pyc"      -> ignores all Python bytecode files
#   "*.egg-info" -> ignores Python package metadata folders
IGNORED_ITEMS = {
    # Version control
    ".git",
    # Python virtual environments
    ".venv",
    "venv",
    "env",
    "virtualenv",
    ".envdir",
    "__pypackages__",
    # Python bytecode and interpreter caches
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".python-version",
    # Type-checker, formatter, and linter caches
    ".mypy_cache",
    ".pyright",
    ".ruff_cache",
    ".pylint.d",
    ".dmypy.json",
    "dmypy.json",
    # Test and coverage output
    ".pytest_cache",
    ".tox",
    ".nox",
    ".coverage",
    ".coverage.*",
    "coverage.xml",
    "htmlcov",
    "test-results",
    "test_results",
    # Build and packaging output
    "build",
    "dist",
    "sdist",
    "wheels",
    "*.egg-info",
    ".eggs",
    "pip-wheel-metadata",
    # Documentation build output
    "site",
    "_build",
    # Notebook and tool caches
    ".ipynb_checkpoints",
    ".hypothesis",
    ".cache",
    # Runtime-generated folders
    "logs",
    "log",
    "tmp",
    "temp",
    "cache",
    # Runtime-generated files
    "*.log",
    "*.tmp",
    "*.temp",
    # Local databases
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    # Environment files and local secrets
    ".env",
    ".env.*",
    "*.env",
    # IDE and editor metadata
    ".idea",
    ".vs",
    ".vscode-server",
    # Operating system metadata
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    # Generated output and this script
    OUTPUT_STRUCTURE_FILE,
    Path(__file__).name,
}


# Folders listed here will appear in project_structure.txt,
# but their files and subfolders will not be included.
#
# Example output:
#   .vscode/
#   data/
#   uploads/
INCLUDE_FOLDER_ONLY = {".vscode", "test", "docs", "output"}


def should_ignore(path: Path) -> bool:
    """
    Return True when the item's name matches an ignored name or pattern.
    """
    return any(fnmatch(path.name, pattern) for pattern in IGNORED_ITEMS)


def should_include_folder_only(path: Path) -> bool:
    """
    Return True when a directory should be listed without scanning its contents.
    """
    return path.is_dir() and any(
        fnmatch(path.name, pattern) for pattern in INCLUDE_FOLDER_ONLY
    )


def to_posix_relative(path: Path, root: Path) -> str:
    """
    Return a path relative to the project root using forward slashes.
    """
    return path.relative_to(root).as_posix()


def build_flat_structure(root: Path) -> list[str]:
    """
    Build a flat list of project files relative to the project root.

    Directories are traversed recursively unless they are ignored or included
    in INCLUDE_FOLDER_ONLY.
    """
    result: list[str] = []

    def walk(directory: Path) -> None:
        try:
            items = [item for item in directory.iterdir() if not should_ignore(item)]
        except PermissionError:
            relative_path = to_posix_relative(directory, root)
            print(f"Skipped inaccessible directory: {relative_path}")
            return
        except OSError as error:
            relative_path = to_posix_relative(directory, root)
            print(f"Skipped directory: {relative_path} ({error})")
            return

        # Directories first, then files, both alphabetically.
        items.sort(
            key=lambda item: (
                not item.is_dir(),
                item.name.lower(),
            )
        )

        for item in items:
            relative_path = to_posix_relative(item, root)

            # Do not follow symbolic links, which could create loops or
            # traverse files outside the project.
            if item.is_symlink():
                if item.is_dir():
                    result.append(f"{relative_path}/")
                else:
                    result.append(relative_path)
                continue

            if item.is_dir():
                if should_include_folder_only(item):
                    result.append(f"{relative_path}/")
                    continue

                walk(item)
                continue

            if item.is_file():
                result.append(relative_path)

    walk(root)
    return result


def write_structure_file(root: Path, paths: Iterable[str]) -> None:
    """
    Write the project structure to project_structure.txt.
    """
    output_path = root / OUTPUT_STRUCTURE_FILE
    content = "\n".join(paths)

    if content:
        content += "\n"

    output_path.write_text(content, encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parent

    print(f"Project root: {root}")

    structure = build_flat_structure(root)
    write_structure_file(root, structure)

    print(f"Created: {OUTPUT_STRUCTURE_FILE}")
    print(f"Items listed: {len(structure)}")
    print("Done.")


if __name__ == "__main__":
    main()
