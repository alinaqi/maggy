"""Auto-install missing Python packages on demand."""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def _pip_install(pip_name: str) -> None:
    """Run pip install for a package."""
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", pip_name, "-q"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def ensure_import(
    package: str, pip_name: str | None = None,
):
    """Import *package*, auto-installing via pip if missing.

    Returns the imported module. Uses pip_name for install
    when the pip package differs from the import name
    (e.g. ``ensure_import("docx", pip_name="python-docx")``).
    """
    try:
        return importlib.import_module(package)
    except ImportError:
        name = pip_name or package
        logger.info("Installing %s …", name)
        _pip_install(name)
        return importlib.import_module(package)
