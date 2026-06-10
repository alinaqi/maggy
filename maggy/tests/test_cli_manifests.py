"""Golden tests for pinned CLI adapter manifests (T2-A).

If any pinned command shape changes, these fail loudly — surfacing adapter
drift instead of silently mis-invoking a CLI.
"""

from __future__ import annotations

from maggy.adapters.cli_manifests import pinned_command, is_pinned
from maggy.adapters.pi import DEFAULT_MODELS, ModelEntry, PiAdapter

# GOLDEN: model name -> exact flag tail between the CLI and the prompt.
GOLDEN_TAILS: dict[str, list[str]] = {
    "local": [],
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
    "kimi": ["--quiet", "-p"],
}

# These are NOT pinned (vendor CLIs via discovered profile).
UNPINNED = {"claude", "gpt", "codex"}


def _model(name: str) -> ModelEntry | None:
    return next((m for m in DEFAULT_MODELS if m.name == name), None)


def test_every_golden_model_builds_exact_command():
    for name, tail in GOLDEN_TAILS.items():
        m = _model(name)
        if m is None:
            continue  # model not in registry on this build
        assert pinned_command(m, "PROMPT") == [m.cli_command, *tail, "PROMPT"], name


def test_unpinned_models_fall_back_to_discovery():
    for name in UNPINNED:
        m = _model(name)
        if m is None:
            continue
        assert pinned_command(m, "P") is None, name
        assert is_pinned(m) is False


def test_minimax_pinned_by_cli_path():
    m = ModelEntry("x", "minimax", "MiniMax-M2.5", "premium",
                   cli_command="/Users/me/bin/minimax")
    assert pinned_command(m, "P") == ["/Users/me/bin/minimax", "P"]


def test_kimi_pinned_by_cli_path():
    m = ModelEntry("x", "moonshot", "kimi", "standard",
                   cli_command="/Users/me/bin/kimi")
    assert pinned_command(m, "P") == ["/Users/me/bin/kimi", "--quiet", "-p", "P"]


def test_pi_build_command_prefers_pinned():
    """pi.py routes a known delegation model through the pinned manifest."""
    adapter = PiAdapter()
    m = _model("deepseek-pro")
    if m is None:
        return
    cmd = adapter._build_command(m, "hello", 5, "/tmp")
    assert cmd == [m.cli_command, "--pro", "hello"]


def test_pi_build_command_claude_unchanged():
    """Unpinned claude still works (no regression)."""
    adapter = PiAdapter()
    m = adapter.get_model("claude")
    cmd = adapter._build_command(m, "hello", 5, "/tmp")
    assert "claude" in cmd[0]
