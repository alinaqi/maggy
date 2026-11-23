"""AWG wiring: MCP server entries that reference per-agent token files.

Token files live at <home>/.maggy/tokens/<agent>.token and are minted by
`harness apply` (task 1.5), never by plan(); emitted config only names the
file. OpenCode and pi plugins are referenced from an AWG checkout
(EmitterSources.awg_repo: plugins/opencode, plugins/pi). The Codex AGENTS.md section is vendored from the AWG repo
(plugins/codex/AGENTS.md) in assets/awg_codex_agents.md.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from maggy.harness.emitters.base import EmitterSources, Scope
from maggy.harness.schema import HarnessProfile

AWG_PLUGINS = {"claude": "claude-code", "codex": "codex"}


def token_file(scope: Scope, agent: str) -> str:
    return str(scope.home / ".maggy" / "tokens" / f"{agent}.token")


def claude_awg_server(scope: Scope) -> dict:
    """Project .mcp.json is checked in, so it uses Claude's ${HOME} expansion."""
    path = "${HOME}/.maggy/tokens/claude.token" if scope.kind == "project" else token_file(scope, "claude")
    return {"type": "stdio", "command": "awg", "args": ["mcp", "--token-file", path]}


def codex_awg_server(scope: Scope) -> dict:
    return {"command": "awg", "args": ["mcp", "--token-file", token_file(scope, "codex")]}


def opencode_awg_server(scope: Scope) -> dict:
    """Project opencode.json is checked in, so it uses OpenCode's {env:HOME} expansion."""
    path = "{env:HOME}/.maggy/tokens/opencode.token" if scope.kind == "project" else token_file(scope, "opencode")
    return {"type": "local", "command": ["awg", "mcp", "--token-file", path], "enabled": True}


def awg_plugin_dir(sources: EmitterSources, agent: str) -> Path | None:
    """<awg_repo>/plugins/<agent> when an AWG checkout is configured and has it."""
    if sources.awg_repo is None:
        return None
    found = sources.awg_repo / "plugins" / agent
    return found if found.is_dir() else None


def codex_awg_section() -> str:
    asset = files("maggy.harness.emitters") / "assets" / "awg_codex_agents.md"
    return asset.read_text(encoding="utf-8").strip()


def awg_skill(sources: EmitterSources, agent: str, wiring: tuple[HarnessProfile, Scope]) -> dict[str, str]:
    """{'awg': SKILL.md} from <awg_repo>/plugins/<claude-code|codex>/skills/awg (user scope only,
    like OpenCode's skills.paths and pi's settings skills); {} when not wired."""
    profile, scope = wiring
    if profile.work.provider != "awg" or scope.kind != "user":
        return {}
    plugin = awg_plugin_dir(sources, AWG_PLUGINS[agent])
    skill = plugin / "skills" / "awg" / "SKILL.md" if plugin else None
    return {"awg": skill.read_text(encoding="utf-8")} if skill and skill.is_file() else {}
