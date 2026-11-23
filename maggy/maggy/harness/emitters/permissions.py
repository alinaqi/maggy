"""The active permission profile (worker.permission) mapped to native rules."""

from __future__ import annotations

from maggy.harness.schema import HarnessProfile
from maggy.harness.schema_sections import PermissionProfile

EDIT_TOOLS = ["Edit", "Write", "MultiEdit", "NotebookEdit"]
WEB_TOOLS = ["WebFetch", "WebSearch"]


def active_permission(profile: HarnessProfile) -> PermissionProfile | None:
    return profile.permissions.profiles.get(profile.worker.permission)


def _commands(profile: HarnessProfile) -> list[str]:
    return [cmd for cmd in profile.commands.model_dump().values() if cmd]


def _bucket(value: object) -> str | None:
    if value is False:
        return "deny"
    return "allow" if value in (True, "workspace") else None


def claude_rules(profile: HarnessProfile) -> dict[str, list[str]]:
    """settings.json permissions.allow/deny. False denies, True/workspace allows;
    network=registries has no Claude rule; shell=allowlist allows Bash(<command>)."""
    rules: dict[str, list[str]] = {"allow": [], "deny": []}
    perm = active_permission(profile)
    if perm is None:
        return rules
    for value, tools in ((perm.write, EDIT_TOOLS), (perm.network, WEB_TOOLS), (perm.shell, ["Bash"])):
        bucket = _bucket(value)
        if bucket:
            rules[bucket] += tools
    if perm.shell == "allowlist":
        rules["allow"] += [f"Bash({cmd})" for cmd in _commands(profile)]
    return rules


def codex_sandbox(profile: HarnessProfile) -> dict:
    """config.toml sandbox defaults: read-only when writes are off, else workspace-write."""
    perm = active_permission(profile)
    read_only = perm is not None and perm.write is False
    regions: dict = {"sandbox_mode": "read-only" if read_only else "workspace-write",
                     "approval_policy": "on-request"}
    if perm is not None and not read_only:
        regions["sandbox_workspace_write.network_access"] = perm.network is not False
    return regions


def opencode_rules(profile: HarnessProfile) -> dict[str, object]:
    """opencode.json permission.<tool>: edit, webfetch/websearch, bash. network=registries has no
    rule; shell=allowlist asks for everything and allows each profile command (last match wins)."""
    perm = active_permission(profile)
    if perm is None:
        return {}
    rules: dict[str, object] = {}
    for value, tools in ((perm.write, ["edit"]), (perm.network, ["webfetch", "websearch"]),
                         (perm.shell, ["bash"])):
        action = _bucket(value)
        rules.update({tool: action for tool in tools if action})
    if perm.shell == "allowlist":
        rules["bash"] = {"*": "ask", **{cmd: "allow" for cmd in _commands(profile)}}
    return rules
