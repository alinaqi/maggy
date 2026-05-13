"""Media detection + streaming for chat — images and documents."""

from __future__ import annotations

from typing import AsyncGenerator


def detect_image(message: str) -> tuple[str, str] | None:
    """Check if message contains an image file path."""
    from maggy.services.vision import extract_image_path
    return extract_image_path(message)


def detect_document(message: str) -> tuple[str, str] | None:
    """Check if message contains a document file path."""
    from maggy.services.documents import extract_document_path
    return extract_document_path(message)


async def stream_vision(
    path: str, prompt: str | None,
) -> AsyncGenerator[dict, None]:
    """Stream vision analysis with Ollama->Claude escalation."""
    from maggy.services.model_escalation import vision_with_escalation
    async for chunk in vision_with_escalation(path, prompt or "Analyze this image."):
        yield chunk


async def stream_doc(
    path: str, prompt: str | None, session,
) -> AsyncGenerator[dict, None]:
    """Extract document text and forward to Claude."""
    from maggy.services.documents import process_document
    async for chunk in process_document(path, prompt, session):
        yield chunk
