"""Semantic intent classification via local Ollama model.

Sends a short prompt to the local Qwen model to classify the user's
intent into a known task type. Falls back to keyword matching when
Ollama is unavailable.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3-coder:30b-a3b-q8_0"
TIMEOUT = 10.0

KNOWN_TYPES = frozenset({
    "review", "security", "search", "docs",
    "tests", "frontend", "general",
})

_PROMPT = (
    "Classify the user message into exactly one category.\n"
    "- review: code review, PR review, validate, verify, look over changes, check correctness\n"
    "- security: auth, encryption, vulnerabilities, CSRF, OAuth, permissions, harden\n"
    "- search: find files, locate code, where is, explain how something works\n"
    "- docs: write documentation, README, docstrings, API docs\n"
    "- tests: unit tests, pytest, test coverage, fixtures, mocks, assertions\n"
    "- frontend: CSS, UI, layout, components, responsive, styling\n"
    "- general: anything else\n"
    'Respond ONLY with JSON: {{"type": "<category>"}}\n\n'
    "Message: {message} /no_think"
)


def _parse_response(text: str) -> str:
    """Extract type from model JSON response."""
    try:
        clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        m = re.search(r"\{[^}]+\}", clean)
        if not m:
            return "general"
        data = json.loads(m.group())
        t = data.get("type", "general").lower().strip()
        return t if t in KNOWN_TYPES else "general"
    except (json.JSONDecodeError, AttributeError):
        return "general"


async def classify_intent(message: str) -> str:
    """Classify intent via local Ollama model.

    Falls back to keyword matching if Ollama is down.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": _PROMPT.format(message=message),
                    }],
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 20},
                },
                timeout=TIMEOUT,
            )
        text = resp.json().get("message", {}).get("content", "")
        return _parse_response(text)
    except Exception:
        logger.debug("Ollama unavailable, using keyword fallback")
        from maggy.services.chat_router import estimate_type
        return estimate_type(message)
