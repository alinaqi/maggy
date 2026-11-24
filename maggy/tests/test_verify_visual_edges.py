"""Visual check edge cases that need no browser: an unavailable browser is PENDING (never
PASS) and a route can only name a file inside the candidate checkout."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from maggy.runner.stages.visual_models import VisualSpec
from maggy.runner.verify import visual
from maggy.runner.verify.browser import BrowserUnavailable
from maggy.runner.verify.visual import VisualJob, check_visual
from regression_helpers import commit_all, write_files
from verify_helpers import GOOD_PAGE, visual_entry
from worker_git_helpers import git, profile


def _no_browser(*_: object) -> list:
    raise BrowserUnavailable("chromium cannot launch: missing")


def test_unavailable_browser_is_pending_not_pass(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(visual, "render", _no_browser)
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write_files(repo, {"checkout.html": GOOD_PAGE})
    sha = commit_all(repo, "page")
    job = VisualJob(repo=repo, sha=sha, work_dir=tmp_path / "work", profile=profile())
    results = check_visual(job, visual_entry())
    assert {r.verdict for r in results} == {"PENDING"} and "chromium" in results[0].reason


def test_route_outside_the_checkout_is_rejected() -> None:
    for route in ("../secret.html", "/etc/passwd", "http://localhost:3000/"):
        with pytest.raises(ValidationError):
            VisualSpec.model_validate({**visual_entry()["visual"], "route": route})


def test_unsafe_baseline_names_are_rejected() -> None:
    assert str(visual.baseline_path("AC3", "mobile")) == ".maggy/baselines/AC3-mobile.png"
    with pytest.raises(ValueError, match="unsafe"):
        visual.baseline_path("../AC3", "mobile")
