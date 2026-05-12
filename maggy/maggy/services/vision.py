"""Vision analysis via Ollama Qwen3-VL — screenshot review."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Generator

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
VISION_MODEL = "qwen3-vl:32b"
_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
})
_DEFAULT_PROMPT = (
    "Analyze this screenshot. Describe what you see, "
    "identify any UI issues, and suggest improvements."
)


def _validate(path: str) -> Path | None:
    """Check file exists and is an image."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return None
    if p.suffix.lower() not in _IMAGE_EXTS:
        return None
    return p


def _encode(path: Path) -> str:
    """Base64-encode an image file."""
    return base64.b64encode(path.read_bytes()).decode()


def analyze_image(
    path: str,
    prompt: str | None = None,
) -> Generator[dict, None, None]:
    """Stream vision analysis from Ollama Qwen3-VL.

    Yields dicts: {type: text|error|done, content: ...}
    """
    resolved = _validate(path)
    if resolved is None:
        yield _err(f"Invalid image: {path}")
        return
    img_b64 = _encode(resolved)
    body = {
        "model": VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": prompt or _DEFAULT_PROMPT,
            "images": [img_b64],
        }],
        "stream": True,
    }
    try:
        with httpx.stream(
            "POST", f"{OLLAMA_URL}/api/chat",
            json=body, timeout=120.0,
        ) as resp:
            for line in resp.iter_lines():
                chunk = json.loads(line)
                if chunk.get("done"):
                    break
                text = chunk.get("message", {}).get(
                    "content", "",
                )
                if text:
                    yield {"type": "text", "content": text}
    except httpx.ConnectError as e:
        yield _err(f"Cannot connect to Ollama: {e}")
        return
    except Exception as e:
        yield _err(str(e))
        return
    yield {"type": "done"}


def _err(msg: str) -> dict:
    return {"type": "error", "content": msg}
