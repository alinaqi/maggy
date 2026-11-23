"""Codex emitter (verified against codex-cli 0.163.0).

user scope (root = HOME): ~/.codex/AGENTS.md (instructions + AWG section),
~/.codex/config.toml (sandbox defaults + [mcp_servers.awg]), ~/.codex/skills/.
project scope: AGENTS.md, .codex/config.toml (sandbox defaults only: a
checked-in file cannot hold the absolute token path), .agents/skills/.
"""

from __future__ import annotations

from maggy.harness.changes import FileChange, ManagedFile
from maggy.harness.emitters.awg import codex_awg_section, codex_awg_server
from maggy.harness.emitters.base import Capabilities, Capability, EmitterSources, Scope
from maggy.harness.emitters.common import markdown, run_plan
from maggy.harness.emitters.permissions import codex_sandbox
from maggy.harness.emitters.sources import instructions_body
from maggy.harness.schema import HarnessProfile

CAPABILITIES = Capabilities(
    instructions=Capability(level="native", notes=(
        "AGENTS.md managed block (~/.codex/AGENTS.md or repo AGENTS.md) plus the AWG section")),
    skills=Capability(level="native", notes=(
        "~/.codex/skills/<name>/SKILL.md (user), .agents/skills/<name>/SKILL.md (project)")),
    hooks=Capability(level="none", notes=(
        "not emitted; the runner enforces hook gates (codex-cli 0.163.0 lists a 'hooks' "
        "feature flag that Maggy does not target yet)")),
    mcp=Capability(level="native", notes=(
        "[mcp_servers.awg] awg mcp --token-file ~/.maggy/tokens/codex.token in "
        "~/.codex/config.toml (user scope only)")),
    permissions=Capability(level="partial", notes=(
        "sandbox_mode read-only/workspace-write and approval_policy on-request, only when "
        "worker.permission names a profile; no per-command "
        "allowlist; network=registries becomes full network access in workspace-write")),
)


class CodexEmitter:
    agent = "codex"

    def __init__(self, sources: EmitterSources) -> None:
        self.sources = sources

    def capabilities(self) -> Capabilities:
        return CAPABILITIES

    def plan(self, profile: HarnessProfile, scope: Scope) -> list[FileChange]:
        user = scope.kind == "user"
        skills_dir = scope.root / (".codex/skills" if user else ".agents/skills")
        skills = (list(profile.skills), skills_dir)
        return run_plan(self.managed_files(profile, scope), skills, (self.sources, scope))

    def managed_files(self, profile: HarnessProfile, scope: Scope) -> list[ManagedFile]:
        """Managed regions per file; lets a compiler merge files shared by emitters."""
        user = scope.kind == "user"
        base = scope.root / ".codex" if user else scope.root
        awg = profile.work.provider == "awg"
        agents = {"instructions": instructions_body(self.sources, profile)}
        agents = {k: v for k, v in agents.items() if v}
        if awg:
            agents["awg"] = codex_awg_section()
        config = codex_sandbox(profile)
        if awg and user:
            config["mcp_servers.awg"] = codex_awg_server(scope)
        files = [markdown(base / "AGENTS.md", agents)] if agents else []
        files.append(ManagedFile(path=scope.root / ".codex" / "config.toml", format="toml",
                                 regions=config, references_token=awg and user))
        return files
