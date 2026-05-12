"""LLM-based dynamic convention inference from project fingerprint.

Collects filesystem signals (file tree, config snippets, git log)
and sends them to a cheap/local model to infer project-specific
conventions that the static rule table doesn't cover.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maggy.adapters.pi import PiAdapter
    from maggy.routing_rules import Convention, RoutingRules

logger = logging.getLogger(__name__)

MAX_CONVENTIONS = 10
MAX_FINGERPRINT = 4000
FALLBACK_MODELS = ["local", "kimi"]

SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv",
    "venv", "dist", "build", ".next", ".cache",
    ".tox", ".mypy_cache", ".ruff_cache", "egg-info",
})

CONFIG_FILES = [
    "pyproject.toml", "package.json", "Makefile",
    "docker-compose.yml", "Dockerfile", "tsconfig.json",
    ".env.example", "Cargo.toml", "go.mod", "Gemfile",
    "mix.exs", "build.gradle", "pom.xml",
]

PROMPT_TEMPLATE = (
    "Analyze this project and list its development conventions.\n"
    "Each convention must be one line starting with '- '.\n"
    "Focus on: build tools, test runners, deployment, migrations,\n"
    "package managers, CI/CD, linting, coding patterns.\n"
    "Be specific — mention exact commands and tool names.\n"
    "Max 10 conventions. No explanations, just the list.\n\n"
    "{fingerprint}"
)


def collect_fingerprint(working_dir: str) -> str:
    """Build compact project fingerprint for LLM analysis."""
    root = Path(working_dir)
    parts = [_file_tree(root), _config_snippets(root), _git_log(root)]
    return "\n".join(p for p in parts if p)[:MAX_FINGERPRINT]


def parse_conventions(text: str) -> list[Convention]:
    """Extract '- convention' lines from LLM response."""
    from maggy.routing_rules import Convention as Conv

    convs: list[Conv] = []
    for line in text.splitlines():
        m = re.match(r"^-\s+(.{5,200})$", line.strip())
        if m:
            convs.append(Conv(m.group(1).strip(), ["all"], "llm-inferred"))
        if len(convs) >= MAX_CONVENTIONS:
            break
    return convs


async def infer_conventions(
    pi: PiAdapter, working_dir: str,
) -> list[Convention]:
    """Send fingerprint to LLM, parse conventions from response."""
    fp = collect_fingerprint(working_dir)
    if len(fp.strip()) < 20:
        return []
    prompt = PROMPT_TEMPLATE.format(fingerprint=fp)
    for model in FALLBACK_MODELS:
        result = await pi.send_prompt(model, prompt, working_dir, max_turns=1, timeout=60)
        if result.success and result.output.strip():
            return parse_conventions(result.output)
        logger.debug("Inference failed on %s: %s", model, result.error)
    return []


async def ensure_inferred(
    rules: RoutingRules, project_key: str,
    working_dir: str, pi: PiAdapter,
) -> None:
    """Run LLM inference if not already cached for this project."""
    if not project_key:
        return
    existing = rules.project_conventions.get(project_key, [])
    if any(c.source == "llm-inferred" for c in existing):
        return
    try:
        convs = await infer_conventions(pi, working_dir)
    except Exception as exc:
        logger.warning("Convention inference failed: %s", exc)
        return
    if not convs:
        return
    existing_texts = {c.text for c in existing}
    new = [c for c in convs if c.text not in existing_texts]
    rules.project_conventions.setdefault(project_key, []).extend(new)


def _file_tree(root: Path) -> str:
    """List files/dirs to depth 2, excluding noise."""
    lines = ["## Project Files"]
    try:
        for p in sorted(root.iterdir()):
            if p.name in SKIP_DIRS or p.name.startswith("."):
                continue
            lines.append(p.name + ("/" if p.is_dir() else ""))
            if p.is_dir():
                for child in sorted(p.iterdir()):
                    if child.name in SKIP_DIRS:
                        continue
                    lines.append(f"  {child.name}")
    except OSError:
        pass
    return "\n".join(lines[:80])


def _config_snippets(root: Path) -> str:
    """Read first 300 chars of known config files."""
    parts: list[str] = []
    for name in CONFIG_FILES:
        path = root / name
        if path.is_file():
            try:
                text = path.read_text(errors="ignore")[:300]
                parts.append(f"## {name}\n{text}")
            except OSError:
                continue
    return "\n".join(parts)


def _git_log(root: Path) -> str:
    """Recent commit messages via git log --oneline -10."""
    if not (root / ".git").is_dir():
        return ""
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", "-10"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return f"## Recent Commits\n{r.stdout.strip()}"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""
