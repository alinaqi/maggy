"""Harness emitters: profile -> native agent config (Claude Code, Codex)."""

from maggy.harness.emitters.base import Capabilities, Capability, Emitter, EmitterSources, Scope
from maggy.harness.emitters.claude import ClaudeEmitter
from maggy.harness.emitters.codex import CodexEmitter
from maggy.harness.emitters.opencode import OpenCodeEmitter
from maggy.harness.emitters.pi import PiEmitter
from maggy.harness.emitters.sources import default_sources

__all__ = [
    "Capabilities", "Capability", "ClaudeEmitter", "CodexEmitter", "Emitter",
    "EmitterSources", "OpenCodeEmitter", "PiEmitter", "Scope", "default_sources",
]
