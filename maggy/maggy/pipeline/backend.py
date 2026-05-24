"""Backend protocol — common interface for all model backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncGenerator, Protocol, runtime_checkable

if TYPE_CHECKING:
    from maggy.services.chat_models import ChatSession


@runtime_checkable
class Backend(Protocol):
    name: str

    async def execute(
        self,
        model: str,
        message: str,
        session: ChatSession,
        working_dir: str,
        project_key: str,
    ) -> AsyncGenerator[dict, None]:
        ...

    def handles(self, model: str) -> bool:
        ...
