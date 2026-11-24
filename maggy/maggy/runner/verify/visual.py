"""Visual checks for `evidence: visual` criteria, in a FRESH worktree at the candidate
(RFC §2.5 Verify, §2.6.2; factory doc §5).

Per viewport: a failed layout assertion -> FAIL (actual kept); no approved baseline at
`.maggy/baselines/<criterion>-<viewport>.png` in the candidate -> PENDING with a PROPOSED
baseline in the work dir (never written to the repo here); a diff above `max_diff_pixels`
-> FAIL with expected/actual/diff; else PASS. Without a `visual` spec the repo's own
Playwright config runs the named test (`repo_playwright`); with neither, PENDING.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from maggy.runner.stages.visual_models import VisualSpec
from maggy.runner.verify.browser import BrowserUnavailable, Capture, render
from maggy.runner.verify.models import ViewResult, VisualJob
from maggy.runner.verify.pixels import compare
from maggy.runner.verify.repo_playwright import run_repo_visual
from maggy.worker.launch import refuse_host_checks
from maggy.worker.worktree import add_detached, remove_worktree

__all__ = ["ViewResult", "VisualJob", "baseline_path", "check_visual"]

BASELINES = Path(".maggy") / "baselines"
SAFE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def baseline_path(criterion: str, viewport: str) -> Path:
    """`.maggy/baselines/<criterion>-<viewport>.png`; ValueError for a name that could
    leave the baselines dir."""
    name = f"{criterion}-{viewport}"
    if not SAFE.match(name):
        raise ValueError(f"unsafe baseline name {name!r}")
    return BASELINES / f"{name}.png"


def check_visual(job: VisualJob, entry: dict) -> list[ViewResult]:
    criterion = str(entry["criterion_id"])
    if not entry.get("visual"):
        return [run_repo_visual(job, entry)]
    spec = VisualSpec.model_validate(entry["visual"])
    refuse_host_checks(job.profile, f"visual check {criterion}")
    out = job.work_dir / "visual" / criterion
    checkout = add_detached(job.repo, job.sha, out / "checkout")
    try:
        captures = render(spec, checkout, out)
        return [_judge(capture, (criterion, checkout, out), spec) for capture in captures]
    except BrowserUnavailable as exc:
        return [ViewResult(criterion, vp.name, "PENDING", str(exc), blocked=True)
                for vp in spec.viewports]
    finally:
        remove_worktree(job.repo, checkout)


def _judge(capture: Capture, where: tuple[str, Path, Path], spec: VisualSpec) -> ViewResult:
    criterion, checkout, out = where
    actual = {"actual": capture.image} if capture.image else {}
    if capture.problems or capture.image is None:
        reason = "; ".join(capture.problems) or "no screenshot"
        return ViewResult(criterion, capture.viewport, "FAIL", reason, actual)
    baseline = checkout / baseline_path(criterion, capture.viewport)
    if not baseline.is_file():
        proposed = out / f"{criterion}-{capture.viewport}-proposed.png"
        shutil.copyfile(capture.image, proposed)
        return ViewResult(criterion, capture.viewport, "PENDING",
                          "no approved baseline; proposed one awaits approval",
                          {**actual, "proposed": proposed})
    return _diff(capture, (criterion, baseline, out), spec.max_diff_pixels)


def _diff(capture: Capture, where: tuple[str, Path, Path], allowed: int) -> ViewResult:
    criterion, baseline, out = where
    expected = out / f"{capture.viewport}-expected.png"
    shutil.copyfile(baseline, expected)
    diff = out / f"{capture.viewport}-diff.png"
    changed = compare(expected, capture.image, diff)
    files = {"expected": expected, "actual": capture.image}
    if changed is None:
        return ViewResult(criterion, capture.viewport, "FAIL", "size differs from baseline", files)
    if changed > allowed:
        return ViewResult(criterion, capture.viewport, "FAIL",
                          f"{changed} pixels differ from the approved baseline (allowed {allowed})",
                          {**files, "diff": diff})
    return ViewResult(criterion, capture.viewport, "PASS", "matches the approved baseline", files)
