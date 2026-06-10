"""Chat grounding — enriches LLM system prompt with project context.

Solves the core problem: Maggy's chat hallucinated about code instead
of reading it, because the system prompt lacked grounding instructions,
project structure, and CLAUDE.md content.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__",
    ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "dist", "build", ".next", ".nuxt",
    "coverage", ".coverage", "egg-info", ".eggs",
}

_MAX_TREE_ENTRIES = 60


def grounding_instructions() -> str:
    return (
        "## Agent Behavior\n"
        "You are an autonomous agent. Execute tasks directly:\n"
        "- Read files, edit code, run commands, run tests.\n"
        "- Never tell the user what to do — do it yourself.\n"
        "- After making changes, verify them (run tests, check output).\n"
        "- Report what you did and what changed, not what to do.\n"
        "\n"
        "## Capabilities\n"
        "You have full shell access:\n"
        "- `grep -rn`, `find`, `cat` to search and read code\n"
        "- `git log`, `git diff`, `git blame` for history\n"
        "- `python`, `node`, `npm`, `pip`, `pytest` to run and test\n"
        "- Any CLI tool installed on this machine\n"
        "\n"
        "## Rules\n"
        "- Read source files before making changes.\n"
        "- Cite file paths and line numbers.\n"
        "- Be concise. Write tests before implementation.\n"
        "- Prefer editing existing files over creating new ones."
    )


def load_claude_md(
    working_dir: str, max_chars: int = 4000,
) -> str:
    candidates = ["CLAUDE.md", ".claude/CLAUDE.md"]
    for name in candidates:
        path = Path(working_dir) / name
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                if len(content) > max_chars:
                    content = content[:max_chars] + "\n...(truncated)"
                return content
            except OSError:
                continue
    return ""


def build_file_tree(
    working_dir: str, max_depth: int = 2,
) -> str:
    root = Path(working_dir)
    if not root.is_dir():
        return ""
    lines: list[str] = []
    _walk(root, root, 0, max_depth, lines)
    if not lines:
        return ""
    return "```\n" + "\n".join(lines[:_MAX_TREE_ENTRIES]) + "\n```"


def _walk(
    base: Path, current: Path,
    depth: int, max_depth: int,
    lines: list[str],
) -> None:
    if depth > max_depth or len(lines) >= _MAX_TREE_ENTRIES:
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
            _walk(base, entry, depth + 1, max_depth, lines)
        else:
            lines.append(f"{indent}{entry.name}")


def build_enriched_prompt(
    working_dir: str, project_key: str,
) -> str:
    parts = [
        (
            f"You are Maggy, an autonomous AI engineering agent working on "
            f"**{project_key}**.\n"
            f"Working directory: `{working_dir}`\n"
            f"Execute tasks directly — edit files, run commands, run tests. "
            f"Never tell the user what to do; do it yourself."
        ),
        grounding_instructions(),
    ]
    claude_md = load_claude_md(working_dir)
    if claude_md:
        parts.append(f"## Project Instructions (CLAUDE.md)\n{claude_md}")
    tree = build_file_tree(working_dir)
    if tree:
        parts.append(f"## Project Structure\n{tree}")
    return "\n\n".join(parts)
