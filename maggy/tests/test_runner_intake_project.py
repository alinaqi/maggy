"""`maggy run intake` binds items to the runner's project and honours the pause flag."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from maggy.cli import app
from maggy.runner.control import set_paused
from tests.runner_awg_helpers import FakeAwgBin

REPORT = {"created": 0, "updated": 0, "skipped": 0, "refs": {}}


@pytest.fixture
def awg(tmp_path: Path) -> FakeAwgBin:
    fake = FakeAwgBin(tmp_path)
    fake.reply("sync", REPORT)
    return fake


def _intake(awg: FakeAwgBin, checkout: Path, *extra: str):
    args = ["run", "intake", "--repo", "acme/shop", "--label", "factory", "--awg-bin",
            str(awg.path), "--checkout", str(checkout), "--state-dir",
            str(checkout / "state"), *extra]
    return CliRunner().invoke(app, args)


def test_intake_tags_items_with_the_given_project(awg, tmp_path: Path) -> None:
    result = _intake(awg, tmp_path, "--project", "SHOP")
    assert result.exit_code == 0, result.output
    assert awg.calls()[0]["argv"] == [
        "sync", "github", "--label=factory", "--capability=maggy-runner",
        "--capability=stage:spec", "--capability=project:SHOP", "--project=SHOP", "--json",
        "--", "acme/shop"]


def test_intake_defaults_the_project_to_the_checkout_name(awg, tmp_path: Path) -> None:
    checkout = tmp_path / "shop"
    checkout.mkdir()
    result = _intake(awg, checkout)
    assert result.exit_code == 0, result.output
    argv = awg.calls()[0]["argv"]
    assert "--capability=project:shop" in argv
    assert not any(arg.startswith("--project=") for arg in argv)


def test_intake_is_refused_while_the_project_is_paused(awg, tmp_path: Path) -> None:
    set_paused(tmp_path / "state", "SHOP", True)
    result = _intake(awg, tmp_path, "--project", "SHOP")
    assert result.exit_code == 2 and "paused" in result.output
    assert awg.calls() == []


def test_intake_runs_when_another_project_is_paused(awg, tmp_path: Path) -> None:
    set_paused(tmp_path / "state", "OTHER", True)
    assert _intake(awg, tmp_path, "--project", "SHOP").exit_code == 0
    assert len(awg.calls()) == 1


def test_intake_refuses_a_malformed_project_key(awg, tmp_path: Path) -> None:
    result = _intake(awg, tmp_path, "--project", "../x")
    assert result.exit_code == 2 and awg.calls() == []
