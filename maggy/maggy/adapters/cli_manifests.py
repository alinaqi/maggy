"""Pinned CLI adapter manifests.

The `--help` auto-discovery (cli_discovery.py) parses unstable vendor help text
to construct subprocess commands. For KNOWN CLIs that is an unnecessary risk: a
flag rename or help-format change silently mis-builds the command. These pinned
manifests are the source of truth for how each known delegation CLI is invoked.
pi.py prefers them over the discovered profile; golden tests fail loudly if a
manifest changes, surfacing drift instead of hiding it.

Each manifest is `(matcher, argv_builder)`. The matcher inspects a ModelEntry;
the builder returns the exact argv given (cli_command, prompt). Returns None for
unknown CLIs, which fall back to discovery.
"""

from __future__ import annotations

# Declarative per-model command shapes. Order matters: first match wins.
# Each entry: model-name match (exact) OR cli-substring match -> argv tail.
_BY_NAME: dict[str, list[str]] = {
    "local": [],                       # qwen3 wrapper: positional prompt
    "deepseek-flash": ["--flash"],
    "deepseek-pro": ["--pro"],
    "gemini-flash-lite": ["--flash-lite"],
    "gemini-flash": ["--flash"],
    "gemini-pro-search": ["--pro-search"],
    "gemini-cli": ["--pro"],
    "agy": ["--print"],
    "grok": [],
    "minimax": [],
    "claude-fable-5": [],
}

# cli_command substring -> argv tail (for entries keyed by wrapper, not name).
_BY_CLI: list[tuple[str, list[str]]] = [
    ("/kimi", ["--quiet", "-p"]),
    ("/minimax", []),
    ("/claude-fable-5", []),
    ("/qwen3", []),
    ("/grok", []),
    ("/agy-delegate", ["--print"]),
]


def pinned_command(
    model, prompt: str, wd: str = "", max_turns: int = 0,
) -> list[str] | None:
    """Return the pinned argv for a known CLI, or None to fall back to discovery."""
    cli = model.cli_command
    name = getattr(model, "name", "")
    if name in _BY_NAME:
        return [cli, *_BY_NAME[name], prompt]
    for substr, tail in _BY_CLI:
        if substr in cli:
            return [cli, *tail, prompt]
    return None


def is_pinned(model) -> bool:
    """True if this model has a pinned manifest (no --help discovery needed)."""
    return pinned_command(model, "") is not None


# Exposed for golden tests — every pinned model's expected command shape.
def golden_examples() -> list[tuple[str, list[str]]]:
    """(label, argv) for a representative prompt, for drift-detection tests."""
    from maggy.adapters.pi import DEFAULT_MODELS
    out: list[tuple[str, list[str]]] = []
    for m in DEFAULT_MODELS:
        cmd = pinned_command(m, "PROMPT")
        if cmd is not None:
            out.append((m.name, cmd))
    return out
