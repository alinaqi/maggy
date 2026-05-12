"""Chat streaming — subprocess execution and JSON parsing.

Extracted from ChatManager for quality-gate compliance.
Handles claude CLI subprocess, stream-json parsing, and
assistant message extraction.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from maggy.services.chat import ChatSession

logger = logging.getLogger(__name__)

CLAUDE_BIN = "claude"


def build_cmd(session: ChatSession, message: str) -> list[str]:
    """Build claude CLI command."""
    cmd = [
        CLAUDE_BIN, "-p", message,
        "--output-format", "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
    ]
    if session.claude_session_id:
        cmd += ["--resume", session.claude_session_id]
    return cmd


def parse_chunk(
    text: str, session: ChatSession,
) -> dict | None:
    """Parse a stream-json line from Claude."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"type": "text", "content": text}
    if "session_id" in data and not session.claude_session_id:
        session.claude_session_id = data["session_id"]
    msg_type = data.get("type", "")
    if msg_type == "assistant":
        return _extract_assistant(data)
    if msg_type == "result":
        content = data.get("result", "")
        chunk: dict = {"type": "result", "content": content}
        cost = data.get("cost_usd")
        if cost is not None:
            chunk["cost_usd"] = float(cost)
        usage = data.get("usage")
        if usage is not None:
            chunk["input_tokens"] = int(usage.get("input_tokens") or 0)
            chunk["output_tokens"] = int(usage.get("output_tokens") or 0)
        return chunk
    return None


def _extract_assistant(data: dict) -> dict:
    """Extract text from assistant message."""
    content = data.get("message", {}).get("content", "")
    if isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if b.get("type") == "text"
        ]
        return {"type": "text", "content": "".join(parts)}
    return {"type": "text", "content": str(content)}


def check_context_pressure(session: ChatSession) -> dict | None:
    """Warn if session messages are getting large."""
    from maggy.services.context_compactor import estimate_tokens
    msgs = [{"content": m.content} for m in session.messages]
    tokens = estimate_tokens(msgs)
    if tokens > 24_000:
        return {"type": "warning", "content": f"Context: ~{tokens} tokens"}
    return None


async def stream_message(
    session: ChatSession, message: str,
) -> AsyncGenerator[dict, None]:
    """Run a single message through Claude CLI."""
    from maggy.services.chat import ChatMessage

    session.messages.append(
        ChatMessage(role="user", content=message),
    )
    session.status = "streaming"
    pressure = check_context_pressure(session)
    if pressure:
        yield pressure
    cmd = build_cmd(session, message)
    response_text = ""
    try:
        env = {
            k: v for k, v in os.environ.items()
            if k != "CLAUDECODE"
        }
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=session.working_dir,
            env=env,
        )
        session.pid = proc.pid or 0
        async for line in proc.stdout:
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            chunk = parse_chunk(text, session)
            if chunk:
                response_text += chunk.get("content", "")
                yield chunk
        await proc.wait()
        session.status = "idle"
    except FileNotFoundError:
        session.status = "error"
        yield {"type": "error", "content": "claude CLI not found"}
    except Exception as e:
        session.status = "error"
        yield {"type": "error", "content": str(e)}
    if response_text:
        session.messages.append(
            ChatMessage(role="assistant", content=response_text),
        )
