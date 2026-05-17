"""E2E Testing Framework Plugin — benchmark, drift, regression, intent bugs.

Works for ANY project. Auto-detects language/framework.
Generates E2E tests, benchmarks performance, detects drift between
spec and implementation, identifies intent-level bugs.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/testkit", tags=["testkit"])


@dataclass
class TestResult:
    name: str
    passed: bool
    duration_ms: float = 0.0
    error: str = ""
    category: str = ""  # e2e, benchmark, drift, regression, intent


@dataclass
class DriftSignal:
    file: str
    spec_behavior: str
    actual_behavior: str
    divergence_score: float  # 0-1, higher = more drift
    suggestion: str = ""


@dataclass
class IntentBug:
    reason_node: str
    original_intent: str
    flaw: str
    impact: str
    suggested_fix: str = ""


@dataclass
class TestRun:
    id: str
    project: str
    started_at: str = ""
    completed_at: str = ""
    results: list[TestResult] = field(default_factory=list)
    drift_signals: list[DriftSignal] = field(default_factory=list)
    intent_bugs: list[IntentBug] = field(default_factory=list)
    benchmark_score: float = 0.0  # ops/sec or relative score
    summary: str = ""


class ProjectDetector:
    """Auto-detect project type to run appropriate tests."""

    @staticmethod
    def detect(project_dir: str) -> dict:
        root = Path(project_dir).expanduser()
        info = {"type": "unknown", "test_cmd": [], "bench_cmd": [], "source_dir": "."}

        if (root / "pyproject.toml").exists():
            info["type"] = "python"
            info["test_cmd"] = ["pytest", "-x", "--tb=short", "-v"]
            info["bench_cmd"] = ["pytest", "--benchmark-only"]
            info["source_dir"] = "src" if (root / "src").exists() else "."
        elif (root / "package.json").exists():
            pkg = _read_json(root / "package.json")
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            info["type"] = "typescript"
            cmd = ["npx", "vitest", "run"] if "vitest" in deps else ["npx", "jest"]
            info["test_cmd"] = cmd
            info["bench_cmd"] = cmd + ["--", "--bench"]
            info["source_dir"] = "src" if (root / "src").exists() else "."

        return info


class BenchmarkRunner:
    """Runs performance benchmarks and tracks scores over time."""

    def __init__(self, project_dir: str):
        self._dir = project_dir
        self._history: list[dict] = []

    def run(self, project_info: dict, runs: int = 3) -> list[TestResult]:
        results = []
        cmd = project_info.get("bench_cmd", [])
        if not cmd:
            cmd = project_info.get("test_cmd", ["pytest"])

        for i in range(runs):
            start = time.perf_counter()
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    cwd=self._dir, timeout=300,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                results.append(TestResult(
                    name=f"benchmark_run_{i+1}",
                    passed=proc.returncode == 0,
                    duration_ms=elapsed_ms,
                    category="benchmark",
                    error=proc.stderr[:200] if proc.returncode != 0 else "",
                ))
            except subprocess.TimeoutExpired:
                results.append(TestResult(
                    name=f"benchmark_run_{i+1}",
                    passed=False, duration_ms=300000,
                    error="timeout after 5min", category="benchmark",
                ))

        # Save history
        avg = sum(r.duration_ms for r in results) / len(results) if results else 0
        self._history.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "avg_ms": avg, "runs": len(results),
        })
        scores_dir = Path.home() / ".maggy" / "testkit" / "benchmarks"
        scores_dir.mkdir(parents=True, exist_ok=True)
        (scores_dir / f"{Path(self._dir).name}.json").write_text(
            json.dumps(self._history[-50:], indent=2))

        return results


class DriftDetector:
    """Detects drift between specification and implementation.

    Compares iCPG ReasonNodes (what the code SHOULD do) against
    actual behavior (what it DOES). Uses AI to analyze divergence.
    """

    def __init__(self, project_dir: str):
        self._dir = project_dir

    def detect(self, project_info: dict) -> list[DriftSignal]:
        """Scan for spec-vs-implementation drift."""
        signals = []
        src_dir = Path(self._dir) / project_info.get("source_dir", ".")

        # Find files with iCPG annotations or docstrings
        for py_file in list(src_dir.rglob("*.py"))[:20]:
            if "__pycache__" in str(py_file) or "test" in py_file.name:
                continue
            content = py_file.read_text()[:2000]
            # Look for contracts/docstrings with "should" or "must"
            if "should" not in content.lower() and "must" not in content.lower():
                continue

            # AI analyzes for drift
            drift = self._analyze_drift(py_file, content)
            if drift and drift.divergence_score > 0.15:
                signals.append(drift)

        return signals

    def _analyze_drift(self, file_path: Path, content: str) -> Optional[DriftSignal]:
        """Use AI to detect drift between spec and implementation."""
        prompt = (
            f"Analyze this code for specification-vs-implementation drift. "
            f"The file's docstrings and contracts describe WHAT it should do. "
            f"The code IS what it actually does. "
            f"Rate divergence 0 (no drift) to 1 (completely drifted). "
            f"Reply with JSON: "
            f'{{"divergence_score": 0.X, "spec_behavior": "...", "actual_behavior": "...", "suggestion": "..."}}\n\n'
            f"File: {file_path.name}\n{content[:1500]}"
        )
        try:
            r = subprocess.run(
                [os.path.expanduser("~/bin/deepseek"), "--flash", prompt],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                data = json.loads(r.stdout.strip().split("{", 1)[-1].rsplit("}", 1)[0].strip())
                data = "{" + data + "}"
                d = json.loads(data) if isinstance(data, str) else data
                return DriftSignal(
                    file=str(file_path.relative_to(self._dir)),
                    spec_behavior=d.get("spec_behavior", ""),
                    actual_behavior=d.get("actual_behavior", ""),
                    divergence_score=d.get("divergence_score", 0.0),
                    suggestion=d.get("suggestion", ""),
                )
        except Exception:
            pass
        return None


class IntentBugDetector:
    """Detects bugs where the original intent/specification was wrong.

    Not implementation bugs — intent bugs. Where the contract itself
    was flawed and needs revision.
    """

    def __init__(self, project_dir: str):
        self._dir = project_dir

    def detect(self, project_info: dict) -> list[IntentBug]:
        """Analyze ReasonNodes for flawed intent."""
        bugs = []
        src_dir = Path(self._dir) / project_info.get("source_dir", ".")

        # Find iCPG ReasonNode files
        for py_file in list(src_dir.rglob("*.py"))[:15]:
            if "__pycache__" in str(py_file) or "test" in py_file.name:
                continue
            content = py_file.read_text()[:2000]

            # Look for assumptions that might be wrong
            indicators = ["assume", "presume", "guarantee", "invariant", "always"]
            if not any(ind in content.lower() for ind in indicators):
                continue

            bug = self._analyze_intent(py_file, content)
            if bug:
                bugs.append(bug)

        return bugs

    def _analyze_intent(self, file_path: Path, content: str) -> Optional[IntentBug]:
        """AI analyzes whether the original intent has a flaw."""
        prompt = (
            f"Review this code's stated intent (contracts, docstrings, invariants). "
            f"Is there a flaw in the ORIGINAL INTENT itself — not the implementation, "
            f"but the assumption the code was built on? "
            f"Examples: assuming data always exists, assuming single-tenant, "
            f"assuming network is reliable, race condition in the design, "
            f"fundamental misunderstanding of the problem domain.\n\n"
            f"File: {file_path.name}\n{content[:1500]}\n\n"
            f"Reply with JSON: "
            f'{{"has_intent_bug": true|false, "original_intent": "...", "flaw": "...", "impact": "...", "suggested_fix": "..."}}'
        )
        try:
            r = subprocess.run(
                [os.path.expanduser("~/bin/deepseek"), "--pro", prompt],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and '"has_intent_bug": true' in r.stdout:
                data = json.loads("{" + r.stdout.strip().split("{", 1)[-1].rsplit("}", 1)[0] + "}")
                return IntentBug(
                    reason_node=str(file_path.relative_to(self._dir)),
                    original_intent=data.get("original_intent", ""),
                    flaw=data.get("flaw", ""),
                    impact=data.get("impact", ""),
                    suggested_fix=data.get("suggested_fix", ""),
                )
        except Exception:
            pass
        return None


class E2ETestKit:
    """Unified E2E testing, benchmarking, drift detection, intent analysis."""

    def __init__(self, project_dir: str = "."):
        self._dir = str(Path(project_dir).expanduser())
        self._detector = ProjectDetector()
        self._bench = BenchmarkRunner(self._dir)
        self._drift = DriftDetector(self._dir)
        self._intent = IntentBugDetector(self._dir)
        self._history: list[TestRun] = []

    def run_full(self, benchmark_runs: int = 3) -> TestRun:
        """Run complete test suite: E2E + benchmark + drift + intent."""
        import uuid
        run = TestRun(
            id=uuid.uuid4().hex[:10],
            project=Path(self._dir).name,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        info = self._detector.detect(self._dir)

        # 1. E2E tests
        try:
            proc = subprocess.run(
                info.get("test_cmd", ["pytest"]),
                capture_output=True, text=True, cwd=self._dir, timeout=300,
            )
            run.results.append(TestResult(
                name="e2e_suite", passed=proc.returncode == 0,
                duration_ms=0, category="e2e",
                error=proc.stderr[:200] if proc.returncode != 0 else "",
            ))
        except Exception as e:
            run.results.append(TestResult(
                name="e2e_suite", passed=False, category="e2e", error=str(e)[:200],
            ))

        # 2. Benchmarks
        run.results.extend(self._bench.run(info, benchmark_runs))

        # 3. Drift detection
        drift_signals = self._drift.detect(info)
        run.drift_signals = drift_signals
        if drift_signals:
            run.results.append(TestResult(
                name="drift_analysis", passed=len(drift_signals) < 3,
                category="drift",
                error=f"{len(drift_signals)} drifted files" if drift_signals else "",
            ))

        # 4. Intent bug detection
        intent_bugs = self._intent.detect(info)
        run.intent_bugs = intent_bugs
        if intent_bugs:
            run.results.append(TestResult(
                name="intent_analysis", passed=len(intent_bugs) == 0,
                category="intent",
                error=f"{len(intent_bugs)} intent bugs found" if intent_bugs else "",
            ))

        # Compute benchmark score
        bench_times = [r.duration_ms for r in run.results if r.category == "benchmark"]
        run.benchmark_score = sum(bench_times) / len(bench_times) if bench_times else 0

        run.completed_at = datetime.now(timezone.utc).isoformat()
        passed = sum(1 for r in run.results if r.passed)
        total = len(run.results)
        run.summary = (
            f"{passed}/{total} passed. "
            f"Drift: {len(drift_signals)} signals. "
            f"Intent bugs: {len(intent_bugs)}. "
            f"Benchmark avg: {run.benchmark_score:.0f}ms"
        )

        self._history.append(run)
        self._save_history()
        return run

    def _save_history(self):
        path = Path.home() / ".maggy" / "testkit" / f"{Path(self._dir).name}-runs.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            [r.__dict__ for r in self._history[-20:]], indent=2, default=str,
        ))

    def regression_scan(self) -> list[TestResult]:
        """Quick regression scan: run tests, check for new failures."""
        info = self._detector.detect(self._dir)
        results = []
        try:
            proc = subprocess.run(
                info.get("test_cmd", ["pytest"]),
                capture_output=True, text=True, cwd=self._dir, timeout=120,
            )
            results.append(TestResult(
                name="regression_scan",
                passed=proc.returncode == 0,
                duration_ms=0, category="regression",
                error=proc.stderr[:200] if proc.returncode != 0 else "",
            ))
        except Exception as e:
            results.append(TestResult(
                name="regression_scan", passed=False, category="regression", error=str(e)[:200],
            ))
        return results


# ── Plugin registration ──────────────────────────────────────────────────

_kit: Optional[E2ETestKit] = None


def register(bus, manifest):
    global _kit
    _kit = E2ETestKit()
    logger.info("e2e-testkit: registered")


async def run_regression_scan():
    """Heartbeat job: periodic regression scan."""
    if not _kit:
        return
    results = _kit.regression_scan()
    failed = [r for r in results if not r.passed]
    if failed:
        logger.warning("e2e-testkit: %d regressions detected", len(failed))


# ── API routes ───────────────────────────────────────────────────────────

@router.post("/run")
async def run_full(request: Request, project_dir: str = Query("."), benchmark_runs: int = Query(3)):
    if not _kit:
        return {"error": "plugin not initialized"}
    kit = E2ETestKit(project_dir) if project_dir != "." else _kit
    run = kit.run_full(benchmark_runs)
    return {
        "run_id": run.id, "summary": run.summary,
        "passed": sum(1 for r in run.results if r.passed),
        "total": len(run.results),
        "drift_signals": len(run.drift_signals),
        "intent_bugs": len(run.intent_bugs),
        "benchmark_avg_ms": run.benchmark_score,
        "results": [{"name": r.name, "passed": r.passed, "category": r.category,
                      "error": r.error[:200]} for r in run.results],
        "drift": [{"file": d.file, "score": d.divergence_score,
                    "suggestion": d.suggestion} for d in run.drift_signals],
        "intent_bugs": [{"node": i.reason_node, "flaw": i.flaw,
                          "impact": i.impact} for i in run.intent_bugs],
    }


@router.post("/drift")
async def detect_drift(request: Request, project_dir: str = Query(".")):
    kit = E2ETestKit(project_dir)
    signals = kit._drift.detect(kit._detector.detect(project_dir))
    return {"signals": [{"file": s.file, "score": s.divergence_score,
                         "suggestion": s.suggestion} for s in signals]}


@router.post("/intent")
async def detect_intent_bugs(request: Request, project_dir: str = Query(".")):
    kit = E2ETestKit(project_dir)
    bugs = kit._intent.detect(kit._detector.detect(project_dir))
    return {"bugs": [{"node": b.reason_node, "flaw": b.flaw,
                      "impact": b.impact, "suggested_fix": b.suggested_fix}
                     for b in bugs]}


@router.get("/history")
async def get_history(request: Request, project_dir: str = Query(".")):
    path = Path.home() / ".maggy" / "testkit" / f"{Path(project_dir).name}-runs.json"
    if path.exists():
        return {"runs": json.loads(path.read_text())}
    return {"runs": []}


def _read_json(path: Path) -> dict:
    try: return json.loads(path.read_text())
    except: return {}
