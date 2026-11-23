"""opencode.json managed keys (verified against opencode 1.19.6).

Lists (instructions, plugin, skills.paths) keep the user's entries first and
append Maggy's. permission.bash objects keep the user's patterns; opencode
evaluates the last matching rule, so the broad "*" stays first.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from maggy.harness.emitters.awg import awg_plugin_dir, opencode_awg_server, token_file
from maggy.harness.emitters.base import EmitterSources, Scope
from maggy.harness.emitters.claude_settings import load_settings
from maggy.harness.emitters.permissions import opencode_rules
from maggy.harness.region_keys import get_path
from maggy.harness.schema import HarnessProfile

PLUGIN_SUFFIX = "plugins/opencode/plugin/awg.js"


def merged(current: object, ours: list, is_ours: Callable[[object], bool]) -> list:
    """The user's list entries (minus Maggy's) followed by Maggy's."""
    have = current if isinstance(current, list) else []
    return [x for x in have if not is_ours(x)] + ours


def _is_awg_plugin(entry: object) -> bool:
    spec = entry[0] if isinstance(entry, list) and entry else entry
    return isinstance(spec, str) and spec.endswith(PLUGIN_SUFFIX)


class OpenCodeConfig:
    """Regions for one opencode.json; `agents_ref` is how it names the managed AGENTS.md."""

    def __init__(self, path: Path, scope: Scope, sources: EmitterSources) -> None:
        self.scope, self.sources = scope, sources
        self.current = load_settings(path)

    def regions(self, profile: HarnessProfile, agents_ref: str | None) -> dict[str, object]:
        out: dict[str, object] = {}
        if agents_ref:
            have = get_path(self.current, "instructions")
            out["instructions"] = merged(have, [agents_ref], lambda x: x == agents_ref)
        out.update(self._permissions(profile))
        if profile.work.provider == "awg":
            out["mcp.awg"] = opencode_awg_server(self.scope)
            out.update(self._awg_plugin())
        return out

    def _permissions(self, profile: HarnessProfile) -> dict[str, object]:
        rules = opencode_rules(profile)
        bash, have = rules.get("bash"), get_path(self.current, "permission.bash")
        if isinstance(bash, dict) and isinstance(have, dict):
            extra = {cmd: act for cmd, act in bash.items() if cmd not in have}
            rules["bash"] = {"*": bash["*"], **have, **extra}
        return {f"permission.{tool}": value for tool, value in rules.items()}

    def _awg_plugin(self) -> dict[str, object]:
        """User scope: AWG's heartbeat plugin and skill, by path into the AWG checkout."""
        plugin_dir = awg_plugin_dir(self.sources, "opencode")
        if plugin_dir is None or self.scope.kind != "user":
            return {}
        entry = [f"file://{plugin_dir / 'plugin' / 'awg.js'}", {"tokenFile": token_file(self.scope, "opencode")}]
        skills = str(plugin_dir / "skills")
        return {"plugin": merged(get_path(self.current, "plugin"), [entry], _is_awg_plugin),
                "skills.paths": merged(get_path(self.current, "skills.paths"), [skills],
                                       lambda x: x == skills)}
