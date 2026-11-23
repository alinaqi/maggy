"""pi emitter (verified against pi 0.73.1 docs: settings.md, skills.md, extensions.md).

user scope (root = HOME): ~/.pi/agent/AGENTS.md, skills/, extensions/maggy-hooks.ts,
and for AWG: extensions/awg/ (a marked copy of AWG's plugins/pi extension),
settings.json `skills` (AWG's skill dir) and awg.json `tokenFile`.
project scope: AGENTS.md, .pi/skills/, .pi/extensions/maggy-hooks.ts (no AWG:
a checked-in repo cannot carry the per-machine token path).
"""

from __future__ import annotations

from pathlib import Path

from maggy.harness.changes import FileChange, ManagedFile
from maggy.harness.emitters.awg import awg_plugin_dir, token_file
from maggy.harness.emitters.base import Capabilities, Capability, EmitterSources, Scope
from maggy.harness.emitters.claude_settings import load_settings
from maggy.harness.emitters.common import markdown, run_plan
from maggy.harness.emitters.copies import plan_copies
from maggy.harness.emitters.opencode_config import merged
from maggy.harness.emitters.pi_hooks import EXTENSION, MARKER, hooks_extension
from maggy.harness.emitters.sources import instructions_body
from maggy.harness.schema import HarnessProfile

CAPABILITIES = Capabilities(
    instructions=Capability(level="native", notes="AGENTS.md managed block (~/.pi/agent/AGENTS.md or repo)"),
    skills=Capability(level="native", notes=(
        "~/.pi/agent/skills/<name>/SKILL.md (project: .pi/skills); the AWG skill via settings.json "
        "skills into the AWG checkout (user scope, needs MAGGY_AWG_REPO)")),
    hooks=Capability(level="partial", notes=(
        "extensions/maggy-hooks.ts runs $HOME/.maggy/hooks/<name>: session_start=session_start, "
        "before_tool=tool_call (non-zero exit blocks), after_tool/after_edit=tool_result, "
        "before_stop=agent_end (cannot block), before_compact=session_before_compact, "
        "session_end=session_shutdown; hooks get no Claude-style JSON payload on stdin")),
    mcp=Capability(level="partial", notes=(
        "pi has no MCP client: AWG tools come from AWG's pi extension, copied into "
        "~/.pi/agent/extensions/awg/ (maggy:managed-extension marker), which runs awg mcp per call; "
        "token file set in ~/.pi/agent/awg.json; user scope only, needs MAGGY_AWG_REPO")),
    permissions=Capability(level="none", notes=(
        "pi has no permission config; the runner passes --tools/--exclude-tools")),
)


def agent_dir(scope: Scope) -> Path:
    return scope.root / (".pi/agent" if scope.kind == "user" else ".pi")


def _files_under(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else []


class PiEmitter:
    agent = "pi"

    def __init__(self, sources: EmitterSources) -> None:
        self.sources = sources

    def capabilities(self) -> Capabilities:
        return CAPABILITIES

    def plan(self, profile: HarnessProfile, scope: Scope) -> list[FileChange]:
        skills = (list(profile.skills), agent_dir(scope) / "skills")
        planned = run_plan(self.managed_files(profile, scope), skills, (self.sources, scope))
        ext = agent_dir(scope) / "extensions"
        candidates = _files_under(ext / "awg") + [p for p in [ext / "maggy-hooks.ts"] if p.is_file()]
        return planned + plan_copies(self.extensions(profile, scope), candidates, (scope.context(), EXTENSION))

    def managed_files(self, profile: HarnessProfile, scope: Scope) -> list[ManagedFile]:
        """Managed regions per file; lets a compiler merge files shared by emitters."""
        base = agent_dir(scope) if scope.kind == "user" else scope.root
        body = instructions_body(self.sources, profile)
        files = [markdown(base / "AGENTS.md", {"instructions": body})] if body else []
        plugin = self._awg_dir(profile, scope)
        if plugin is None:
            return files
        settings = agent_dir(scope) / "settings.json"
        skills = str(plugin / "skills")
        have = load_settings(settings).get("skills")
        return files + [
            ManagedFile(path=settings, format="json",
                        regions={"skills": merged(have, [skills], lambda x: x == skills)}),
            ManagedFile(path=agent_dir(scope) / "awg.json", format="json", references_token=True,
                        regions={"tokenFile": token_file(scope, "pi")})]

    def extensions(self, profile: HarnessProfile, scope: Scope) -> dict[Path, str]:
        """Whole-file extension copies: the hooks extension and AWG's pi extension."""
        ext = agent_dir(scope) / "extensions"
        hooks = hooks_extension(profile.hooks)
        wanted = {ext / "maggy-hooks.ts": hooks} if hooks else {}
        plugin = self._awg_dir(profile, scope)
        source = plugin / "extensions" / "awg" if plugin else None
        for path in _files_under(source) if source else []:
            text = path.read_text(encoding="utf-8")
            wanted[ext / "awg" / path.relative_to(source)] = f"{MARKER}\n{text}"
        return wanted

    def _awg_dir(self, profile: HarnessProfile, scope: Scope) -> Path | None:
        if profile.work.provider != "awg" or scope.kind != "user":
            return None
        return awg_plugin_dir(self.sources, "pi")
