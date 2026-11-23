"""Readers for the Phase 1 exit test: what each agent got after `harness apply`."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

AGENTS = ["claude", "codex", "opencode", "pi"]
_RULES = re.compile(r"<!-- maggy:begin instructions -->\n(.*?)<!-- maggy:end instructions -->", re.S)


def agent_dirs(home: Path) -> dict[str, Path]:
    return {"claude": home / ".claude", "codex": home / ".codex",
            "opencode": home / ".config" / "opencode", "pi": home / ".pi" / "agent"}


def rules_block(path: Path) -> str:
    [found] = _RULES.findall(path.read_text())
    return found


def _names(skills_dir: Path) -> set[str]:
    return {p.parent.name for p in skills_dir.glob("*/SKILL.md")}


def _configured_dirs(home: Path, agent: str) -> list[str]:
    """Extra skill dirs an agent loads by config: opencode skills.paths, pi settings skills."""
    if agent == "opencode":
        return opencode_config(home).get("skills", {}).get("paths", [])
    settings = home / ".pi" / "agent" / "settings.json"
    if agent == "pi" and settings.is_file():
        return json.loads(settings.read_text()).get("skills", [])
    return []


def skill_names(home: Path, agent: str) -> set[str]:
    """Every skill the agent loads: its skills dir plus dirs named in its config."""
    found = _names(agent_dirs(home)[agent] / "skills")
    for extra in _configured_dirs(home, agent):
        found |= _names(Path(extra))
    return found


def awg_token_refs(home: Path) -> dict[str, str]:
    """The token file each agent's AWG MCP server / extension is pointed at."""
    claude = json.loads((home / ".claude.json").read_text())["mcpServers"]["awg"]["args"][-1]
    codex = tomllib.loads((home / ".codex" / "config.toml").read_text())["mcp_servers"]["awg"]["args"][-1]
    opencode = opencode_config(home)["mcp"]["awg"]["command"][-1]
    pi = json.loads((home / ".pi" / "agent" / "awg.json").read_text())["tokenFile"]
    return {"claude": claude, "codex": codex, "opencode": opencode, "pi": pi}


def opencode_config(home: Path) -> dict:
    return json.loads((home / ".config" / "opencode" / "opencode.json").read_text())


def codex_mcp_list(home: Path) -> list[dict] | None:
    """`codex mcp list --json` on the emitted config (temp HOME); None without codex."""
    if shutil.which("codex") is None:
        return None
    env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}
    done = subprocess.run(["codex", "mcp", "list", "--json"], capture_output=True, text=True,
                          env=env, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)
