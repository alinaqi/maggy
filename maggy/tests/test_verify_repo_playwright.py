"""A repo with its own Playwright config: the visual criterion runs its named test with
`--update-snapshots=none` (factory doc §5); a missing snapshot is PENDING, never PASS."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from maggy.harness.schema import HarnessProfile
from maggy.runner.verify.visual import VisualJob, check_visual
from regression_helpers import commit_all, write_files
from verify_helpers import visual_entry
from worker_git_helpers import git, profile_data, write_script

FAKE_PLAYWRIGHT = """
import json, os, sys
from pathlib import Path
ARGV_OUT = {argv_out!r}
mode = Path("mode.txt").read_text().strip()
Path(ARGV_OUT).write_text(json.dumps(sys.argv[1:]))
body = {"pass": "", "diff": '<failure message="expect(page).toHaveScreenshot() failed">'
        '12 pixels are different</failure>',
        "missing": '<failure message="A snapshot doesn\\'t exist at /x/AC3.png">'
        'expect(page).toHaveScreenshot</failure>'}[mode]
report = f'<testsuites><testsuite><testcase name="AC3">{body}</testcase></testsuite></testsuites>'
Path(os.environ["PLAYWRIGHT_JUNIT_OUTPUT_NAME"]).write_text(report)
sys.exit(0 if mode == "pass" else 1)
"""


def _job(tmp_path: Path, mode: str) -> VisualJob:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write_files(repo, {"playwright.config.ts": "export default {}\n", "mode.txt": mode})
    sha = commit_all(repo, "repo with playwright")
    body = FAKE_PLAYWRIGHT.replace("{argv_out!r}", repr(str(tmp_path / "argv.json")))
    script = write_script(tmp_path, "fake_playwright", body)
    data = profile_data()
    data["validation"]["regression"] = {
        "runner": "playwright", "command": shlex.join([sys.executable, str(script)])}
    return VisualJob(repo=repo, sha=sha, work_dir=tmp_path / "work",
                     profile=HarnessProfile.model_validate(data))


@pytest.mark.parametrize(("mode", "verdict"), [("pass", "PASS"), ("diff", "FAIL"),
                                               ("missing", "PENDING")])
def test_repo_playwright_test_maps_to_visual_verdicts(
        tmp_path: Path, mode: str, verdict: str) -> None:
    job = _job(tmp_path, mode)
    [result] = check_visual(job, visual_entry() | {"visual": None})
    assert result.verdict == verdict and result.viewport == "repo-playwright"
    argv = (tmp_path / "argv.json").read_text()
    assert "--update-snapshots=none" in argv and "AC3 expired coupon layout" in argv
    assert result.artifacts["log"].is_file()


def test_visual_criterion_without_a_check_is_pending(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write_files(repo, {"README.md": "x\n"})
    sha = commit_all(repo, "no playwright")
    job = VisualJob(repo=repo, sha=sha, work_dir=tmp_path / "w",
                    profile=HarnessProfile.model_validate(profile_data()))
    [result] = check_visual(job, visual_entry() | {"visual": None})
    assert result.verdict == "PENDING" and "no visual check" in result.reason
