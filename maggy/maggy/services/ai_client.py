"""AI client — uses API key or falls back to CLI subscription."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil

logger = logging.getLogger(__name__)

_DS_BASE = "https://api.deepseek.com/v1"


async def ai_complete(
    prompt: str, cfg, model: str = "",
) -> str | None:
    """Get AI completion. Tries DeepSeek, Anthropic, then CLI."""
    target_model = model or cfg.ai.model
    if target_model.startswith("deepseek-"):
        result = await _deepseek_complete(prompt, target_model)
        if result:
            return result
    if cfg.ai.api_key:
        return await _api_complete(
            prompt, cfg.ai.api_key, target_model,
        )
    if shutil.which("claude"):
        return await _cli_complete(prompt, "claude")
    if shutil.which("codex"):
        return await _cli_complete(prompt, "codex")
    return None


async def _deepseek_complete(
    prompt: str, model: str,
) -> str | None:
    """Call DeepSeek via OpenAI-compatible API."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{_DS_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning("DeepSeek API failed: %s", e)
        return None


async def _api_complete(
    prompt: str, api_key: str, model: str,
) -> str | None:
    """Call Anthropic API directly."""
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        msg = await client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        logger.warning("API completion failed: %s", e)
        return None


async def _cli_complete(
    prompt: str, cli: str,
) -> str | None:
    """Call AI via CLI subscription (claude/codex)."""
    try:
        process = await asyncio.create_subprocess_exec(
            cli, "-p", prompt, "--output-format", "text",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=600,
        )
        if process.returncode == 0:
            return stdout.decode().strip()
        logger.warning(
            "%s CLI failed (rc=%d): %s",
            cli, process.returncode,
            stderr.decode()[:200],
        )
    except asyncio.TimeoutError:
        logger.warning("%s CLI timed out", cli)
    except OSError as e:
        logger.warning("%s CLI not available: %s", cli, e)
    return None
