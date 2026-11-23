"""In-memory AWG state for FakeAwg: items, leases with expiry, fencing tokens, versions."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from maggy.runner.awg_errors import FenceStale, LeaseLost, NotFound
from maggy.runner.awg_types import Claim


@dataclass
class FakeItem:
    ref: str
    title: str
    capabilities: frozenset[str]
    acceptance_criteria: list[str]
    state: str = "READY"
    version: int = 1
    fencing_token: int = 0
    attempt_id: str | None = None
    lease_expires: float = 0.0
    revision_sha: str | None = None
    comments: list[dict] = field(default_factory=list)
    annotations: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)


class FakeAwgState:
    def __init__(self, clock: Callable[[], float] = time.time, lease_seconds: int = 900,
                 evidence_credential: str = "ci") -> None:
        self.clock, self.lease_seconds = clock, lease_seconds
        self.evidence_credential = evidence_credential
        self.items: dict[str, FakeItem] = {}
        self._attempts = 0

    def add_item(self, title: str, capabilities: list[str] | tuple = (),
                 acceptance_criteria: list[str] | tuple = ()) -> str:
        ref = f"AWG-{len(self.items) + 1}"
        self.items[ref] = FakeItem(ref, title, frozenset(capabilities), list(acceptance_criteria))
        return ref

    def _item(self, ref: str) -> FakeItem:
        if ref not in self.items:
            raise NotFound("not_found", f"no work item {ref}")
        return self.items[ref]

    def _claimable(self, item: FakeItem, capabilities: list[str]) -> bool:
        lapsed = item.state == "ACTIVE" and item.lease_expires < self.clock()
        return item.capabilities <= set(capabilities) and (item.state == "READY" or lapsed)

    def _grant(self, item: FakeItem) -> Claim:
        self._attempts += 1
        item.state, item.attempt_id = "ACTIVE", f"att-{self._attempts}"
        item.fencing_token, item.version = item.fencing_token + 1, item.version + 1
        item.lease_expires = self.clock() + self.lease_seconds
        return Claim(ref=item.ref, work_id=item.ref, attempt_id=item.attempt_id,
                     fencing_token=item.fencing_token, lease_expires=item.lease_expires,
                     version=item.version, title=item.title,
                     acceptance_criteria=list(item.acceptance_criteria), context=item.title)

    def _live(self, claim: Claim) -> FakeItem:
        """The item only while `claim` is its live, unexpired lease (AWG check_fence)."""
        item = self._item(claim.ref)
        if (item.attempt_id, item.fencing_token) != (claim.attempt_id, claim.fencing_token):
            raise FenceStale("stale_fencing_token", "fencing token is not the live lease")
        if item.state != "ACTIVE" or item.lease_expires < self.clock():
            raise LeaseLost("lease_lost", f"lease on {claim.ref} is gone")
        return item

    def _end(self, item: FakeItem, state: str) -> dict:
        item.state, item.attempt_id, item.version = state, None, item.version + 1
        return {"display_id": item.ref, "state": state}
