"""Adapter env declarations: safe provider keys, auth files referenced read-only in place."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.env import auth_file_refs
from worker_helpers import adapter_data
from worker_launch_helpers import SHIPPED, shipped


def _env(**changes) -> dict:
    return adapter_data(env={"provider_keys": ["FAKE_API_KEY"], "auth_files": [], **changes})


@pytest.mark.parametrize("key", ["AWG_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "GITLAB_TOKEN",
                                 "AWS_SECRET_ACCESS_KEY", "SSH_AUTH_SOCK", "MAGGY_SECRET"])
def test_provider_key_cannot_smuggle_forbidden_credential(key):
    with pytest.raises(ValidationError, match=key):
        AdapterSpec.model_validate(_env(provider_keys=[key]))


@pytest.mark.parametrize("key", ["", "1KEY", "BAD-KEY", "A B"])
def test_provider_key_must_be_env_name(key):
    with pytest.raises(ValidationError, match="provider_keys"):
        AdapterSpec.model_validate(_env(provider_keys=[key]))


@pytest.mark.parametrize("path", ["auth.json", ".codex/auth.json", "~/../etc/auth", "~user/a",
                                  "/abs/../x"])
def test_auth_file_must_be_home_or_absolute_without_dotdot(path):
    with pytest.raises(ValidationError, match="auth_files"):
        AdapterSpec.model_validate(_env(auth_files=[path]))


@pytest.mark.parametrize("name", SHIPPED)
def test_shipped_auth_files_live_outside_any_workspace(name):
    for ref in auth_file_refs(shipped(name), "/home/dev"):
        assert ref.read_only is True
        assert ref.path.is_absolute()
        assert ref.path.is_relative_to("/home/dev")


def test_auth_file_refs_expand_home_and_are_read_only():
    spec = AdapterSpec.model_validate(_env(auth_files=["~/.fake/auth.json", "/etc/fake.json"]))
    refs = auth_file_refs(spec, "/home/dev")
    assert [str(ref.path) for ref in refs] == ["/home/dev/.fake/auth.json", "/etc/fake.json"]
    assert all(ref.read_only for ref in refs)


def test_more_than_one_provider_key_is_rejected():
    with pytest.raises(ValidationError, match="provider_keys"):
        AdapterSpec.model_validate(_env(provider_keys=["OPENAI_API_KEY", "CODEX_API_KEY"]))
