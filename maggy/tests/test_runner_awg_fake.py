"""FakeAwg contract: capability claims, lease expiry, fencing, versions."""

from __future__ import annotations

import pytest

from maggy.runner.awg_client import AwgClient, Claim, FenceStale, LeaseLost
from maggy.runner.awg_fake import FakeAwg
from tests.runner_awg_helpers import Clock, fake_awg


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def awg(clock: Clock) -> FakeAwg:
    return fake_awg(clock)


def test_claims_only_capable_items(clock: Clock) -> None:
    fake = FakeAwg(clock=clock)
    fake.add_item("Approve plan", capabilities=["human"])
    assert fake.next_claim(["maggy-runner"]) is None
    ref = fake.add_item("Build", capabilities=["maggy-runner", "stage:build"])
    claim = fake.next_claim(["maggy-runner", "stage:build"])
    assert claim.ref == ref and claim.title == "Build"
    assert fake.next_claim(["maggy-runner", "stage:build"]) is None
    assert isinstance(fake, AwgClient)


def test_claim_bumps_fence_and_version(awg: FakeAwg, clock: Clock) -> None:
    first = awg.next_claim(["maggy-runner"])
    assert first.acceptance_criteria == ["works"] and first.lease_expires == 1060.0
    clock.now += 61
    second = awg.next_claim(["maggy-runner"])
    assert second.fencing_token == first.fencing_token + 1
    assert second.version > first.version and second.attempt_id != first.attempt_id


def test_lease_expiry_loses_the_lease(awg: FakeAwg, clock: Clock) -> None:
    claim = awg.next_claim(["maggy-runner"])
    clock.now += 50
    renewed = awg.heartbeat(claim)
    assert renewed.lease_expires == 1110.0
    clock.now += 61
    with pytest.raises(LeaseLost):
        awg.heartbeat(claim)
    with pytest.raises(LeaseLost):
        awg.submit(claim, "late", "abc")


def test_reclaimed_item_fences_out_the_old_attempt(awg: FakeAwg, clock: Clock) -> None:
    old = awg.next_claim(["maggy-runner"])
    clock.now += 61
    new = awg.next_claim(["maggy-runner"])
    with pytest.raises(FenceStale):
        awg.submit(old, "stale", "abc")
    forged = Claim(**{**new.model_dump(), "fencing_token": new.fencing_token + 5})
    with pytest.raises(FenceStale):
        awg.heartbeat(forged)
    awg.submit(new, "done", "def")
    assert awg.show(new.ref)["work"]["state"] == "VERIFYING"
