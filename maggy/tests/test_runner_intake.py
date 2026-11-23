"""`maggy run intake`: wraps `awg sync github --label --capability --json` (RFC §2.4 intake)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from maggy.cli import app
from tests.runner_awg_helpers import FakeAwgBin

REPORT = {"created": 1, "updated": 0, "skipped": 1,
          "refs": {"created": [{"issue": 4, "ref": "AWG-3"}], "updated": [], "skipped": []}}


@pytest.fixture
def awg(tmp_path: Path) -> FakeAwgBin:
    fake = FakeAwgBin(tmp_path)
    fake.reply("sync", REPORT)
    return fake


def _intake(awg: FakeAwgBin, checkout: Path, *extra: str):
    args = ["run", "intake", "--repo", "acme/shop", "--awg-bin", str(awg.path),
            "--checkout", str(checkout), *extra]
    return CliRunner().invoke(app, args)


def _repo_profile(checkout: Path, intake: dict) -> None:
    (checkout / ".maggy").mkdir(parents=True, exist_ok=True)
    (checkout / ".maggy" / "harness.yaml").write_text(yaml.safe_dump({"intake": intake}))


def test_intake_wraps_awg_sync_with_label_and_runner_capabilities(awg, tmp_path: Path) -> None:
    result = _intake(awg, tmp_path, "--label", "factory")
    assert result.exit_code == 0, result.output
    [call] = awg.calls()
    assert call["argv"] == ["sync", "github", "--label=factory", "--capability=maggy-runner",
                            "--capability=stage:spec",
                            f"--capability=project:{tmp_path.name}", "--json", "--", "acme/shop"]
    assert "created 1" in result.output and "AWG-3" in result.output


def test_intake_takes_label_and_capabilities_from_repo_profile(awg, tmp_path: Path) -> None:
    _repo_profile(tmp_path, {"source": "github", "label": "bot",
                             "capabilities": ["maggy-runner", "stage:spec"]})
    result = _intake(awg, tmp_path, "--project", "SHOP")
    assert result.exit_code == 0, result.output
    assert awg.calls()[0]["argv"] == [
        "sync", "github", "--label=bot", "--capability=maggy-runner",
        "--capability=stage:spec", "--capability=project:SHOP", "--project=SHOP", "--json", "--",
        "acme/shop"]


def test_intake_refuses_without_a_label(awg, tmp_path: Path) -> None:
    result = _intake(awg, tmp_path)
    assert result.exit_code == 2
    assert "label" in result.output and awg.calls() == []


@pytest.mark.parametrize("repo", ["-x/y", "acme", "acme/shop;rm", "a/b/c"])
def test_intake_refuses_malformed_repo(awg, tmp_path: Path, repo: str) -> None:
    args = ["run", "intake", "--repo", repo, "--label", "f", "--awg-bin", str(awg.path),
            "--checkout", str(tmp_path)]
    assert CliRunner().invoke(app, args).exit_code == 2
    assert awg.calls() == []


def test_intake_reports_awg_failure(awg, tmp_path: Path) -> None:
    awg.reply("sync", rc=1, stderr='{"error": {"code": "forbidden", "message": "no admin"}}')
    result = _intake(awg, tmp_path, "--label", "factory")
    assert result.exit_code == 2 and "forbidden" in result.output
