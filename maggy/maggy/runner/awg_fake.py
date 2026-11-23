"""FakeAwg: the AwgClient protocol in memory, for runner unit tests.

Mirrors AWG Local: capability-filtered claims, leases that expire, fencing tokens bumped per
claim, versions, idempotent keyed annotations, and evidence trust taken from the credential
(agent=1, ci=3) rather than from the caller.
"""

from __future__ import annotations

from maggy.runner.awg_fake_state import FakeAwgState
from maggy.runner.awg_types import TRUST, Claim, EvidenceSpec


class FakeAwg(FakeAwgState):
    def next_claim(self, capabilities: list[str]) -> Claim | None:
        for item in self.items.values():
            if self._claimable(item, capabilities):
                return self._grant(item)
        return None

    def heartbeat(self, claim: Claim) -> Claim:
        item = self._live(claim)
        item.lease_expires = self.clock() + self.lease_seconds
        return claim.model_copy(update={"lease_expires": item.lease_expires})

    def submit(self, claim: Claim, summary: str, sha: str) -> dict:
        item = self._live(claim)
        item.revision_sha = sha
        return self._end(item, "VERIFYING")

    def release(self, claim: Claim, reason: str) -> dict:
        return self._end(self._live(claim), "READY")

    def block(self, claim: Claim, question: str, human: bool = True) -> dict:
        item = self._live(claim)
        item.comments.append({"body": question})
        return self._end(item, "WAITING_HUMAN" if human else "BLOCKED")

    def handoff(self, claim: Claim, text: str) -> dict:
        comment = {"body": f"[handoff {claim.attempt_id}] {text}"}
        self._item(claim.ref).comments.append(comment)
        return comment

    def annotate(self, claim: Claim, key: str, data: dict) -> dict:
        item = self._item(claim.ref)
        found = next((a for a in item.annotations if a["key"] == key), None)
        if found is None:
            found = {"key": key, "data": dict(data), "attempt_id": claim.attempt_id}
            item.annotations.append(found)
        return dict(found)

    def annotations(self, ref: str) -> list[dict]:
        return [dict(a) for a in self._item(ref).annotations]

    def evidence(self, claim: Claim, spec: EvidenceSpec) -> dict:
        record = {**spec.model_dump(), "trust_class": TRUST[self.evidence_credential],
                  "producer": self.evidence_credential}
        self._item(claim.ref).evidence.append(record)
        return dict(record)

    def show(self, ref: str) -> dict:
        item = self._item(ref)
        work = {"display_id": item.ref, "state": item.state, "version": item.version,
                "acceptance_criteria": list(item.acceptance_criteria),
                "revision_sha": item.revision_sha, "attributes": dict(item.attributes),
                "execution_policy": {"capabilities": sorted(item.capabilities)}}
        return {"work": work, "comments": list(item.comments),
                "annotations": self.annotations(ref), "evidence": list(item.evidence)}
