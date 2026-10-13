"""Behavioural tests for hooks/route-task-hook (runs the real bash script).

Classifiers are disabled by pointing Ollama at a dead port and giving the hook
an empty ~/bin, so the tier comes from the seeded routing cache. That mirrors
the production failure: a cached tier whose delegation binary is not installed.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HOOK = Path(__file__).parent.parent / "hooks" / "route-task-hook"


def _run(home: Path, tier: str | None, prompt: str = "fix the bug") -> str:
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    if tier:
        cache = {"ts": "2026-10-13T00:00:00Z", "tier": tier, "classifier": "cache"}
        (home / ".claude" / "routing-cache.json").write_text(json.dumps(cache))
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/opt/homebrew/bin",
        "OLLAMA_BASE": "http://127.0.0.1:9",
        "DEEPSEEK_API_KEY": "",
    }
    proc = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps({"prompt": prompt, "cwd": str(home)}),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]


def _install(home: Path, name: str) -> None:
    bin_dir = home / "bin"
    bin_dir.mkdir(exist_ok=True)
    tool = bin_dir / name
    tool.write_text("#!/bin/bash\necho ok\n")
    tool.chmod(0o755)


def test_qwen_tier_is_gone_from_the_hook() -> None:
    text = HOOK.read_text()
    assert "~/bin/qwen3" not in text
    assert "QWEN" not in text


def test_missing_delegate_binary_falls_back_to_claude(tmp_path: Path) -> None:
    ctx = _run(tmp_path, "DEEPSEEK_FLASH")
    assert ctx.startswith("ROUTING DECISION: CLAUDE")
    assert "fallback" in ctx.lower()
    assert "bin/groq" in ctx  # upstream default flash provider
    assert "delegate this task" not in ctx.lower()
    assert "PLAN FIRST" not in ctx
    assert "CONTRACT" not in ctx


def test_installed_delegate_binary_is_used(tmp_path: Path) -> None:
    _install(tmp_path, "groq")
    ctx = _run(tmp_path, "DEEPSEEK_FLASH")
    assert ctx.startswith("ROUTING DECISION: FLASH_TIER")
    assert "bin/groq" in ctx


def test_stale_unknown_cached_tier_falls_back(tmp_path: Path) -> None:
    ctx = _run(tmp_path, "QWEN")
    assert ctx.startswith("ROUTING DECISION: CLAUDE")
    assert "bin/qwen3" not in ctx
    assert "delegate this task" not in ctx.lower()


def test_no_cache_and_no_classifier_is_claude(tmp_path: Path) -> None:
    ctx = _run(tmp_path, None)
    assert ctx.startswith("ROUTING DECISION: CLAUDE")


def test_codex_tier_needs_codex_on_path(tmp_path: Path) -> None:
    ctx = _run(tmp_path, "CODEX")
    assert ctx.startswith("ROUTING DECISION: CLAUDE")
    assert "codex" in ctx


def test_cache_keeps_classified_tier_not_fallback(tmp_path: Path) -> None:
    _run(tmp_path, "KIMI")
    cache = json.loads((tmp_path / ".claude" / "routing-cache.json").read_text())
    assert cache["tier"] == "KIMI"
    assert os.path.exists(tmp_path / ".claude" / "routing-log.jsonl")
