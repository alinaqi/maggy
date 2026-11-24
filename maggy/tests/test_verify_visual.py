"""Visual checks in a fresh worktree at the candidate (RFC §2.5 Verify, factory doc §5).

Browser tests: they run here (cached chromium) and skip with a reason where Playwright or
its browsers are missing, so CI stays hermetic.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from maggy.runner.verify.visual import VisualJob, check_visual
from regression_helpers import commit_all, write_files
from verify_helpers import GOOD_PAGE, OVERLAP_PAGE, RECOLOURED_PAGE, browser, visual_entry
from worker_git_helpers import git, profile

__all__ = ["browser"]


def _size(path: Path) -> tuple[int, int]:
    from PIL import Image  # the browser fixture skips first when maggy[visual] is missing
    return Image.open(path).size


def _repo(tmp_path: Path, page: str) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write_files(repo, {"checkout.html": page})
    return repo, commit_all(repo, "page")


def _job(work_dir: Path, repo: Path, sha: str) -> VisualJob:
    return VisualJob(repo=repo, sha=sha, work_dir=work_dir, profile=profile())


def _approve_all(repo: Path, results: list) -> str:
    """Commit every proposed image as the approved baseline (what an approval does)."""
    for result in results:
        target = repo / ".maggy" / "baselines" / f"AC3-{result.viewport}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(result.artifacts["proposed"], target)
    return commit_all(repo, "baselines")


@pytest.mark.usefixtures("browser")
def test_missing_baseline_is_pending_with_a_proposed_image(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path, GOOD_PAGE)
    results = check_visual(_job(tmp_path / "work", repo, sha), visual_entry())
    assert [(r.viewport, r.verdict) for r in results] == [("mobile", "PENDING"),
                                                          ("desktop", "PENDING")]
    proposed = results[0].artifacts["proposed"]
    assert proposed.is_relative_to(tmp_path / "work") and _size(proposed) == (390, 844)
    assert "baseline" in results[0].reason
    assert git(repo, "worktree", "list").count("\n") == 0  # the fresh checkout was removed


@pytest.mark.usefixtures("browser")
def test_passes_against_the_approved_baseline(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path, GOOD_PAGE)
    candidate = _approve_all(repo, check_visual(_job(tmp_path / "work", repo, sha), visual_entry()))
    results = check_visual(_job(tmp_path / "again", repo, candidate), visual_entry())
    assert {r.verdict for r in results} == {"PASS"}
    assert results[0].artifacts["actual"].is_file()


@pytest.mark.usefixtures("browser")
def test_pixel_diff_fails_with_expected_actual_and_diff(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path, GOOD_PAGE)
    _approve_all(repo, check_visual(_job(tmp_path / "work", repo, sha), visual_entry()))
    write_files(repo, {"checkout.html": RECOLOURED_PAGE})
    candidate = commit_all(repo, "recolour the total")
    results = check_visual(_job(tmp_path / "diff", repo, candidate), visual_entry())
    assert {r.verdict for r in results} == {"FAIL"}
    assert set(results[0].artifacts) == {"expected", "actual", "diff"}
    assert all(path.is_file() for path in results[0].artifacts.values())
    assert "pixels differ" in results[0].reason


@pytest.mark.usefixtures("browser")
def test_layout_assertion_failure_fails_with_artifacts(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path, OVERLAP_PAGE)
    results = check_visual(_job(tmp_path / "work", repo, sha), visual_entry())
    assert {r.verdict for r in results} == {"FAIL"}
    assert "below" in results[0].reason and "#coupon" in results[0].reason
    assert results[0].artifacts["actual"].is_file() and "proposed" not in results[0].artifacts


@pytest.mark.usefixtures("browser")
def test_page_cannot_reach_the_network(tmp_path: Path) -> None:
    page = GOOD_PAGE.replace("</body>", '<img src="http://example.invalid/x.png"></body>')
    repo, sha = _repo(tmp_path, page)
    results = check_visual(_job(tmp_path / "work", repo, sha), visual_entry())
    assert {r.verdict for r in results} == {"PENDING"}  # renders; the request was aborted
