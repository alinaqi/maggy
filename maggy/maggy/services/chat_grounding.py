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
        "## Your Capabilities\n"
        "You have full shell access. Use it proactively:\n"
        "- `grep -rn`, `find`, `cat` to search and read code\n"
        "- `git log`, `git diff`, `git blame` for history\n"
        "- `python`, `node`, `npm`, `pip`, `pytest` to run and test\n"
        "- Any CLI tool installed on this machine\n"
        "\n"
        "## When the Question Is About Code\n"
        "- Read the relevant source files before answering.\n"
        "- Verify claims by reading actual code — never guess at file paths,\n"
        "  function names, or features without checking.\n"
        "- Cite file paths and line numbers when referencing code.\n"
        "- If you cannot find something, say so clearly.\n"
        "\n"
        "## When the Question Is Not About Code\n"
        "- Answer directly. Not every question requires reading files.\n"
        "- For research, planning, brainstorming, or general questions,\n"
        "  engage conversationally — share your knowledge and reasoning.\n"
        "- For architecture decisions or new project setup, discuss\n"
        "  tradeoffs and help the user think through options.\n"
        "\n"
        "## General\n"
        "- Be concise. Short answers for short questions.\n"
        "- Match the user's level — explain less to experts, more to beginners.\n"
        "- When you take an action (edit, run, install), explain what you did\n"
        "  and what happened.\n"
        "- Prefer editing existing files over creating new ones.\n"
        "- Write tests before implementation when building features."
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
            f"You are an AI engineering assistant in Maggy, working on "
            f"**{project_key}**.\n"
            f"Working directory: `{working_dir}`\n"
            f"You help with coding, debugging, research, planning, "
            f"architecture, and any engineering task."
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
