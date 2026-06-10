"""Tests for T2-B: container isolation of the autonomous pipeline."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from maggy.pipeline.container_runner import ContainerToolRunner, docker_available
from maggy.pipeline.tool_executor import ToolExecutor, build_tool_executor
from maggy.pipeline.tool_sandbox import ToolSandbox
from maggy.pipeline.tool_schema import ToolCall


def _proc(rc=0, out="", err=""):
    return subprocess.CompletedProcess([], rc, out, err)


# ── ContainerToolRunner (mocked docker) ────────────────────────────────

def test_start_creates_container():
    runs = []

    def fake_run(cmd, timeout=120, stdin=None):
        runs.append(cmd)
        return _proc(0, "container123\n")

    r = ContainerToolRunner("/tmp/ws", run=fake_run)
    cid = r.start()
    assert cid == "container123"
    assert runs[0][:3] == ["docker", "run", "-d"]
    assert any(c.endswith(":/workspace") for c in runs[0])
    # start is idempotent
    assert r.start() == "container123" and len(runs) == 1


def test_exec_runs_in_workspace():
    calls = []

    def fake_run(cmd, timeout=120, stdin=None):
        calls.append(cmd)
        if cmd[1] == "run":
            return _proc(0, "cid\n")
        return _proc(0, "ok")

    r = ContainerToolRunner("/tmp/ws", run=fake_run)
    rc, out = r.exec(["git", "status"])
    assert rc == 0 and out == "ok"
    exec_cmd = calls[-1]
    assert exec_cmd[:2] == ["docker", "exec"]
    assert exec_cmd[-2:] == ["git", "status"]
    assert "/workspace" in exec_cmd


def test_write_file_uses_stdin():
    seen = {}

    def fake_run(cmd, timeout=120, stdin=None):
        if cmd[1] == "run":
            return _proc(0, "cid\n")
        seen["cmd"], seen["stdin"] = cmd, stdin
        return _proc(0)

    r = ContainerToolRunner("/tmp/ws", run=fake_run)
    msg = r.write_file("src/a.py", "print(1)")
    assert "wrote src/a.py" in msg
    assert seen["stdin"] == "print(1)"
    assert "-i" in seen["cmd"]  # interactive for stdin


def test_start_failure_raises():
    r = ContainerToolRunner("/tmp/ws", run=lambda *a, **k: _proc(1, "", "boom"))
    with pytest.raises(RuntimeError):
        r.start()


def test_docker_available():
    assert docker_available(run=lambda *a, **k: _proc(0)) is True
    assert docker_available(run=lambda *a, **k: _proc(1)) is False


# ── ToolExecutor routes through the runner ─────────────────────────────

@pytest.mark.asyncio
async def test_executor_routes_writes_through_container(tmp_path):
    runner = MagicMock()
    runner.write_file.return_value = "wrote x"
    ex = ToolExecutor(ToolSandbox(str(tmp_path)), str(tmp_path), runner=runner)
    res = await ex.execute_round([
        ToolCall(name="file_write", params={"path": "a.py", "content": "x"}),
    ])
    assert res[0].success
    runner.write_file.assert_called_once_with("a.py", "x")


@pytest.mark.asyncio
async def test_executor_test_run_uses_container_shell(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
    runner = MagicMock()
    runner.run_shell.return_value = (0, "3 passed")
    monkeypatch.setattr(
        "maggy.pipeline.tool_handlers._detect_test_command",
        lambda wd: "pytest -q",
    )
    ex = ToolExecutor(ToolSandbox(str(tmp_path)), str(tmp_path), runner=runner)
    res = await ex.execute_round([ToolCall(name="test_run", params={})])
    assert "3 passed" in res[0].output
    runner.run_shell.assert_called_once()


@pytest.mark.asyncio
async def test_executor_legacy_path_when_no_runner(tmp_path):
    """No runner -> in-process host handlers still work (fallback)."""
    (tmp_path / "f.txt").write_text("hello")
    ex = ToolExecutor(ToolSandbox(str(tmp_path)), str(tmp_path))  # runner=None
    res = await ex.execute_round([
        ToolCall(name="file_read", params={"path": "f.txt"}),
    ])
    assert "hello" in res[0].output


# ── factory selects isolation ──────────────────────────────────────────

def test_factory_container_when_docker(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "maggy.pipeline.container_runner.docker_available", lambda run=None: True,
    )
    monkeypatch.setattr(
        "maggy.pipeline.container_runner.ContainerToolRunner.start",
        lambda self: "cid",
    )
    ex = build_tool_executor(ToolSandbox(str(tmp_path)), str(tmp_path), isolation="auto")
    assert ex._runner is not None


def test_factory_process_isolation_has_no_runner(tmp_path):
    ex = build_tool_executor(ToolSandbox(str(tmp_path)), str(tmp_path), isolation="process")
    assert ex._runner is None


def test_factory_container_required_raises_without_docker(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "maggy.pipeline.container_runner.ContainerToolRunner.start",
        lambda self: (_ for _ in ()).throw(RuntimeError("no docker")),
    )
    with pytest.raises(RuntimeError):
        build_tool_executor(ToolSandbox(str(tmp_path)), str(tmp_path), isolation="container")


@pytest.mark.asyncio
async def test_executor_close_tears_down_runner(tmp_path):
    runner = MagicMock()
    ex = ToolExecutor(ToolSandbox(str(tmp_path)), str(tmp_path), runner=runner)
    ex.close()
    runner.close.assert_called_once()
