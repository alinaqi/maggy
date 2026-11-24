"""FakeAwg contract: idempotent annotations, evidence trust, release/block/handoff."""

from __future__ import annotations

import pytest

from maggy.runner.awg_client import EvidenceSpec, LeaseLost, NotFound
from maggy.runner.awg_fake import FakeAwg
from tests.runner_awg_helpers import Clock, fake_awg


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def awg(clock: Clock) -> FakeAwg:
    return fake_awg(clock)


def test_annotate_is_idempotent_by_key(awg: FakeAwg) -> None:
    claim = awg.next_claim(["maggy-runner"])
    first = awg.annotate(claim, "pr-intent", {"branch": "maggy/AWG-1"})
    again = awg.annotate(claim, "pr-intent", {"branch": "other"})
    awg.annotate(claim, "pr-result", {"pr": 12})
    assert again == first
    keys = [a["idempotency_key"] for a in awg.annotations(claim.ref)]
    assert keys == ["pr-intent", "pr-result"]
    assert awg.annotations(claim.ref)[0]["data"] == {"branch": "maggy/AWG-1"}


def test_evidence_trust_follows_the_credential(clock: Clock) -> None:
    for credential, trust in (("ci", 3), ("agent", 1)):
        fake = FakeAwg(clock=clock, evidence_credential=credential)
        fake.add_item("Build")
        claim = fake.next_claim([])
        spec = EvidenceSpec(kind="test", verdict="PASS", commit_sha="abc",
                            meta={"spec_version": str(claim.version)})
        record = fake.evidence(claim, spec)
        assert record["trust_class"] == trust and record["commit_sha"] == "abc"
        assert fake.show(claim.ref)["evidence"] == [record]


def test_release_block_and_handoff(awg: FakeAwg, clock: Clock) -> None:
    claim = awg.next_claim(["maggy-runner"])
    awg.release(claim, "quota")
    assert awg.show(claim.ref)["work"]["state"] == "READY"
    claim = awg.next_claim(["maggy-runner"])
    awg.handoff(claim, "resume from maggy/AWG-1")
    awg.block(claim, "which db?")
    shown = awg.show(claim.ref)
    assert shown["work"]["state"] == "WAITING_HUMAN"
    assert [c["body"] for c in shown["comments"]] == [
        f"[handoff {claim.attempt_id}] resume from maggy/AWG-1", "which db?"]
    with pytest.raises(LeaseLost):
        awg.heartbeat(claim)


def test_block_without_human_is_blocked(awg: FakeAwg) -> None:
    claim = awg.next_claim(["maggy-runner"])
    awg.block(claim, "flaky infra", human=False)
    assert awg.show(claim.ref)["work"]["state"] == "BLOCKED"


def test_unknown_ref_is_not_found(awg: FakeAwg) -> None:
    with pytest.raises(NotFound):
        awg.show("AWG-404")
