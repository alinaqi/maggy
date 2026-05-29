"""Tool handlers — concrete implementations of allowlisted tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

_MAX_READ = 50_000
_MAX_WRITE = 100_000
_MAX_GREP_LINES = 50


async def file_read(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except OSError as e:
        return f"Error reading {path}: {e}"
    if len(content) > _MAX_READ:
        return content[:_MAX_READ] + "\n...(truncated)"
    return content


async def grep(pattern: str, path: Path) -> str:
    proc = await asyncio.create_subprocess_exec(
        "grep", "-rn", "--include=*.py", "--include=*.ts",
        "--include=*.js", "--include=*.json", "--include=*.yaml",
        "--include=*.yml", "--include=*.md", "--include=*.txt",
        pattern, str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    lines = stdout.decode(errors="replace").splitlines()
    return "\n".join(lines[:_MAX_GREP_LINES])


async def git_status(working_dir: Path) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git", "status", "--short",
        cwd=str(working_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return f"Error: {stderr.decode(errors='replace')}"
    return stdout.decode(errors="replace")


async def git_diff(
    working_dir: Path, ref: str = "HEAD",
) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git", "diff", ref,
        cwd=str(working_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode(errors="replace")[:_MAX_READ]


async def git_log(
    working_dir: Path, n: int = 10,
) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git", "log", f"-{n}", "--oneline",
        cwd=str(working_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode(errors="replace")


async def file_write(path: Path, content: str) -> str:
    if len(content) > _MAX_WRITE:
        return "Error: content too large (max 100KB)"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"Error writing {path}: {e}"
    return f"Wrote {len(content)} bytes to {path.name}"


async def file_edit(
    path: Path, old: str, new: str,
) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    if old not in content:
        return f"Error: old text not found in {path.name}"
    updated = content.replace(old, new, 1)
    path.write_text(updated, encoding="utf-8")
    return f"Edited {path.name}"


async def test_run(
    working_dir: Path, timeout_s: int = 120,
) -> str:
    cmd = _detect_test_command(working_dir)
    if not cmd:
        return "Error: no test command detected"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_s,
        )
        return stdout.decode(errors="replace")[-5000:]
    except asyncio.TimeoutError:
        proc.kill()
        return f"Error: test run timed out after {timeout_s}s"


async def git_commit(
    working_dir: Path,
    message: str,
    files: list[str] | None = None,
) -> str:
    if files:
        proc = await asyncio.create_subprocess_exec(
            "git", "add", *files,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    proc = await asyncio.create_subprocess_exec(
        "git", "commit", "-m", message,
        cwd=str(working_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return f"Error: {stderr.decode(errors='replace')}"
    return stdout.decode(errors="replace")


def _detect_test_command(working_dir: Path) -> str:
    if (working_dir / "pyproject.toml").exists():
        return "python3 -m pytest -x -q"
    if (working_dir / "package.json").exists():
        return "npm test"
    return ""
