"""Guard: the dead maggy.contracts package stays deleted; pipeline contracts stay."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "maggy"


def test_contracts_package_is_gone() -> None:
    assert importlib.util.find_spec("maggy.contracts") is None
    assert not (PACKAGE_DIR / "contracts").exists()


def test_pipeline_execution_contract_still_imports() -> None:
    module = importlib.import_module("maggy.pipeline.contracts")
    assert module.ExecutionContract


def test_no_kept_code_references_contracts_package() -> None:
    hits = [
        str(p.relative_to(PACKAGE_DIR)) for p in PACKAGE_DIR.rglob("*.py")
        if "maggy.contracts" in p.read_text(encoding="utf-8")
    ]
    assert hits == []
