"""IFS Scorer — combines F1 × F2 × F3 into composite."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_here = Path(__file__).resolve().parent


def _ensure(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, _here / filename,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _ensure("telos_models", "models.py")
_reader_mod = _ensure("cortex_reader", "cortex_reader.py")
_conf = _ensure("telos_conformance", "plane_conformance.py")
_val = _ensure("telos_validation", "plane_validation.py")
_integ = _ensure("telos_integrity", "plane_integrity.py")


def score_project(project_dir: str) -> Any:
    resolved = Path(project_dir).resolve()
    project_name = resolved.name or str(resolved)
    test_result = _conf.run_tests(project_dir)
    f1 = _conf.compute_f1(test_result)

    reader = _reader_mod.CortexReader(project_dir)
    if reader.available:
        reasons = reader.get_reasons()
        drift = reader.get_active_drift()
        orphans = reader.get_orphan_symbols()
        stale = reader.get_stale_reasons(days=7)
        reason_dicts = [{"id": r.id} for r in reasons]
        f2 = _val.compute_f2(drift, reason_dicts)
        integ = _integ.compute_f3(
            reasons, orphans, stale,
        )
        f3 = integ["f3"]
        violations = integ["violations"]
        reader.close()
    else:
        f2, f3 = 1.0, 1.0
        drift, violations = [], []
        reasons = []

    ifs = _models.IFSScore(
        f1=f1, f2=f2, f3=f3,
        details={
            "test_result": test_result,
            "drift_count": len(drift),
            "violation_count": len(violations),
        },
    )
    return _models.TelosResult(
        project=project_name,
        ifs=ifs,
        test_results=test_result,
        drift_signals=drift,
        intent_bugs=violations,
        anti_criteria_violations=[],
    )
