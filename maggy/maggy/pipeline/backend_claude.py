"""Claude backend — wraps ChatManager for Claude CLI execution."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from maggy.services.chat import ChatManager
    from maggy.services.chat_models import ChatSession

logger = logging.getLogger(__name__)

_PI_MODELS = frozenset({
    "deepseek", "kimi", "local", "qwen", "gemini", "codex", "grok",
    "deepseek-flash", "deepseek-pro", "gemini-flash", "gemini-flash-lite",
    "gemini-pro-search", "gpt",
})


class ClaudeBackend:
    name = "claude"

    def __init__(self, chat: ChatManager) -> None:
        self._chat = chat

    def handles(self, model: str) -> bool:
        return model.lower() not in _PI_MODELS

    async def execute(
        self,
        model: str,
        message: str,
        session: ChatSession,
        working_dir: str,
        project_key: str,
    ) -> AsyncGenerator[dict, None]:
        async for chunk in self._chat.send(session.id, message):
            yield chunk
