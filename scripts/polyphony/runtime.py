"""Docker container runtime (§8 worker).

Create, start, stop, remove containers via subprocess calls.
All Docker commands go through _run_docker for easy mocking.
"""

from __future__ import annotations

import re
import subprocess

from .models import RunSpec


def build_docker_args(run_spec: RunSpec) -> list[str]:
    """Build docker create argument list from RunSpec."""
    safe_name = re.sub(r"[^\w\-]", "-", run_spec.task_id)
    name = f"polyphony-{safe_name}-{run_spec.attempt}"

    args = ["docker", "create", "--name", name]

    # Workspace mount
    args += ["-v", f"{run_spec.workspace}:/workspace"]

    # Identity volume mounts
    for mount in run_spec.volume_mounts:
        args += ["-v", mount]

    # Environment variables
    for key, val in run_spec.env_overlay.items():
        args += ["-e", f"{key}={val}"]

    args.append(run_spec.image)
    return args


def create_container(run_spec: RunSpec) -> str:
    """Create a Docker container. Returns container ID."""
    args = build_docker_args(run_spec)
    result = _run_docker(args)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def start_container(container_id: str) -> None:
    """Start a created container."""
    _run_docker(["docker", "start", container_id])


def stop_container(
    container_id: str,
    timeout: int | None = None,
) -> None:
    """Stop a running container."""
    cmd = ["docker", "stop"]
    if timeout is not None:
        cmd += ["-t", str(timeout)]
    cmd.append(container_id)
    _run_docker(cmd)


def remove_container(container_id: str) -> None:
    """Remove a container."""
    _run_docker(["docker", "rm", container_id])


def container_logs(container_id: str) -> str:
    """Get container stdout/stderr logs."""
    result = _run_docker(["docker", "logs", container_id])
    return result.stdout


def wait_container(container_id: str) -> int:
    """Wait for container to exit. Returns exit code."""
    result = _run_docker(
        ["docker", "wait", container_id],
    )
    return int(result.stdout.strip())


def _run_docker(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a docker command. Thin wrapper for mocking."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
