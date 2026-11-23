"""The boundary decision follows what the adapter mapping grants, not the profile's words.

A checked-in repo profile can redefine (and lock) `permissions.profiles.workspace` as
`{write: false, shell: false}`; opencode/pi must still refuse host execution, because
their `workspace` mapping grants edit and bash (RFC §2.6.7).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from maggy.harness.loader import resolve_profile
from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.launch import Refused, resolve_launch
from worker_helpers import adapter_data
from worker_launch_helpers import profile, shipped

LYING = {"locked": ["permissions"],
         "permissions": {"profiles": {"workspace": {"write": False, "shell": False}}}}


def _repo_locked_profile(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".maggy").mkdir(parents=True)
    (repo / ".maggy" / "harness.yaml").write_text(yaml.safe_dump(LYING))
    home = tmp_path / "home.yaml"
    home.write_text("{}\n")
    return resolve_profile(personal_path=home, repo_root=repo).profile


@pytest.mark.parametrize("name", ["opencode", "pi"])
def test_repo_cannot_downgrade_workspace_to_dodge_host_refusal(tmp_path: Path, name: str):
    prof = _repo_locked_profile(tmp_path)
    assert prof.permissions.profiles["workspace"].write is False
    with pytest.raises(Refused, match="no native sandbox"):
        resolve_launch(shipped(name), prof, "workspace")


def test_unlisted_grant_defaults_to_write_and_shell():
    adapter = AdapterSpec.model_validate(adapter_data())
    grant = adapter.grant("workspace")
    assert (grant.write, grant.shell) == (True, True)


def test_declared_read_only_grant_runs_on_host_without_opt_in():
    adapter = AdapterSpec.model_validate(adapter_data(
        grants={"read_only": {"write": False, "shell": False}}))
    plan = resolve_launch(adapter, profile(), "read_only")
    assert plan.host_execution is False


def test_grants_must_name_a_mapped_permission():
    with pytest.raises(ValidationError, match="grants names unknown"):
        AdapterSpec.model_validate(adapter_data(grants={"ghost": {"write": False}}))


@pytest.mark.parametrize("name", ["claude", "opencode", "pi"])
def test_shipped_read_only_mappings_declare_no_write_no_shell(name):
    grant = shipped(name).grant("read_only")
    assert (grant.write, grant.shell) == (False, False)
