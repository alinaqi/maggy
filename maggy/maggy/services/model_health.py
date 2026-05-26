"""Model health checking — ping models, verify they respond."""

from __future__ import annotations

import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from maggy.services.council_config import ModelDef

_ALLOWED_PREFIXES = {
    "echo", "printf",
    "qwen3", "deepseek", "kimi", "grok", "codex",
    "gemini-api", "gemini-cli", "agy-delegate",
}

_BLOCKED_COMMANDS = {"rm", "bash", "sh", "zsh", "curl", "wget", "nc", "python", "python3", "perl", "ruby", "node"}


def _validate_cmd(argv: list[str]) -> bool:
    if not argv:
        return False
    base = Path(argv[0]).name
    if base in _BLOCKED_COMMANDS:
        return False
    if base in _ALLOWED_PREFIXES:
        return True
    resolved = Path(argv[0]).expanduser()
    return resolved.name in _ALLOWED_PREFIXES


@dataclass
class HealthResult:
    model_id: str
    success: bool
    latency_ms: float = 0.0
    output: str = ""
    error: str = ""


def check_model_health(
    model_id: str,
    cmd_argv: list[str],
    timeout: int = 15,
) -> HealthResult:
    if not cmd_argv:
        return HealthResult(model_id=model_id, success=False, error="No command configured")

    if not _validate_cmd(cmd_argv):
        return HealthResult(model_id=model_id, success=False, error="Command not in allowlist")

    expanded = list(cmd_argv)
    expanded[0] = str(Path(expanded[0]).expanduser())

    prompt = "Respond with exactly: OK"
    full_cmd = expanded + [prompt]

    start = time.monotonic()
    try:
        r = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = (time.monotonic() - start) * 1000
        if r.returncode == 0:
            return HealthResult(
                model_id=model_id,
                success=True,
                latency_ms=round(elapsed, 1),
                output=r.stdout.strip()[:500],
            )
        return HealthResult(
            model_id=model_id,
            success=False,
            latency_ms=round(elapsed, 1),
            error=r.stderr.strip()[:300] or f"Exit code {r.returncode}",
        )
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return HealthResult(
            model_id=model_id,
            success=False,
            latency_ms=round(elapsed, 1),
            error=f"Timeout after {timeout}s",
        )
    except FileNotFoundError:
        return HealthResult(
            model_id=model_id,
            success=False,
            error=f"Command not found: {expanded[0]}",
        )
    except Exception as e:
        return HealthResult(
            model_id=model_id,
            success=False,
            error=str(e)[:200],
        )


def check_all_models(
    models: list[ModelDef],
    timeout: int = 15,
) -> list[HealthResult]:
    results: list[HealthResult] = []
    to_check = []
    for m in models:
        argv = m.cmd_argv()
        if argv is None:
            results.append(HealthResult(
                model_id=m.id,
                success=False,
                error="No command configured",
            ))
        else:
            to_check.append((m.id, argv))

    with ThreadPoolExecutor(max_workers=min(len(to_check), 6)) as pool:
        futures = {
            pool.submit(check_model_health, mid, argv, timeout): mid
            for mid, argv in to_check
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    return sorted(results, key=lambda r: next(
        (m.tier for m in models if m.id == r.model_id), 99
    ))
