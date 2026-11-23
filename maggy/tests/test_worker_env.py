"""Worker and check env scrubbing: allowlist plus declared provider keys only (RFC §2.6.1)."""

from __future__ import annotations

import random
import string

import pytest

from maggy.worker.env import ALLOWED_NAMES, build_check_env, build_worker_env
from worker_launch_helpers import shipped

SAFE = {"PATH": "/usr/bin:/bin", "HOME": "/home/dev", "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8", "TERM": "xterm", "TMPDIR": "/tmp/x", "SHELL": "/bin/zsh",
        "USER": "dev"}
SECRETS = {"AWG_TOKEN": "a", "GITHUB_TOKEN": "g", "GH_TOKEN": "h", "AWS_SECRET_ACCESS_KEY": "s",
           "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "k", "SSH_AUTH_SOCK": "/tmp/ssh",
           "FOO_TOKEN": "f", "GITLAB_TOKEN": "l", "MAGGY_API_SECRET": "m", "DB_PASSWORD": "p",
           "LC_SECRET_TOKEN": "t", "AWS_PROFILE": "prod", "GEMINI_API_KEY": "gm",
           "CODEX_API_KEY": "cx", "CLAUDE_CODE_OAUTH_TOKEN": "co", "OPENROUTER_API_KEY": "or"}
BASE = {**SAFE, **SECRETS}


def test_claude_worker_keeps_only_its_key_and_allowlist():
    env = build_worker_env(shipped("claude"), BASE)
    assert env == {**SAFE, "ANTHROPIC_API_KEY": "k"}


def test_codex_worker_keeps_only_openai_key_and_allowlist():
    env = build_worker_env(shipped("codex"), BASE)
    assert env == {**SAFE, "OPENAI_API_KEY": "o"}


@pytest.mark.parametrize("name", ["claude", "codex", "opencode", "pi"])
def test_every_shipped_worker_gets_at_most_one_provider_key(name):
    env = build_worker_env(shipped(name), BASE)
    assert len(set(env) & set(SECRETS)) <= 1


def test_check_env_has_no_credentials_and_throwaway_home():
    env = build_check_env(BASE, "/tmp/check-home")
    assert env == {**SAFE, "HOME": "/tmp/check-home"}
    assert not set(env) & set(SECRETS)


def test_declared_key_absent_from_base_is_not_invented():
    env = build_worker_env(shipped("codex"), SAFE)
    assert env == SAFE


def test_inputs_are_not_mutated():
    base = dict(BASE)
    build_worker_env(shipped("claude"), base)
    build_check_env(base, "/tmp/h")
    assert base == BASE


def _random_names(seed: int, count: int = 400) -> list[str]:
    rng = random.Random(seed)
    alphabet = string.ascii_uppercase + string.digits + "_"
    stems = ["AWG_", "GITHUB_", "GH_", "GITLAB_", "AWS_", "SSH_", "MAGGY_", "LC_", "NPM_",
             "OPENAI_", "ANTHROPIC_", "CLAUDE_", "", "XDG_", "NODE_"]
    tails = ["", "_TOKEN", "_SECRET", "_KEY", "_API_KEY", "_PASSWORD"]
    return [rng.choice(stems) + "".join(rng.choices(alphabet, k=rng.randint(1, 8)))
            + rng.choice(tails) for _ in range(count)]


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("name", ["claude", "codex", "opencode", "pi"])
def test_nothing_outside_allowlist_or_declared_keys_survives(seed, name):
    adapter = shipped(name)
    base = {key: "v" for key in _random_names(seed)} | BASE
    env = build_worker_env(adapter, base)
    for key in env:
        assert key in ALLOWED_NAMES or key.startswith("LC_") or key in adapter.env.provider_keys
    extras = {key for key in env if key not in SAFE and not key.startswith("LC_")}
    assert extras <= set(adapter.env.provider_keys)


@pytest.mark.parametrize("seed", range(5))
def test_check_env_survivors_are_allowlisted_and_never_secret(seed):
    base = {key: "v" for key in _random_names(seed)} | BASE
    env = build_check_env(base, "/tmp/h")
    assert set(env) <= set(SAFE) | {key for key in base if key.startswith("LC_")}
    banned = ("TOKEN", "SECRET", "KEY", "PASSWORD")
    assert not [key for key in env if any(word in key for word in banned)]
