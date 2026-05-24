"""Execute protocol steps and stream results."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator

from maggy.skills.protocol_models import Protocol

logger = logging.getLogger(__name__)

_CMD_TIMEOUT = 60.0


class ProtocolExecutor:
    async def execute(
        self, protocol: Protocol, working_dir: str,
        variables: dict[str, str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        vs = variables or {}
        for step in protocol.steps:
            if not _check_condition(step.condition, working_dir):
                yield _step_event(step.name, "skipped")
                continue
            yield _step_event(step.name, "running", label=step.label)
            cmd = _substitute(step.cmd, vs)
            ok, output = await _run(cmd, working_dir)
            if ok:
                yield _step_event(step.name, "done", output=output)
            elif step.optional:
                yield _step_event(step.name, "warning", output=output)
            else:
                yield _step_event(step.name, "failed", output=output)
                yield {
                    "type": "protocol_abort",
                    "reason": f"Step '{step.name}' failed",
                    "output": output,
                }
                return
        yield {"type": "protocol_complete", "protocol": protocol.name}


def _step_event(
    name: str, status: str, label: str = "",
    output: str = "",
) -> dict:
    d: dict = {"type": "protocol_step", "step": name, "status": status}
    if label:
        d["label"] = label
    if output:
        d["output"] = output
    return d


def _check_condition(condition: str, working_dir: str) -> bool:
    if not condition:
        return True
    wd = Path(working_dir)
    if "*" in condition:
        return bool(list(wd.rglob(condition))[:1])
    return (wd / condition).exists()


def _substitute(cmd: str, variables: dict[str, str]) -> str:
    result = cmd
    for k, v in variables.items():
        result = result.replace(f"{{{k}}}", v)
    return result


async def _run(cmd: str, cwd: str) -> tuple[bool, str]:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, cwd=cwd,
        )
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=_CMD_TIMEOUT,
        )
        output = stdout.decode("utf-8", errors="replace").strip()
        return proc.returncode == 0, output
    except asyncio.TimeoutError:
        return False, f"Command timed out after {_CMD_TIMEOUT}s"
    except Exception as e:
        return False, str(e)
