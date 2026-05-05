"""Tests for Polyphony Docker runtime (§8 worker)."""

import pytest
from unittest.mock import patch, MagicMock
from polyphony.runtime import (
    create_container,
    start_container,
    stop_container,
    remove_container,
    container_logs,
    wait_container,
    build_docker_args,
)
from polyphony.models import RunSpec


@pytest.fixture
def run_spec():
    return RunSpec(
        task_id="T-1",
        agent="claude-opus",
        identity="protaige",
        workspace="/tmp/ws/T-1/1",
        image="polyphony-worker:latest",
        env_overlay={"API_KEY": "API_KEY"},
        volume_mounts=["~/.claude:/home/worker/.claude:ro"],
        deadline_seconds=600,
    )


class TestBuildDockerArgs:
    def test_includes_image(self, run_spec):
        args = build_docker_args(run_spec)
        assert "polyphony-worker:latest" in args

    def test_includes_volumes(self, run_spec):
        args = build_docker_args(run_spec)
        assert "-v" in args
        # Collect all -v values
        volumes = []
        for i, a in enumerate(args):
            if a == "-v" and i + 1 < len(args):
                volumes.append(args[i + 1])
        assert any(
            "~/.claude:/home/worker/.claude:ro" in v
            for v in volumes
        )

    def test_includes_env(self, run_spec):
        args = build_docker_args(run_spec)
        assert "-e" in args

    def test_includes_workspace_mount(self, run_spec):
        args = build_docker_args(run_spec)
        arg_str = " ".join(args)
        assert "/tmp/ws/T-1/1" in arg_str

    def test_container_name(self, run_spec):
        args = build_docker_args(run_spec)
        assert "--name" in args


class TestCreateContainer:
    @patch("polyphony.runtime._run_docker")
    def test_creates_container(self, mock_docker, run_spec):
        mock_docker.return_value = MagicMock(
            returncode=0, stdout="container_id_123\n",
        )
        cid = create_container(run_spec)
        assert cid == "container_id_123"
        assert mock_docker.called

    @patch("polyphony.runtime._run_docker")
    def test_failure_raises(self, mock_docker, run_spec):
        mock_docker.return_value = MagicMock(
            returncode=1, stderr="error",
        )
        with pytest.raises(RuntimeError, match="error"):
            create_container(run_spec)


class TestStartContainer:
    @patch("polyphony.runtime._run_docker")
    def test_starts(self, mock_docker):
        mock_docker.return_value = MagicMock(returncode=0)
        start_container("abc123")
        mock_docker.assert_called_once()
        cmd = mock_docker.call_args[0][0]
        assert "start" in cmd
        assert "abc123" in cmd


class TestStopContainer:
    @patch("polyphony.runtime._run_docker")
    def test_stops(self, mock_docker):
        mock_docker.return_value = MagicMock(returncode=0)
        stop_container("abc123")
        cmd = mock_docker.call_args[0][0]
        assert "stop" in cmd

    @patch("polyphony.runtime._run_docker")
    def test_stop_with_timeout(self, mock_docker):
        mock_docker.return_value = MagicMock(returncode=0)
        stop_container("abc123", timeout=30)
        cmd = mock_docker.call_args[0][0]
        assert "-t" in cmd
        assert "30" in cmd


class TestRemoveContainer:
    @patch("polyphony.runtime._run_docker")
    def test_removes(self, mock_docker):
        mock_docker.return_value = MagicMock(returncode=0)
        remove_container("abc123")
        cmd = mock_docker.call_args[0][0]
        assert "rm" in cmd
        assert "abc123" in cmd


class TestContainerLogs:
    @patch("polyphony.runtime._run_docker")
    def test_returns_logs(self, mock_docker):
        mock_docker.return_value = MagicMock(
            returncode=0,
            stdout="line1\nline2\n",
        )
        logs = container_logs("abc123")
        assert logs == "line1\nline2\n"


class TestWaitContainer:
    @patch("polyphony.runtime._run_docker")
    def test_returns_exit_code(self, mock_docker):
        mock_docker.return_value = MagicMock(
            returncode=0, stdout="0\n",
        )
        code = wait_container("abc123")
        assert code == 0

    @patch("polyphony.runtime._run_docker")
    def test_nonzero_exit(self, mock_docker):
        mock_docker.return_value = MagicMock(
            returncode=0, stdout="1\n",
        )
        code = wait_container("abc123")
        assert code == 1
