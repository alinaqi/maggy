"""The checks behind `maggy harness doctor`; each returns (info, warnings, errors)."""

from __future__ import annotations

from dataclasses import dataclass, field

from maggy.harness.cli.awg_tokens import token_path
from maggy.harness.cli.detect import TESTED_VERSIONS, agent_version
from maggy.harness.cli.env import ToolEnv
from maggy.harness.compile import emitters_for
from maggy.harness.schema import HarnessProfile

T3_ADVICE = [
    "T3: T3 inherits each driven agent's native config; Maggy emits nothing T3-specific.",
    "T3: T3 injects its own MCP server per thread, next to the AWG server emitted here.",
    "T3: Claude profiles with a custom home read only project/local settings: "
    "run `maggy harness apply --scope project` in each repo you open from T3.",
]


@dataclass
class Findings:
    info: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def capability_rows(env: ToolEnv, agents: list[str], found: Findings) -> list[str]:
    """One row per agent: installed vs tested version and capability levels."""
    rows = [f"{'agent':<9} {'version':<9} {'tested':<9} capabilities"]
    for emitter in emitters_for(agents, env.sources):
        agent, tested = emitter.agent, TESTED_VERSIONS[emitter.agent]
        version = agent_version(env, agent)
        levels = " ".join(f"{k}={v['level']}" for k, v in emitter.capabilities().model_dump().items())
        rows.append(f"{agent:<9} {version or '-':<9} {tested:<9} {levels}")
        _version_finding(agent, version, found)
    return rows


def capability_gaps(env: ToolEnv, agents: list[str]) -> list[str]:
    """Every non-native capability, with what falls back (RFC §2.2: report gaps honestly)."""
    return [f"GAP {emitter.agent} {name}={cap['level']}: {cap['notes']}"
            for emitter in emitters_for(agents, env.sources)
            for name, cap in emitter.capabilities().model_dump().items() if cap["level"] != "native"]


def _version_finding(agent: str, version: str | None, found: Findings) -> None:
    tested = TESTED_VERSIONS[agent]
    if version is None:
        found.errors.append(f"{agent}: not found on PATH")
    elif version != tested:
        found.warnings.append(f"{agent} {version} drifts from tested {tested}; re-check its emitted config")


def _token_check(env: ToolEnv, agent: str, found: Findings) -> None:
    path = token_path(env, agent)
    if not path.is_file():
        found.errors.append(f"{agent}: missing token file {path} (run `maggy harness init`)")
        return
    if env.which("awg") is None:
        found.errors.append(f"{agent}: awg not found on PATH; cannot check {path}")
        return
    done = env.run(["awg", "--token-file", str(path), "status"])
    if done.returncode == 0:
        found.info.append(f"{agent}: AWG reachable with {path}")
    else:
        found.errors.append(f"{agent}: AWG not reachable with {path} (exit {done.returncode})")


def awg_checks(env: ToolEnv, profile: HarnessProfile, agents: list[str]) -> Findings:
    """Token files and AWG reachability per agent, then T3 advice."""
    found = Findings()
    if profile.work.provider == "awg":
        for agent in agents:
            _token_check(env, agent, found)
    if "t3" in profile.surfaces:
        found.info += T3_ADVICE
    return found


def host_execution_warnings(profile: HarnessProfile) -> list[str]:
    """RFC §2.6.7: running unsandboxed agents on the host is an explicit, flagged opt-in."""
    if not profile.worker.allow_host_execution:
        return []
    return ["worker.allow_host_execution is true: write- or shell-capable runs on adapters "
            "without a native sandbox (opencode, pi) execute directly on this host"]
