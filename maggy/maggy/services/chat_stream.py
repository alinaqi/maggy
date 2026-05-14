"""Chat streaming — subprocess execution and JSON parsing."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from maggy.services.chat import ChatSession

logger = logging.getLogger(__name__)

CLAUDE_BIN = shutil.which("claude") or "claude"
_STALE_MARKERS = ("not found",)


def _resolve_cwd(session: ChatSession) -> str:
    """Use working_dir if it exists, else fall back to repo_dir."""
    wd = session.working_dir
    if os.path.isdir(wd):
        return wd
    repo = getattr(session, "repo_dir", "")
    if repo and os.path.isdir(repo):
        logger.warning("Worktree missing %s, using repo_dir", wd)
        session.working_dir = repo
        return repo
    return wd


def build_cmd(session: ChatSession, message: str) -> list[str]:
    """Build claude CLI command."""
    prompt = _with_history_context(session, message)
    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
    ]
    if session.claude_session_id:
        cmd += ["--resume", session.claude_session_id]
    else:
        cmd += ["--continue"]
    return cmd


def _with_history_context(
    session: ChatSession, message: str,
) -> str:
    """Prepend history context on first use, then clear."""
    ctx = session.history_context
    if not ctx:
        return message
    session.history_context = ""
    return f"[Context]\n{ctx}\n[/Context]\n\n{message}"


def parse_chunks(
    text: str, session: ChatSession,
) -> list[dict]:
    """Parse a stream-json line into chunks."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [{"type": "text", "content": text}]
    if "session_id" in data and not session.claude_session_id:
        session.claude_session_id = data["session_id"]
    msg_type = data.get("type", "")
    if msg_type == "assistant":
        return _extract_chunks(data)
    if msg_type == "result":
        return [_extract_result(data)]
    return []


def _extract_result(data: dict) -> dict:
    """Extract cost/usage from result message."""
    chunk: dict = {"type": "result"}
    if (cost := data.get("cost_usd")) is not None:
        chunk["cost_usd"] = float(cost)
    if (u := data.get("usage")) is not None:
        chunk["input_tokens"] = int(u.get("input_tokens") or 0)
        chunk["output_tokens"] = int(u.get("output_tokens") or 0)
    return chunk


def _extract_chunks(data: dict) -> list[dict]:
    """Extract text and tool_use from assistant message."""
    content = data.get("message", {}).get("content", "")
    if not isinstance(content, list):
        return [{"type": "text", "content": str(content)}]
    chunks: list[dict] = []
    for block in content:
        btype = block.get("type", "")
        if btype == "text":
            chunks.append({"type": "text", "content": block.get("text", "")})
        elif btype == "tool_use":
            chunks.append({"type": "tool_use", "tool": block.get("name", ""), "input": block.get("input", {})})
    return chunks


def check_context_pressure(session: ChatSession) -> dict | None:
    """Warn if session messages are getting large."""
    from maggy.services.context_compactor import estimate_tokens
    msgs = [{"content": m.content} for m in session.messages]
    tokens = estimate_tokens(msgs)
    if tokens > 24_000:
        return {
            "type": "warning",
            "content": f"Context: ~{tokens} tokens",
        }
    return None


def _is_stale_error(chunk: dict) -> bool:
    """True if chunk indicates a stale Claude session ID."""
    if chunk.get("type") != "text":
        return False
    content = chunk.get("content", "")
    return content.startswith("Error:") and any(
        m in content.lower() for m in _STALE_MARKERS
    )


_CLAUDE_TIMEOUT = 180.0


async def _run_claude(
    session: ChatSession, message: str,
) -> AsyncGenerator[dict, None]:
    """Execute Claude CLI and yield parsed chunks."""
    cmd = build_cmd(session, message)
    resume = session.claude_session_id or "(new)"
    cwd = _resolve_cwd(session)
    logger.info("claude start pid=? resume=%s cwd=%s", resume, cwd)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd, env=env,
            limit=1024 * 1024,
        )
        session.pid = proc.pid or 0
        logger.info("claude pid=%d", proc.pid or 0)
        got_output = False
        async for line in _read_with_timeout(proc):
            got_output = True
            for chunk in parse_chunks(line, session):
                yield chunk
        rc = await proc.wait()
        logger.info("claude pid=%d exit=%d", proc.pid or 0, rc)
        if not got_output:
            yield {"type": "error", "content": "Claude produced no output"}
    except asyncio.TimeoutError:
        logger.warning("claude pid=%d timed out", proc.pid or 0)
        proc.kill()
        yield {"type": "error", "content": "Claude CLI timed out"}
    except FileNotFoundError as e:
        detail = f"claude CLI or cwd not found: {e}"
        logger.warning(detail)
        yield {"type": "error", "content": detail}
    except Exception as e:
        logger.exception("claude error")
        yield {"type": "error", "content": str(e)}


async def _read_with_timeout(
    proc: asyncio.subprocess.Process,
) -> AsyncGenerator[str, None]:
    """Read stdout lines with per-line timeout."""
    while True:
        try:
            line = await asyncio.wait_for(
                proc.stdout.readline(), timeout=_CLAUDE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise
        if not line:
            break
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            yield text


async def stream_message(
    session: ChatSession, message: str,
) -> AsyncGenerator[dict, None]:
    """Run a single message through Claude CLI."""
    from maggy.services.chat import ChatMessage
    session.messages.append(ChatMessage(role="user", content=message))
    session.status = "streaming"
    pressure = check_context_pressure(session)
    if pressure:
        yield pressure
    response_text = ""
    async for chunk in _run_claude(session, message):
        if _is_stale_error(chunk) and session.claude_session_id:
            session.claude_session_id = ""
            async for retry in _run_claude(session, message):
                if retry["type"] == "text":
                    response_text += retry.get("content", "")
                yield retry
            break
        if chunk["type"] == "text":
            response_text += chunk.get("content", "")
        yield chunk
    session.status = "idle"
    if response_text:
        session.messages.append(
            ChatMessage(role="assistant", content=response_text),
        )
