"""OpenCode emitter (verified against opencode 1.19.6).

user scope (root = HOME): $XDG_CONFIG_HOME/opencode (default ~/.config/opencode):
AGENTS.md (global rules), opencode.json, skills/. project scope: AGENTS.md,
opencode.json, .opencode/skills/. OpenCode loads <config>/AGENTS.md and the
repo AGENTS.md itself; `instructions` names the same file (paths are deduped).
"""

from __future__ import annotations

import os
from pathlib import Path

from maggy.harness.changes import FileChange, ManagedFile
from maggy.harness.emitters.base import Capabilities, Capability, EmitterSources, Scope
from maggy.harness.emitters.common import markdown, run_plan
from maggy.harness.emitters.opencode_config import OpenCodeConfig
from maggy.harness.emitters.sources import instructions_body
from maggy.harness.schema import HarnessProfile

CAPABILITIES = Capabilities(
    instructions=Capability(level="native", notes=(
        "AGENTS.md managed block (<config>/AGENTS.md or repo AGENTS.md), also listed in "
        "opencode.json instructions")),
    skills=Capability(level="native", notes=(
        "<config>/skills/<name>/SKILL.md (project: .opencode/skills); the AWG skill via skills.paths "
        "into the AWG checkout (user scope, needs MAGGY_AWG_REPO); OpenCode also scans ~/.claude/skills")),
    hooks=Capability(level="none", notes=(
        "not emitted: OpenCode hooks are JS plugins; the runner enforces hook gates. AWG's lease "
        "heartbeat plugin is wired separately (plugin key, user scope)")),
    mcp=Capability(level="native", notes=(
        "mcp.awg local server: awg mcp --token-file ~/.maggy/tokens/opencode.token "
        "(project opencode.json uses {env:HOME})")),
    permissions=Capability(level="partial", notes=(
        "worker.permission profile -> permission.edit/webfetch/websearch/bash; shell=allowlist is "
        "bash {'*': ask, <command>: allow}; network=registries has no rule; user bash patterns are "
        "kept and dropped commands are not removed")),
)


def config_dir(scope: Scope) -> Path:
    """User: $XDG_CONFIG_HOME/opencode (absolute values only), else ~/.config/opencode."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else scope.root / ".config"
    return base / "opencode"


class OpenCodeEmitter:
    agent = "opencode"

    def __init__(self, sources: EmitterSources) -> None:
        self.sources = sources

    def capabilities(self) -> Capabilities:
        return CAPABILITIES

    def plan(self, profile: HarnessProfile, scope: Scope) -> list[FileChange]:
        user = scope.kind == "user"
        skills_dir = config_dir(scope) / "skills" if user else scope.root / ".opencode" / "skills"
        skills = (list(profile.skills), skills_dir)
        return run_plan(self.managed_files(profile, scope), skills, (self.sources, scope))

    def managed_files(self, profile: HarnessProfile, scope: Scope) -> list[ManagedFile]:
        """Managed regions per file; lets a compiler merge files shared by emitters."""
        base = config_dir(scope) if scope.kind == "user" else scope.root
        body = instructions_body(self.sources, profile)
        files = [markdown(base / "AGENTS.md", {"instructions": body})] if body else []
        ref = (str(base / "AGENTS.md") if scope.kind == "user" else "AGENTS.md") if body else None
        path = base / "opencode.json"
        regions = OpenCodeConfig(path, scope, self.sources).regions(profile, ref)
        if regions:
            files.append(ManagedFile(path=path, format="json", regions=regions,
                                     references_token=profile.work.provider == "awg"))
        return files
