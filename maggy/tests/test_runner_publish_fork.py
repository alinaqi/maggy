"""A fork PR whose branch is also named maggy/<ref> is never adopted (RFC §2.4)."""

from __future__ import annotations

import json
from pathlib import Path

from runner_publish_helpers import candidate, make_rig, result_for

FORK = {"number": 1, "url": "https://example.invalid/pr/1", "isDraft": False, "state": "OPEN",
        "head": "", "base": "main", "title": "attacker", "body": "attacker body",
        "isCrossRepository": True, "headRepositoryOwner": {"login": "attacker"}}


def test_fork_pr_with_same_branch_name_is_ignored(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    head = f"maggy/{rig.claim.ref}"
    (rig.gh.root / "prs.json").write_text(json.dumps([{**FORK, "head": head}]))
    sha = candidate(rig.repo, rig.claim.ref, "one")
    outcome = rig.publisher(rig.claim, result_for(sha))
    fork, ours = rig.gh.prs()
    assert fork["body"] == "attacker body", "the fork PR was edited"
    assert rig.gh.creates() == 1 and ours["isDraft"] and not ours["isCrossRepository"]
    assert outcome["pr"] == {"action": "created", "number": 2, "url": ours["url"]}
    lookup = rig.gh.calls()[0]
    assert "isCrossRepository" in lookup[lookup.index("--json") + 1]


def test_settle_never_records_a_fork_pr(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    head = f"maggy/{rig.claim.ref}"
    (rig.gh.root / "prs.json").write_text(json.dumps([{**FORK, "head": head}]))
    assert rig.publisher.gh.find(head) is None
