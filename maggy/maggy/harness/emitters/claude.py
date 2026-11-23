"""Claude Code emitter.

user scope (root = HOME): ~/.claude/AGENTS.md + ~/.claude/CLAUDE.md (@AGENTS.md
resolves relative to the importing file), ~/.claude/settings.json,
~/.claude.json (user MCP servers), ~/.claude/skills/.
project scope: AGENTS.md + CLAUDE.md, .claude/settings.json, .mcp.json,
.claude/skills/.
"""

from __future__ import annotations

from maggy.harness.changes import FileChange, ManagedFile
from maggy.harness.emitters.awg import claude_awg_server
from maggy.harness.emitters.base import Capabilities, Capability, EmitterSources, Scope
from maggy.harness.emitters.claude_settings import settings_regions
from maggy.harness.emitters.common import markdown, run_plan
from maggy.harness.emitters.sources import instructions_body
from maggy.harness.schema import HarnessProfile

CAPABILITIES = Capabilities(
    instructions=Capability(level="native", notes=(
        "AGENTS.md managed block, imported by a CLAUDE.md block '@AGENTS.md' "
        "(user: ~/.claude/, project: repo root)")),
    skills=Capability(level="native", notes=(
        "~/.claude/skills/<name>/SKILL.md (project: .claude/skills); copies carry a "
        "maggy:managed-skill marker; only SKILL.md is copied")),
    hooks=Capability(level="native", notes=(
        "settings.json hooks: session_start=SessionStart, before_tool=PreToolUse, after_tool and "
        "after_edit=PostToolUse, before_stop=Stop, before_compact=PreCompact, session_end=SessionEnd; "
        "commands run $HOME/.maggy/hooks/<name>; user hook entries are kept")),
    mcp=Capability(level="native", notes=(
        "AWG as mcpServers.awg (awg mcp --token-file ~/.maggy/tokens/claude.token) in ~/.claude.json "
        "or .mcp.json; the AWG Claude mod is not enabled: it acts with the stored owner login")),
    permissions=Capability(level="partial", notes=(
        "worker.permission profile -> settings.json permissions.allow/deny, merged with user rules "
        "and never removed; network=registries has no Claude rule")),
)


class ClaudeEmitter:
    agent = "claude"

    def __init__(self, sources: EmitterSources) -> None:
        self.sources = sources

    def capabilities(self) -> Capabilities:
        return CAPABILITIES

    def plan(self, profile: HarnessProfile, scope: Scope) -> list[FileChange]:
        claude_dir = scope.root / ".claude"
        skills = (list(profile.skills), claude_dir / "skills")
        return run_plan(self.managed_files(profile, scope), skills, (self.sources, scope))

    def managed_files(self, profile: HarnessProfile, scope: Scope) -> list[ManagedFile]:
        """Managed regions per file; lets a compiler merge files shared by emitters."""
        claude_dir = scope.root / ".claude"
        base = claude_dir if scope.kind == "user" else scope.root
        files = []
        body = instructions_body(self.sources, profile)
        if body:
            files += [markdown(base / "AGENTS.md", {"instructions": body}),
                      markdown(base / "CLAUDE.md", {"agents-import": "@AGENTS.md"})]
        settings = claude_dir / "settings.json"
        regions = settings_regions(profile, settings)
        if regions:
            files.append(ManagedFile(path=settings, format="json", regions=regions))
        if profile.work.provider == "awg":
            files.append(self._awg(scope))
        return files

    def _awg(self, scope: Scope) -> ManagedFile:
        name = ".claude.json" if scope.kind == "user" else ".mcp.json"
        return ManagedFile(path=scope.root / name, format="json", references_token=True,
                           regions={"mcpServers.awg": claude_awg_server(scope)})
