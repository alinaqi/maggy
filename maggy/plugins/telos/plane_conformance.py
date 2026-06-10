"""Plane 1 — Conformance: F1 = passed_tests / total_tests."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _detect_runner(project_dir: str) -> list[str]:
    root = Path(project_dir)
    if (root / "pyproject.toml").exists():
        return ["python3", "-m", "pytest", "-v", "--tb=line"]
    if (root / "package.json").exists():
        return ["npx", "vitest", "run"]
    return ["python3", "-m", "pytest", "-v", "--tb=line"]


def _parse_pytest_output(output: str) -> dict[str, int]:
    passed = 0
    failed = 0
    errors = 0
    m = re.search(r"(\d+) passed", output)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", output)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+) error", output)
    if m:
        errors = int(m.group(1))
    return {
        "passed": passed,
        "failed": failed + errors,
    }


def run_tests(project_dir: str) -> dict:
    root = Path(project_dir)
    if not root.is_dir():
        return {"passed": 0, "failed": 0, "error": "not a dir"}
    cmd = _detect_runner(project_dir)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=120,
        )
        combined = proc.stdout + proc.stderr
        counts = _parse_pytest_output(combined)
        return {**counts, "error": ""}
    except Exception as e:
        return {
            "passed": 0,
            "failed": 0,
            "error": str(e)[:200],
        }


def compute_f1(result: dict) -> float:
    if result.get("error"):
        return 0.0
    total = result["passed"] + result["failed"]
    if total == 0:
        return 1.0
    return result["passed"] / total
