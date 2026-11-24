"""The local vision backend: Ollama Qwen-VL (`services/vision.py`), reference + candidate.

Nothing leaves the machine. Unreachable Ollama or a missing model is `available() == False`;
an unparseable answer is `uncertain`, so it routes to a human rather than passing.
"""

from __future__ import annotations

import base64
import json

import httpx
from pydantic import ValidationError

from maggy.runner.verify.vision import LOCAL, VisionRequest, VisionVerdict
from maggy.services.vision import OLLAMA_URL, VISION_MODEL

PROMPT = ("You review a UI screenshot against one acceptance criterion at viewport {viewport}."
          "\nCriterion {cid}: {text}\nThe first image is the approved reference, the second "
          "the candidate. Reply with JSON only: {{\"verdict\": \"pass\"|\"fail\"|\"uncertain\", "
          "\"region\": \"<affected area>\", \"evidence\": \"<what is visible>\"}}. Use "
          "uncertain when you cannot tell.")


class OllamaVision:
    provider = LOCAL

    def __init__(self, url: str = OLLAMA_URL, model: str = VISION_MODEL,
                 timeout_s: float = 120.0) -> None:
        self.url, self.model, self.timeout_s = url.rstrip("/"), model, timeout_s
        self.name = f"ollama:{model}"

    def available(self) -> bool:
        try:
            tags = httpx.get(f"{self.url}/api/tags", timeout=2.0).json()
        except (httpx.HTTPError, ValueError):
            return False
        return any(m.get("name") == self.model for m in tags.get("models") or [])

    def review(self, request: VisionRequest) -> VisionVerdict:
        try:
            reply = httpx.post(f"{self.url}/api/chat", json=self._body(request),
                               timeout=self.timeout_s).json()
            return VisionVerdict.model_validate(json.loads(reply["message"]["content"]))
        except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as exc:
            return VisionVerdict(verdict="uncertain", evidence=f"no usable answer: {exc}"[:500])

    def _body(self, request: VisionRequest) -> dict:
        images = [p for p in (request.reference, request.candidate) if p is not None]
        prompt = PROMPT.format(viewport=request.viewport, cid=request.criterion_id,
                               text=request.criterion_text)
        return {"model": self.model, "stream": False, "format": "json",
                "messages": [{"role": "user", "content": prompt,
                              "images": [base64.b64encode(p.read_bytes()).decode()
                                         for p in images]}]}
