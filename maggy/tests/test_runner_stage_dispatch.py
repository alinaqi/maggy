"""Stage dispatch (RFC §2.4): the runner holds stage:spec/plan/build (the profile can restrict
which), and items are driven by their `stage:<name>` capability."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from maggy.harness.schema import HarnessProfile
from maggy.runner.config import claim_capabilities
from runner_loop_helpers import EDIT_AGENT, make_rig
from worker_git_helpers import profile_data

ALL = ["maggy-runner", "stage:spec", "stage:plan", "stage:build", "project:shop"]


def test_runner_holds_every_stage_by_default() -> None:
    assert claim_capabilities("shop") == (ALL, ["maggy-runner", "project:shop"])


def test_profile_stages_restrict_the_held_capabilities() -> None:
    held, required = claim_capabilities("shop", ["build"])
    assert held == ["maggy-runner", "stage:build", "project:shop"]
    assert required == ["maggy-runner", "project:shop"]


def test_profile_worker_stages_default_and_validation() -> None:
    assert HarnessProfile.model_validate(profile_data()).worker.stages == ["spec", "plan", "build"]
    data = profile_data()
    data["worker"]["stages"] = ["deploy"]
    with pytest.raises(ValidationError):
        HarnessProfile.model_validate(data)


def _restricted(tmp_path: Path, stages: list[str], capabilities: list[str]):
    rig = make_rig(tmp_path, EDIT_AGENT, capabilities=capabilities)
    data = profile_data()
    data["worker"]["stages"] = stages
    profile = HarnessProfile.model_validate(data)
    rig.runner.config = replace(rig.runner.config, profile=profile)
    return rig


def test_runner_restricted_to_build_never_claims_a_spec_item(tmp_path: Path) -> None:
    rig = _restricted(tmp_path, ["build"], ["maggy-runner", "stage:spec", "project:demo"])
    assert rig.runner.run_once().outcome == "idle"
    assert rig.awg.items[rig.ref].state == "READY"


def test_runner_restricted_to_spec_never_claims_a_build_item(tmp_path: Path) -> None:
    rig = _restricted(tmp_path, ["spec"], ["maggy-runner", "stage:build", "project:demo"])
    assert rig.runner.run_once().outcome == "idle"
