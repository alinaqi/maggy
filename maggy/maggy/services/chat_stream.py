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
_MAX_RETRIES = 2

_SESSION_ERRORS = ("not found", "invalid signature", "thinking block", "session")
_OVERLOAD_ERRORS = ("overloaded", "rate limit", "529", "capacity")
_CONTEXT_ERRORS = ("too long", "context length", "max tokens", "token limit")


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


def _build_system_prompt(session: ChatSession) -> str:
    """Build system prompt with layered assembly (includes skill index)."""
    wd = session.working_dir
    pkey = getattr(session, "project_key", "") or "project"
    try:
        from maggy.prompt.assembly import PromptAssemblyService
        return PromptAssemblyService().assemble(wd, pkey)
    except Exception:
        from maggy.services.chat_grounding import build_enriched_prompt
        return build_enriched_prompt(wd, pkey)


def build_cmd(session: ChatSession, message: str) -> list[str]:
    """Build claude CLI command."""
    prompt = _with_history_context(session, message)
    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
        "--append-system-prompt", _build_system_prompt(session),
    ]
    resume_id = (session.claude_session_id or "").strip()
    if resume_id:
        cmd += ["--resume", resume_id]
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
    if msg_type == "error":
        err_msg = data.get("error", {})
        if isinstance(err_msg, dict):
            err_msg = err_msg.get("message", str(err_msg))
        return [{"type": "error", "content": f"API Error: {err_msg}"}]
    if msg_type == "system" and "error" in data.get("message", "").lower():
        return [{"type": "error", "content": data.get("message", "")}]
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


def _classify_error(chunk: dict) -> str | None:
    """Classify an error chunk into a recovery strategy.

    Returns: 'session' | 'overload' | 'context' | 'generic' | None
    """
    if chunk.get("type") not in ("text", "error"):
        return None
    content = chunk.get("content", "").lower()
    if not content:
        return None
    if any(m in content for m in _SESSION_ERRORS):
        return "session"
    if any(m in content for m in _OVERLOAD_ERRORS):
        return "overload"
    if any(m in content for m in _CONTEXT_ERRORS):
        return "context"
    if chunk.get("type") == "error":
        return "generic"
    return None


def _peek_type(text: str) -> str:
    """Extract type field from JSON for logging."""
    try:
        return json.loads(text).get("type", "?")
    except Exception:
        return "parse-error"


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
            chunks = parse_chunks(line, session)
            if not chunks:
                logger.debug("skip line type=%s", _peek_type(line))
            for chunk in chunks:
                logger.debug("yield chunk type=%s", chunk.get("type"))
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


async def _apply_recovery(
    session: ChatSession, error_class: str, error_content: str,
) -> dict:
    """Apply a recovery strategy and return a status chunk."""
    if error_class == "session":
        session.claude_session_id = ""
        # session ID cleared — persisted below
        _persist_session_id_now(session)
        return {"type": "agent_status", "status": "Session expired — retrying fresh..."}
    if error_class == "context":
        from maggy.services.context_compactor import compact_messages
        before = len(session.messages)
        session.messages = compact_messages(session.messages)
        trimmed = before - len(session.messages)
        session._persisted_idx = 0
        session.claude_session_id = ""
        _persist_session_id_now(session)
        return {"type": "agent_status", "status": f"Context too long — compacted {trimmed} messages, retrying..."}
    if error_class == "overload":
        await asyncio.sleep(3)
        return {"type": "agent_status", "status": "API overloaded — waiting 3s and retrying..."}
    session.claude_session_id = ""
    _persist_session_id_now(session)
    return {"type": "agent_status", "status": f"Error encountered — retrying fresh... ({error_content[:80]})"}


def _persist_session_id_now(session: ChatSession) -> None:
    """Immediately persist cleared session ID to SQLite."""
    try:
        from maggy.services.session_store import SessionStore
        from pathlib import Path
        db_path = Path.home() / ".maggy" / "sessions.db"
        if db_path.exists():
            store = SessionStore(db_path)
            store.update_claude_id(session.id, "")
    except Exception:
        pass


async def stream_message(
    session: ChatSession, message: str,
) -> AsyncGenerator[dict, None]:
    """Run a message through Claude CLI with automatic error recovery."""
    from maggy.services.chat import ChatMessage
    session.messages.append(ChatMessage(role="user", content=message))
    session.status = "streaming"
    pressure = check_context_pressure(session)
    if pressure:
        yield pressure

    response_text = ""
    attempt = 0

    while attempt <= _MAX_RETRIES:
        error_hit = False
        async for chunk in _run_claude(session, message):
            error_class = _classify_error(chunk)
            if error_class and attempt < _MAX_RETRIES:
                error_hit = True
                attempt += 1
                logger.info(
                    "Self-correction: %s error (attempt %d/%d): %s",
                    error_class, attempt, _MAX_RETRIES,
                    chunk.get("content", "")[:120],
                )
                status = await _apply_recovery(
                    session, error_class, chunk.get("content", ""),
                )
                _learn_error(session, error_class, chunk.get("content", ""))
                yield status
                break
            if error_class and attempt >= _MAX_RETRIES:
                session.claude_session_id = ""
                # session ID cleared — persisted below
                _persist_session_id_now(session)
                _learn_error(session, error_class, chunk.get("content", ""))
                yield {"type": "error", "content": "Session corrupted — cleared. Please resend your message."}
                error_hit = True
                break
            if chunk["type"] == "text":
                response_text += chunk.get("content", "")
            yield chunk
        if not error_hit:
            break

    session.status = "idle"
    if response_text:
        session.messages.append(
            ChatMessage(role="assistant", content=response_text),
        )
        _learn_chat(session, message, response_text, error_hit)


def _learn_chat(
    session: ChatSession, user_msg: str, assistant_msg: str, had_error: bool,
) -> None:
    try:
        from maggy.learn.chat_learner import extract_signals
        from maggy.learn._writer import fire_and_forget_write
        signals = extract_signals(user_msg, assistant_msg, had_error)
        if signals:
            engram = getattr(session, "_engram_store", None)
            pkey = getattr(session, "project_key", "")
            fire_and_forget_write(engram, "chat-feedback", signals, pkey)
    except Exception:
        pass


def _learn_error(
    session: ChatSession, error_class: str, error_content: str,
) -> None:
    try:
        from maggy.learn.error_learner import build_error_signal
        from maggy.learn._writer import fire_and_forget_write
        sig = build_error_signal(error_class, error_content, True)
        engram = getattr(session, "_engram_store", None)
        pkey = getattr(session, "project_key", "")
        fire_and_forget_write(engram, "error-patterns", [sig], pkey)
    except Exception:
        pass
