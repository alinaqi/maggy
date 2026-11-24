"""Vision reviewer (RFC §2.5 Verify, §2.6.9; factory doc §5 agent-assisted visual review).

A backend gets the approved criterion text, the reference and candidate images and the
viewport, and returns {pass|fail|uncertain, region, evidence}. Local backends (Ollama
Qwen-VL) are always allowed; an external one only when the personal profile's
`evidence.external_review` lists its provider. `uncertain`, an unavailable backend or none
at all is PENDING (a human decides), never PASS.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from maggy.harness.schema import HarnessProfile

LOCAL = "local"
GATE = {"pass": "PASS", "fail": "FAIL", "uncertain": "PENDING"}


class VisionVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verdict: Literal["pass", "fail", "uncertain"]
    region: str = Field("", max_length=500)
    evidence: str = Field("", max_length=2000)


@dataclass(frozen=True)
class VisionRequest:
    criterion_id: str
    criterion_text: str
    reference: Path | None
    candidate: Path
    viewport: str


class VisionBackend(Protocol):
    name: str
    provider: str  # "local", or the external provider evidence would be sent to

    def available(self) -> bool: ...

    def review(self, request: VisionRequest) -> VisionVerdict: ...


@dataclass(frozen=True)
class VisionOutcome:
    verdict: Literal["PASS", "FAIL", "PENDING"]
    detail: str
    backend: str | None = None


def review_criterion(backends: Sequence[VisionBackend], profile: HarnessProfile,
                     request: VisionRequest) -> VisionOutcome:
    refused = [b for b in backends if not allowed(b, profile)]
    usable = [b for b in backends if allowed(b, profile) and b.available()]
    if not usable:
        return VisionOutcome("PENDING", _why_none(refused))
    backend = usable[0]
    answer = backend.review(request)
    detail = f"{backend.name}: {answer.verdict} ({answer.region}): {answer.evidence}"
    return VisionOutcome(GATE[answer.verdict], detail, backend.name)


def allowed(backend: VisionBackend, profile: HarnessProfile) -> bool:
    """Local backends always; external ones only when opted in per provider."""
    opted = profile.evidence.external_review or []
    return backend.provider == LOCAL or backend.provider in opted


def _why_none(refused: list[VisionBackend]) -> str:
    detail = "no vision backend available; a human reviews this criterion"
    if refused:
        names = ", ".join(sorted({b.provider for b in refused}))
        detail += (f" (external provider(s) {names} refused: not listed in the personal "
                   "profile's evidence.external_review)")
    return detail
