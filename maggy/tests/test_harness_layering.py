"""Harness profile layering: defaults < repo < personal < repo-locked."""

from __future__ import annotations

from pathlib import Path

from harness_helpers import all_paths, repo_file, write_yaml

from maggy.harness import HarnessProfile, resolve_profile


def _resolve(tmp_path: Path, repo: object = None, personal: object = None):
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    if repo is not None:
        write_yaml(repo_file(root), repo)
    home_file = tmp_path / "home" / "harness.yaml"
    if personal is not None:
        write_yaml(home_file, personal)
    return resolve_profile(repo_root=root, personal_path=home_file)


def test_missing_files_fall_back_to_defaults(tmp_path: Path) -> None:
    resolved = _resolve(tmp_path)
    assert resolved.profile == HarnessProfile()
    assert set(resolved.provenance.values()) == {"default"}
    assert resolved.provenance["gates.quality.max_function_lines"] == "default"


def test_empty_files_are_defaults(tmp_path: Path) -> None:
    resolved = _resolve(tmp_path, repo="", personal="\n# nothing\n")
    assert resolved.profile == HarnessProfile()
    assert set(resolved.provenance.values()) == {"default"}


def test_personal_beats_repo_unlocked(tmp_path: Path) -> None:
    repo = {"gates": {"coverage_min": 0.9}, "worker": {"timeout_minutes": 45}}
    personal = {"gates": {"coverage_min": 0.7}}
    resolved = _resolve(tmp_path, repo, personal)
    assert resolved.profile.gates.coverage_min == 0.7
    assert resolved.profile.worker.timeout_minutes == 45
    assert resolved.provenance["gates.coverage_min"] == "personal"
    assert resolved.provenance["worker.timeout_minutes"] == "repo"


def test_repo_locked_beats_personal(tmp_path: Path) -> None:
    repo = {"validation": {"required": ["lint", "test"]}, "locked": ["validation"]}
    personal = {"validation": {"required": ["test"], "visual_for": ["ui"]}}
    resolved = _resolve(tmp_path, repo, personal)
    assert resolved.profile.validation.required == ["lint", "test"]
    assert resolved.profile.validation.visual_for == []
    assert resolved.provenance["validation"] == "repo-locked"
    assert resolved.provenance["validation.required"] == "repo-locked"
    assert resolved.provenance["validation.visual_for"] == "default"


def test_locked_subtree_drops_personal_siblings(tmp_path: Path) -> None:
    high = {"paths": ["src/auth/**"], "require": "plan_approval"}
    repo = {"risk": {"high": high}, "locked": ["risk"]}
    personal = {"risk": {"low": {"paths": ["**"], "autonomy": "merge"}}}
    resolved = _resolve(tmp_path, repo, personal)
    assert resolved.profile.risk.low is None
    assert resolved.profile.risk.high.paths == ["src/auth/**"]
    assert resolved.provenance["risk.high.require"] == "repo-locked"
    assert resolved.provenance["risk.low"] == "default"


def test_dotted_lock_only_locks_that_key(tmp_path: Path) -> None:
    repo = {"gates": {"coverage_min": 0.9}, "locked": ["gates.coverage_min"]}
    personal = {"gates": {"coverage_min": 0.1, "tdd": "preferred"}}
    resolved = _resolve(tmp_path, repo, personal)
    assert resolved.profile.gates.coverage_min == 0.9
    assert resolved.profile.gates.tdd == "preferred"
    assert resolved.provenance["gates.coverage_min"] == "repo-locked"
    assert resolved.provenance["gates.tdd"] == "personal"
    assert resolved.provenance["gates"] == "repo-locked"


def test_dicts_deep_merge_and_lists_replace(tmp_path: Path) -> None:
    repo = {"agents": {"installed": ["claude", "codex"], "prefer": {"bulk": "opencode"}}}
    personal = {"agents": {"installed": ["pi"], "prefer": {"review": "codex"}}}
    resolved = _resolve(tmp_path, repo, personal)
    assert resolved.profile.agents.installed == ["pi"]
    assert resolved.profile.agents.prefer == {"bulk": "opencode", "review": "codex"}


def test_provenance_covers_every_key(tmp_path: Path) -> None:
    repo = {"agents": {"prefer": {"bulk": "opencode"}}, "commands": {"test": "pytest"},
            "budget": {"per_day_usd": 10}, "locked": ["budget"]}
    personal = {"agents": {"prefer": {"review": "codex"}}, "budget": {"per_run_usd": 99}}
    resolved = _resolve(tmp_path, repo, personal)
    assert set(resolved.provenance) == all_paths(resolved.profile.model_dump())
    expected = {"agents": "personal", "agents.prefer": "personal",
                "agents.prefer.bulk": "repo", "agents.prefer.review": "personal",
                "agents.default": "default", "commands.test": "repo",
                "commands": "repo", "budget.per_day_usd": "repo-locked",
                "budget.per_run_usd": "default", "locked": "repo",
                "version": "default"}
    assert {k: resolved.provenance[k] for k in expected} == expected
    assert resolved.profile.budget.per_run_usd is None


def test_personal_path_defaults_to_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    write_yaml(tmp_path / ".maggy" / "harness.yaml", {"skills": ["python"]})
    resolved = resolve_profile(repo_root=tmp_path / "missing-repo")
    assert resolved.profile.skills == ["python"]
    assert resolved.provenance["skills"] == "personal"
