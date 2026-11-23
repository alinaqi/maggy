"""Build hook: bundle the repo's skills/ and rules/ into the package.

The harness reads skills and instruction includes from them. In a source
checkout they sit next to this project (../skills, ../rules); an installed
wheel has no checkout, so they are copied into maggy/harness/library (git
ignored, shipped via package-data) before setuptools collects package data.
Building from an sdist, where ../skills does not exist, keeps the copy the
sdist already carries. All metadata lives in pyproject.toml.
"""

from __future__ import annotations

import shutil
from pathlib import Path

LIBRARY = ("skills", "rules")


def sync_library(repo: Path, package: Path) -> None:
    """Copy <repo>/skills and <repo>/rules into <package>/harness/library."""
    library = package / "harness" / "library"
    for name in LIBRARY:
        source = repo / name
        if source.is_dir():
            shutil.rmtree(library / name, ignore_errors=True)
            shutil.copytree(source, library / name, ignore=shutil.ignore_patterns("__pycache__", ".*"))


if __name__ == "__main__":
    from setuptools import setup

    here = Path(__file__).resolve().parent
    sync_library(here.parent, here / "maggy")
    setup()
