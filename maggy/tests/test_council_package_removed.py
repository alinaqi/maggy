"""Guard: the dead maggy.council package stays deleted; the review council stays."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest

REVIEW_DIR = Path(__file__).resolve().parents[1] / "maggy" / "review"
KEPT = ("maggy.review.pipeline", "maggy.runner.pr_evidence.council")


def test_council_package_is_gone() -> None:
    assert importlib.util.find_spec("maggy.council") is None


@pytest.mark.parametrize("name", KEPT)
def test_review_council_still_imports(name: str) -> None:
    assert importlib.import_module(name)


def test_review_package_does_not_reference_council_package() -> None:
    hits = [
        p.name for p in REVIEW_DIR.rglob("*.py")
        if "maggy.council" in p.read_text(encoding="utf-8")
    ]
    assert hits == []
