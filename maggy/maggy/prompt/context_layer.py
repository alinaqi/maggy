"""Context layer — project-specific prompt sections with invalidation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from maggy.prompt.modes import DetectedMode
from maggy.prompt.sections import PromptSection

_SKIP_DIRS = {
    ".git", ".svn", "node_modules", "__pycache__",
    ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".next", "coverage", ".eggs",
}

_STACK_MAP = {
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "requirements.txt": "Python",
    "package.json": "Node.js / JavaScript",
    "tsconfig.json": "TypeScript",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "Gemfile": "Ruby",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java (Gradle)",
}


def file_tree_section(
    working_dir: str, max_lines: int = 300,
) -> PromptSection:
    lines: list[str] = []
    root = Path(working_dir)
    if root.is_dir():
        _walk(root, 0, 2, lines, max_lines)
    content = ""
    if lines:
        content = "## File Structure\n```\n" + "\n".join(lines) + "\n```"
    return PromptSection(id="file_tree", layer="context", content=content, priority=12)


def _walk(
    current: Path, depth: int,
    max_depth: int, lines: list[str],
    max_lines: int,
) -> None:
    if depth > max_depth or len(lines) >= max_lines:
        return
    try:
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return
    for entry in entries:
        if entry.name.startswith(".") and entry.is_dir():
            continue
        if entry.name in _SKIP_DIRS:
            continue
        indent = "  " * depth
        if entry.is_dir():
            lines.append(f"{indent}{entry.name}/")
            _walk(entry, depth + 1, max_depth, lines, max_lines)
        else:
            lines.append(f"{indent}{entry.name}")


def git_state_section(working_dir: str) -> PromptSection:
    if not (Path(working_dir) / ".git").is_dir():
        return PromptSection(id="git_state", layer="context", content="")
    parts: list[str] = []
    branch = _git_cmd(working_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch:
        parts.append(f"Branch: `{branch}`")
    log = _git_cmd(working_dir, ["log", "--oneline", "-10"])
    if log:
        parts.append(f"Recent commits:\n```\n{log}\n```")
    content = ""
    if parts:
        content = "## Git State\n" + "\n".join(parts)
    return PromptSection(id="git_state", layer="context", content=content, priority=11)


def _git_cmd(cwd: str, args: list[str]) -> str:
    try:
        r = subprocess.run(
            ["git"] + args, cwd=cwd,
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def tech_stack_section(working_dir: str) -> PromptSection:
    root = Path(working_dir)
    stacks: list[str] = []
    for filename, tech in _STACK_MAP.items():
        if (root / filename).exists() and tech not in stacks:
            stacks.append(tech)
    content = ""
    if stacks:
        content = "Tech stack: " + ", ".join(stacks)
    return PromptSection(id="tech_stack", layer="context", content=content, priority=13)


def claude_md_section(
    working_dir: str, max_chars: int = 4000,
) -> PromptSection:
    for name in ("CLAUDE.md", ".claude/CLAUDE.md"):
        path = Path(working_dir) / name
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
                if len(text) > max_chars:
                    text = text[:max_chars] + "\n...(truncated)"
                content = f"## Project Instructions\n{text}"
                return PromptSection(
                    id="claude_md", layer="context",
                    content=content, priority=10,
                )
            except OSError:
                continue
    return PromptSection(id="claude_md", layer="context", content="")


def mode_section(detected: DetectedMode) -> PromptSection:
    markers = ", ".join(detected.markers) if detected.markers else "none"
    content = (
        f"Current mode: **{detected.mode.value}** "
        f"(confidence: {detected.confidence}, markers: {markers})"
    )
    return PromptSection(id="current_mode", layer="context", content=content, priority=9)
