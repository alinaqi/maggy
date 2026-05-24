"""Pi backend — wraps PiAdapter for non-Claude CLI models."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from maggy.adapters.pi import PiAdapter
    from maggy.services.chat_models import ChatSession

logger = logging.getLogger(__name__)

_PI_MODELS = frozenset({
    "deepseek", "kimi", "local", "qwen", "gemini", "codex", "grok",
    "deepseek-flash", "deepseek-pro", "gemini-flash", "gemini-flash-lite",
    "gemini-pro-search", "gpt",
})


class PiBackend:
    name = "pi"

    def __init__(self, pi: PiAdapter) -> None:
        self._pi = pi

    def handles(self, model: str) -> bool:
        return model.lower() in _PI_MODELS

    async def execute(
        self,
        model: str,
        message: str,
        session: ChatSession,
        working_dir: str,
        project_key: str,
    ) -> AsyncGenerator[dict, None]:
        ctx = _build_context(working_dir, project_key)
        hist = getattr(session, "history_context", "") or ""
        if hist:
            session.history_context = ""
            ctx += f"[Previous conversation context]\n{hist}\n[/Previous conversation context]\n\n"
        chat_hist = _recent_messages(session, max_turns=10)
        if chat_hist:
            ctx += f"{chat_hist}\n\n"
        result = await self._pi.send_prompt(
            model, ctx + message, working_dir,
        )
        if result.success:
            yield {"type": "text", "content": result.output or ""}
            yield {
                "type": "result",
                "cost_usd": result.cost_usd,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }
        else:
            yield {"type": "error", "content": result.error or "Pi model failed"}


def _recent_messages(session, max_turns: int = 10) -> str:
    msgs = getattr(session, "messages", None) or []
    if not msgs:
        return ""
    recent = msgs[-max_turns:]
    lines = ["[Recent conversation]"]
    for m in recent:
        role = getattr(m, "role", "user")
        content = getattr(m, "content", "") or ""
        content = content[:500]
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    lines.append("[/Recent conversation]")
    return "\n".join(lines)


def _build_context(working_dir: str, project_key: str) -> str:
    base = (
        "You are an AI coding assistant in Maggy. "
        "The user is a software engineer. Respond helpfully and concisely. "
        f"Working directory: {working_dir}\n\n"
    )
    try:
        from maggy.skills.injector import build_skill_context, match_skills
        from maggy.skills.registry import SkillRegistry
        reg = SkillRegistry()
        reg.load_global()
        if project_key:
            reg.load_project(project_key, working_dir)
        skills = reg.resolve(project_key or None)
        matched = match_skills(skills, working_dir)
        ctx = build_skill_context(matched, max_chars=3000)
        if ctx:
            return f"{base}{ctx}\n\n"
    except Exception as e:
        logger.debug("Pi skill injection skipped: %s", e)
    return base
