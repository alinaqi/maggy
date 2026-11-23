"""`maggy harness show` and the registration on the main `maggy` app."""

from __future__ import annotations

from pathlib import Path

from harness_cli_helpers import TESTED, FakeTools, invoke, make_env, write_profile
from typer.testing import CliRunner

from maggy.cli import app as maggy_app


def _row(output: str, key: str) -> list[str]:
    [line] = [ln for ln in output.splitlines() if ln.split() and ln.split()[0] == key]
    return line.split()


def test_show_prints_values_with_provenance(tmp_path: Path) -> None:
    env = make_env(tmp_path, FakeTools(dict(TESTED)))
    write_profile(env, {"skills": ["python"], "gates": {"tdd": "preferred"}})
    repo = tmp_path / "repo"
    (repo / ".maggy").mkdir(parents=True)
    (repo / ".maggy" / "harness.yaml").write_text("commands:\n  test: pytest -q\n")
    result = invoke(env, ["show", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    assert _row(result.output, "gates.tdd") == ["gates.tdd", "preferred", "personal"]
    assert _row(result.output, "commands.test") == ["commands.test", "pytest", "-q", "repo"]
    assert _row(result.output, "work.provider") == ["work.provider", "awg", "default"]
    assert _row(result.output, "skills")[-1] == "personal"


def test_show_invalid_profile_exits_one(tmp_path: Path) -> None:
    env = make_env(tmp_path, FakeTools(dict(TESTED)))
    write_profile(env, {"gates": {"tdd": "sometimes"}})
    result = invoke(env, ["show"])
    assert result.exit_code == 1
    assert "gates.tdd" in result.output


def test_harness_is_registered_on_the_maggy_app() -> None:
    result = CliRunner().invoke(maggy_app, ["harness", "--help"])
    assert result.exit_code == 0, result.output
    for name in ("init", "show", "doctor", "diff", "apply"):
        assert name in result.output
