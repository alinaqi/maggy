"""Harness emitters: profile -> native agent config (Claude Code, Codex)."""

from maggy.harness.emitters.base import Capabilities, Capability, Emitter, EmitterSources, Scope
from maggy.harness.emitters.claude import ClaudeEmitter
from maggy.harness.emitters.codex import CodexEmitter
from maggy.harness.emitters.sources import default_sources

__all__ = [
    "Capabilities", "Capability", "ClaudeEmitter", "CodexEmitter", "Emitter",
    "EmitterSources", "Scope", "default_sources",
]
