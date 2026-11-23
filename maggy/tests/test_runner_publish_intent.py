"""Intent then action then result annotations; crash recovery without duplicates (RFC §2.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.awg_fake import FakeAwg
from maggy.runner.awg_types import Claim
from runner_publish_helpers import FakeGh, candidate, make_rig, reclaim, remote_head, result_for


class WatchingAwg(FakeAwg):
    """Records, per annotation key, the remote head and PR count at that moment."""

    remote: Path
    gh: FakeGh
    seen: list[tuple[str, str, int]]

    def annotate(self, claim: Claim, key: str, data: dict) -> dict:
        self.seen.append((key, remote_head(self.remote, claim.ref), self.gh.creates()))
        return super().annotate(claim, key, data)


class CrashingAwg(FakeAwg):
    """Dies once right after the PR was created, before its result is recorded."""

    crashed = False

    def annotate(self, claim: Claim, key: str, data: dict) -> dict:
        if key.endswith(":result") and ":pr:" in key and not self.crashed:
            self.crashed = True
            raise RuntimeError("runner crashed")
        return super().annotate(claim, key, data)


def test_intent_is_recorded_before_each_action(tmp_path: Path, monkeypatch) -> None:
    awg = WatchingAwg(lease_seconds=900)
    awg.seen = []
    rig = make_rig(tmp_path, monkeypatch, awg=awg)
    awg.remote, awg.gh = rig.remote, rig.gh
    sha = candidate(rig.repo, rig.claim.ref, "one")
    rig.publisher(rig.claim, result_for(sha))
    key = f"{rig.claim.ref}:{rig.claim.attempt_id}"
    assert awg.seen == [(f"{key}:push:{sha}", "", 0), (f"{key}:push:{sha}:result", sha, 0),
                        (f"{key}:pr:{sha}", sha, 0), (f"{key}:pr:{sha}:result", sha, 1)]
    data = {a["key"]: a["data"] for a in rig.awg.annotations(rig.claim.ref)}
    assert data[f"{key}:push:{sha}"]["phase"] == "intent"
    assert data[f"{key}:pr:{sha}:result"]["number"] == 1


def test_crash_between_intent_and_result_reconciles(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch, awg=CrashingAwg(lease_seconds=900))
    sha = candidate(rig.repo, rig.claim.ref, "one")
    with pytest.raises(RuntimeError, match="crashed"):
        rig.publisher(rig.claim, result_for(sha))
    assert rig.gh.creates() == 1
    outcome = rig.publisher(reclaim(rig), result_for(sha))
    assert rig.gh.creates() == 1 and len(rig.gh.prs()) == 1
    assert outcome == {"push": {"pushed": False, "sha": sha},
                       "pr": {"action": "edited", "number": 1, "url": rig.gh.prs()[0]["url"]}}
    keys = [a["key"] for a in rig.awg.annotations(rig.claim.ref)]
    assert f"{rig.claim.ref}:{rig.claim.attempt_id}:pr:{sha}:result" in keys


def test_repeated_intent_key_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    sha = candidate(rig.repo, rig.claim.ref, "one")
    rig.publisher(rig.claim, result_for(sha))
    rig.publisher(rig.claim, result_for(sha))
    keys = [a["key"] for a in rig.awg.annotations(rig.claim.ref)]
    assert len(keys) == len(set(keys)) == 4
