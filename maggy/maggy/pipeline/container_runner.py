"""Container tool runner — run pipeline tool ops inside a Docker container.

T2-B (council): the autonomous pipeline ran file/git/shell operations on the
HOST, contained only by path validation (a graveyard of bypasses; `test_run`
even shelled out directly). This runner confines those operations to a Docker
container with the workspace mounted at /workspace, so a path-validation bypass
or a malicious `test_run` command cannot escape the workspace. It becomes the
default isolation for the autonomous path; the host path-sandbox is the
explicit, deprecated fallback for hosts without Docker.

All docker calls go through `_run` (a thin, mockable wrapper).
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

WORKDIR = "/workspace"
DEFAULT_IMAGE = "polyphony-worker:latest"


def _run(cmd: list[str], timeout: int = 120, stdin: str | None = None):
    """Run a docker command. Thin wrapper for mocking."""
    return subprocess.run(
        cmd, capture_output=True, text=True, check=False,
        timeout=timeout, input=stdin,
    )


class ContainerToolRunner:
    """Runs tool operations inside a workspace-mounted Docker container."""

    def __init__(self, working_dir: str, image: str = DEFAULT_IMAGE, run=_run):
        self._wd = str(Path(working_dir).resolve())
        self._image = image
        self._run = run
        self._cid: str | None = None

    def start(self) -> str:
        """Lazily create + start the container; returns its id."""
        if self._cid:
            return self._cid
        p = self._run([
            "docker", "run", "-d", "--rm",
            "-v", f"{self._wd}:{WORKDIR}", "-w", WORKDIR,
            self._image, "sleep", "infinity",
        ])
        if p.returncode != 0:
            raise RuntimeError(f"container start failed: {(p.stderr or '')[:200]}")
        self._cid = p.stdout.strip()
        return self._cid

    def exec(self, argv: list[str], timeout: int = 120) -> tuple[int, str]:
        """docker exec a command in /workspace. Returns (rc, combined output)."""
        cid = self.start()
        p = self._run(
            ["docker", "exec", "-w", WORKDIR, cid, *argv], timeout=timeout,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def run_shell(self, cmd: str, timeout: int = 120) -> tuple[int, str]:
        """Run a shell command inside the container."""
        return self.exec(["sh", "-lc", cmd], timeout=timeout)

    def read_file(self, rel_path: str) -> str:
        rc, out = self.exec(["cat", "--", rel_path])
        return out if rc == 0 else f"error: {out[:200]}"

    def write_file(self, rel_path: str, content: str) -> str:
        """Write a file via stdin to avoid shell-escaping the content."""
        cid = self.start()
        q = shlex.quote(rel_path)
        p = self._run(
            ["docker", "exec", "-i", "-w", WORKDIR, cid, "sh", "-c", f"cat > {q}"],
            stdin=content,
        )
        if p.returncode != 0:
            return f"error: {(p.stderr or '')[:200]}"
        return f"wrote {rel_path} ({len(content)} bytes)"

    def close(self) -> None:
        """Stop + remove the container (best-effort)."""
        if not self._cid:
            return
        try:
            self._run(["docker", "rm", "-f", self._cid], timeout=30)
        except Exception:
            pass
        self._cid = None


def docker_available(run=_run) -> bool:
    """True if a Docker daemon is reachable."""
    try:
        return run(["docker", "info"], timeout=10).returncode == 0
    except Exception:
        return False
