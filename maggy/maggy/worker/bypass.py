"""Permission-bypass flags: allowed only under container isolation (RFC §2.3, §2.6.7)."""

from __future__ import annotations

from maggy.worker.adapter_spec import AdapterSpec

# Exact flags (also as --flag=value) and mode values that switch a CLI's checks off.
BYPASS_FLAGS = frozenset({"--yolo", "--auto", "--dangerously-skip-permissions",
                          "--allow-dangerously-skip-permissions",
                          "--dangerously-bypass-approvals-and-sandbox"})
BYPASS_PREFIXES = ("--dangerously", "--allow-dangerously")
BYPASS_VALUES = ("bypassPermissions", "danger-full-access")


def bypass_flags(adapter: AdapterSpec) -> list[str]:
    """Every adapter element (argv, flags, env values) that bypasses permissions."""
    return [item for item in _elements(adapter) if is_bypass(item)]


def is_bypass(item: str) -> bool:
    name = item.partition("=")[0]
    return (name in BYPASS_FLAGS or name.startswith(BYPASS_PREFIXES)
            or any(value in item for value in BYPASS_VALUES))


def _elements(adapter: AdapterSpec) -> list[str]:
    envs = [adapter.disable_awg.env, *adapter.permission_env.values()]
    lists = [adapter.argv, adapter.model_flags, adapter.disable_awg.flags,
             *adapter.permissions.values(), *(list(env.values()) for env in envs)]
    return [item for items in lists for item in items]
