"""Inspect built Core archives for application/agent content and dependencies."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath


def check_archive(path: Path) -> None:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            metadata = archive.read(
                next(n for n in names if n.endswith(".dist-info/METADATA"))
            ).decode()
    else:
        with tarfile.open(path) as archive:
            names = archive.getnames()
            member = archive.extractfile(
                next(n for n in names if n.endswith("/PKG-INFO") and n.count("/") == 1)
            )
            assert member is not None
            metadata = member.read().decode()
        names = [name.partition("/")[2] for name in names]

    forbidden = {"fpg-lab", "fpg_lab", ".agents", ".venv", "personal", "data"}
    for name in names:
        assert not forbidden.intersection(PurePosixPath(name).parts), (
            f"{path}: unwanted content {name}"
        )
    assert any(name.endswith("fpg_core/py.typed") for name in names), (
        f"{path}: missing typed package"
    )
    message = Parser().parsestr(metadata)
    assert message["Name"] == "fpg-core", path
    for requirement in message.get_all("Requires-Dist", []):
        assert not requirement.lower().startswith(
            ("fpg-lab", "nicegui", "plotly", "sqlalchemy")
        ), requirement


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    wheels = list(args.directory.glob("fpg_core-*.whl"))
    sources = list(args.directory.glob("fpg_core-*.tar.gz"))
    if not wheels or not sources:
        parser.error("Build both Core wheel and source archive first: python -m build")
    for path in sorted(wheels + sources):
        check_archive(path)
        print(f"Core-only distribution verified: {path.name}")


if __name__ == "__main__":
    main()
