"""Semantic classification via local Ollama model.

Classifies task type and blast score (complexity 1-10) using the local
Qwen model. Falls back to keyword matching when Ollama is unavailable.
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

_TYPE_PROMPT = (
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

_BLAST_PROMPT = (
    "Rate the complexity of this coding task from 1 to 10.\n"
    "1-2: trivial (typo, rename, config change)\n"
    "3-4: simple (small bug fix, add logging, format)\n"
    "5-6: moderate (new endpoint, feature, component)\n"
    "7-8: complex (refactor, migration, multi-file)\n"
    "9-10: critical (architecture, security overhaul, system redesign)\n"
    'Respond ONLY with JSON: {{"blast": <number>}}\n\n'
    "Message: {message} /no_think"
)


async def _ollama_call(prompt: str) -> str | None:
    """Send a prompt to Ollama and return content."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 20},
                },
                timeout=TIMEOUT,
            )
        return resp.json().get("message", {}).get("content", "")
    except Exception:
        return None


def _strip_think(text: str) -> str:
    """Remove <think>...</think> tags from model output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)


def _parse_response(text: str) -> str:
    """Extract type from model JSON response."""
    try:
        clean = _strip_think(text)
        m = re.search(r"\{[^}]+\}", clean)
        if not m:
            return "general"
        data = json.loads(m.group())
        t = data.get("type", "general").lower().strip()
        return t if t in KNOWN_TYPES else "general"
    except (json.JSONDecodeError, AttributeError):
        return "general"


def _parse_blast(text: str) -> int | None:
    """Extract blast score from model JSON response."""
    try:
        clean = _strip_think(text)
        m = re.search(r"\{[^}]+\}", clean)
        if not m:
            return None
        data = json.loads(m.group())
        score = int(data.get("blast", 0))
        return max(1, min(10, score))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


async def classify_intent(message: str) -> str:
    """Classify intent via local Ollama model.

    Falls back to keyword matching if Ollama is down.
    """
    text = await _ollama_call(_TYPE_PROMPT.format(message=message))
    if text is not None:
        return _parse_response(text)
    logger.debug("Ollama unavailable, using keyword fallback")
    from maggy.services.chat_router import estimate_type
    return estimate_type(message)


async def classify_blast(message: str) -> int:
    """Estimate blast score (1-10) via local Ollama model.

    Falls back to keyword-based estimation if Ollama is down.
    """
    text = await _ollama_call(_BLAST_PROMPT.format(message=message))
    if text is not None:
        score = _parse_blast(text)
        if score is not None:
            return score
    logger.debug("Ollama blast unavailable, using keyword fallback")
    from maggy.services.chat_router import estimate_blast
    return estimate_blast(message)
