"""Fail-closed launch policy: which adapter/permission runs are allowed (RFC §2.6.7)."""

from __future__ import annotations

from dataclasses import dataclass, replace

from maggy.harness.schema import HarnessProfile
from maggy.harness.schema_sections import PermissionProfile
from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.bypass import bypass_flags
from maggy.worker.templating import ArgvValues, render_argv

HOST_HINT = ("set worker.allow_host_execution: true in ~/.maggy/harness.yaml to run on the host, "
             "or use isolation: container")


class Refused(Exception):
    """The runner must not start this worker; the message says why."""


@dataclass(frozen=True)
class LaunchPlan:
    adapter: AdapterSpec
    permission: str
    env: dict[str, str]
    host_execution: bool

    def argv(self, values: ArgvValues) -> list[str]:
        """The run's argv, always with this plan's permission flags."""
        return render_argv(self.adapter, replace(values, permission=self.permission))


def resolve_launch(adapter: AdapterSpec, profile: HarnessProfile, permission: str) -> LaunchPlan:
    """A LaunchPlan, or Refused when the run would lack a boundary it needs."""
    if profile.worker.isolation == "container":
        raise Refused("container isolation not implemented yet")
    perm = _permission(adapter, profile, permission)
    bypass = bypass_flags(adapter)
    if bypass:
        raise Refused(f"adapter {adapter.name} uses permission-bypass flag(s) {', '.join(bypass)}; "
                      "these are only allowed with isolation: container")
    host = needs_boundary(perm) and not adapter.sandbox.native
    if host and not profile.worker.allow_host_execution:
        raise Refused(f"adapter {adapter.name} has no native sandbox and permission {permission!r} "
                      f"allows writes or shell; {HOST_HINT}")
    env = {**adapter.disable_awg.env, **adapter.permission_env.get(permission, {})}
    return LaunchPlan(adapter, permission, env, host)


def needs_boundary(perm: PermissionProfile) -> bool:
    return perm.write is not False or perm.shell is not False


def _permission(adapter: AdapterSpec, profile: HarnessProfile, name: str) -> PermissionProfile:
    if name not in profile.permissions.profiles:
        raise Refused(f"no permission profile {name!r} in permissions.profiles")
    if name not in adapter.permissions:
        raise Refused(f"adapter {adapter.name} has no mapping for {name!r}")
    return profile.permissions.profiles[name]
