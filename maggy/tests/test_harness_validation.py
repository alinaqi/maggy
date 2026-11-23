"""Harness profile validation: clear errors naming the file and key path."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_helpers import repo_file, write_yaml

from maggy.harness import HarnessConfigError, resolve_profile
from maggy.harness.secrets import is_secret_key


def _error(tmp_path: Path, personal: object, repo: object = None) -> tuple[str, Path]:
    root = tmp_path / "repo"
    if repo is not None:
        write_yaml(repo_file(root), repo)
    home_file = write_yaml(tmp_path / "home" / "harness.yaml", personal or "")
    with pytest.raises(HarnessConfigError) as info:
        resolve_profile(repo_root=root, personal_path=home_file)
    bad = repo_file(root) if repo is not None else home_file
    return str(info.value), bad


def test_unknown_top_level_key_rejected(tmp_path: Path) -> None:
    message, bad = _error(tmp_path, {"colour": "blue"})
    assert str(bad) in message and "colour" in message


def test_unknown_nested_key_rejected(tmp_path: Path) -> None:
    message, bad = _error(tmp_path, {"gates": {"quality": {"max_lines": 5}}})
    assert str(bad) in message and "gates.quality.max_lines" in message


def test_bad_type_rejected_with_repo_file(tmp_path: Path) -> None:
    message, bad = _error(tmp_path, None, repo={"worker": {"timeout_minutes": "soon"}})
    assert str(bad) in message and "worker.timeout_minutes" in message


@pytest.mark.parametrize(("data", "path"), [
    ({"models": {"tiers": {"api_key": "x"}}}, "models.tiers.api_key"),
    ({"agents": {"prefer": {"GITHUB_TOKEN": "x"}}}, "agents.prefer.GITHUB_TOKEN"),
    ({"permissions": {"profiles": {"db": {"password": "x"}}}}, "permissions.profiles.db.password"),
    ({"skills": [{"clientSecret": "x"}]}, "skills[0].clientSecret"),
    ({"work": {"apiKey": "x"}}, "work.apiKey"),
])
def test_secret_looking_keys_rejected(tmp_path: Path, data: dict, path: str) -> None:
    message, bad = _error(tmp_path, data)
    assert str(bad) in message and path in message and "secret" in message.lower()


def test_is_secret_key_ignores_harmless_names() -> None:
    assert not any(map(is_secret_key, ["max_tokens", "tdd", "per_run_usd", "secretary"]))
    assert all(map(is_secret_key, ["token", "api-key", "db_password", "secrets"]))


def test_invalid_yaml_names_file_and_line(tmp_path: Path) -> None:
    message, bad = _error(tmp_path, "agents: [claude\nskills: x: y\n")
    assert str(bad) in message and "line" in message


def test_non_mapping_file_rejected(tmp_path: Path) -> None:
    message, bad = _error(tmp_path, "- claude\n- codex\n")
    assert str(bad) in message and "mapping" in message


def test_personal_cannot_declare_locked(tmp_path: Path) -> None:
    message, bad = _error(tmp_path, {"locked": ["gates"]})
    assert str(bad) in message and "locked" in message


def test_locked_entry_must_name_a_profile_key(tmp_path: Path) -> None:
    message, bad = _error(tmp_path, None, repo={"locked": ["nonsense"]})
    assert str(bad) in message and "locked" in message and "nonsense" in message
