"""`maggy harness diff/apply`: plan vs disk, confirm, backup, lock, conflicts."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_cli_helpers import TESTED, FakeTools, invoke, make_env, write_profile

PROFILE = {"agents": {"installed": ["claude", "codex"]},
           "instructions": {"include": ["rules/tdd.md"]}, "skills": ["python"]}


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    made = make_env(tmp_path, FakeTools(dict(TESTED)))
    write_profile(made, PROFILE)
    return made


def test_diff_shows_unified_diff_and_writes_nothing(env) -> None:
    result = invoke(env, ["diff", "--agent", "claude"])
    assert result.exit_code == 0, result.output
    agents = env.home / ".claude" / "AGENTS.md"
    assert f"+++ {agents}" in result.output
    assert "+Write the failing test first." in result.output
    assert not agents.exists()


def test_apply_yes_writes_then_second_apply_is_noop(env) -> None:
    first = invoke(env, ["apply", "--yes"])
    assert first.exit_code == 0, first.output
    written = env.home / ".codex" / "AGENTS.md"
    assert "Write the failing test first." in written.read_text()
    assert (env.home / ".maggy" / "harness.lock").is_file()
    lock_before = (env.home / ".maggy" / "harness.lock").read_text()
    mtime = written.stat().st_mtime_ns
    second = invoke(env, ["apply", "--yes"])
    assert second.exit_code == 0, second.output
    assert "Nothing to apply" in second.output
    assert written.stat().st_mtime_ns == mtime
    assert (env.home / ".maggy" / "harness.lock").read_text() == lock_before
    assert not (env.home / ".maggy" / "backups").exists()


def test_apply_declined_writes_nothing(env) -> None:
    result = invoke(env, ["apply"], text="n\n")
    assert result.exit_code == 1
    assert not (env.home / ".claude" / "AGENTS.md").exists()


def test_apply_backs_up_existing_file(env) -> None:
    target = env.home / ".claude" / "AGENTS.md"
    target.parent.mkdir(parents=True)
    target.write_text("# mine\n")
    result = invoke(env, ["apply", "--yes", "--agent", "claude"])
    assert result.exit_code == 0, result.output
    [backup] = list((env.home / ".maggy" / "backups").glob("*/.claude/AGENTS.md"))
    assert backup.read_text() == "# mine\n"
    assert target.read_text().startswith("# mine\n")


def _conflicted(env) -> Path:
    invoke(env, ["apply", "--yes", "--agent", "claude"])
    target = env.home / ".claude" / "AGENTS.md"
    target.write_text(target.read_text().replace("Write the failing test first.", "My edit."))
    return target


def test_conflict_is_listed_and_exits_one(env) -> None:
    target = _conflicted(env)
    result = invoke(env, ["apply", "--yes", "--agent", "claude"])
    assert result.exit_code == 1
    assert f"conflict: {target}" in result.output
    assert "--take-mine" in result.output and "--take-profile" in result.output
    assert "My edit." in target.read_text()
    assert invoke(env, ["diff", "--agent", "claude"]).exit_code == 1


def test_take_profile_and_take_mine_resolve_conflicts(env) -> None:
    target = _conflicted(env)
    mine = invoke(env, ["apply", "--yes", "--agent", "claude", "--take-mine"])
    assert mine.exit_code == 0, mine.output
    assert "My edit." in target.read_text()
    again = invoke(env, ["apply", "--yes", "--agent", "claude"])
    assert again.exit_code == 0 and "My edit." in target.read_text(), again.output
    target.write_text(target.read_text().replace("My edit.", "Other edit."))
    assert invoke(env, ["apply", "--yes", "--agent", "claude"]).exit_code == 1
    theirs = invoke(env, ["apply", "--yes", "--agent", "claude", "--take-profile"])
    assert theirs.exit_code == 0, theirs.output
    assert "Write the failing test first." in target.read_text()


def test_usage_errors_exit_two(env) -> None:
    assert invoke(env, ["apply", "--yes", "--take-mine", "--take-profile"]).exit_code == 2
    assert invoke(env, ["diff", "--agent", "cursor"]).exit_code == 2
    assert invoke(env, ["diff", "--scope", "global"]).exit_code == 2


def test_project_scope_merges_the_shared_agents_md(env, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    result = invoke(env, ["apply", "--yes", "--scope", "project", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    text = (repo / "AGENTS.md").read_text()
    assert text.count("Write the failing test first.") == 1
    assert "AWG" in text
    assert (repo / "CLAUDE.md").is_file()
    assert invoke(env, ["apply", "--yes", "--scope", "project", "--repo", str(repo)]).exit_code == 0
