"""The AwgClient protocol the runner drives (RFC §2.4); CLI-backed and in-memory fakes implement it.

Lifecycle calls (claim, heartbeat, submit, release, block, handoff, annotate) act with the
runner's `agent` credential; `evidence` alone uses the separate `ci` credential (§2.6.1).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from maggy.runner.awg_errors import (
    AwgError,
    AwgUnavailable,
    FenceStale,
    LeaseLost,
    NotFound,
    Unauthorized,
)
from maggy.runner.awg_types import TRUST, AwgCliConfig, Claim, EvidenceSpec

__all__ = ["TRUST", "AwgCliConfig", "AwgClient", "AwgError", "AwgUnavailable", "Claim",
           "EvidenceSpec", "FenceStale", "LeaseLost", "NotFound", "Unauthorized"]


@runtime_checkable
class AwgClient(Protocol):
    def next_claim(self, capabilities: list[str], require: list[str] | None = None) -> Claim | None:
        """Claim the best ready item whose capabilities we hold and that declares every
        `require` capability (opt-in); None when nothing is ready."""

    def heartbeat(self, claim: Claim) -> Claim:
        """Extend the lease; raises LeaseLost/FenceStale when it is gone."""

    def submit(self, claim: Claim, summary: str, sha: str) -> dict:
        """Finish the attempt at commit `sha`; AWG decides DONE from its contract."""

    def release(self, claim: Claim, reason: str) -> dict:
        """Give the item back to the queue."""

    def block(self, claim: Claim, question: str, human: bool = True) -> dict:
        """WAITING_HUMAN (default) or BLOCKED with the question."""

    def handoff(self, claim: Claim, text: str) -> dict:
        """Leave a resume note for the next attempt."""

    def annotate(self, claim: Claim, key: str, data: dict) -> dict:
        """Record structured data under `key`; a repeated key returns the first record."""

    def annotations(self, ref: str) -> list[dict]:
        """The item's annotations, oldest first."""

    def evidence(self, claim: Claim, spec: EvidenceSpec) -> dict:
        """Attach commit-bound evidence with the ci credential."""

    def show(self, ref: str) -> dict:
        """The item, its state and why."""
