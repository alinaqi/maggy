"""Idempotent draft PR through `gh`: lookup by stable head, create once, then edit (RFC §2.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.publish_gh import GhCli
from maggy.runner.publish_git import PublishError
from runner_publish_helpers import candidate, make_rig, reclaim, result_for


def test_first_run_creates_a_draft_pr(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    sha = candidate(rig.repo, rig.claim.ref, "one")
    outcome = rig.publisher(rig.claim, result_for(sha))
    head = f"maggy/{rig.claim.ref}"
    lookup, create, relookup = rig.gh.calls()
    assert relookup == lookup
    assert lookup[:2] == ["pr", "list"] and lookup[lookup.index("--head") + 1] == head
    assert "number,url,isDraft,state" in lookup
    assert create[:3] == ["pr", "create", "--draft"]
    [pr] = rig.gh.prs()
    assert pr["isDraft"] and pr["head"] == head and pr["base"] == "main"
    assert rig.claim.ref in pr["title"]
    assert outcome["pr"] == {"action": "created", "number": 1, "url": pr["url"]}


def test_rerun_same_attempt_edits_instead_of_duplicating(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    sha = candidate(rig.repo, rig.claim.ref, "one")
    rig.publisher(rig.claim, result_for(sha))
    outcome = rig.publisher(rig.claim, result_for(sha))
    assert rig.gh.creates() == 1 and len(rig.gh.prs()) == 1
    assert rig.gh.calls()[-1][:3] == ["pr", "edit", "1"]
    assert outcome["pr"]["action"] == "edited"


def test_new_attempt_updates_body_of_existing_pr(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    first = candidate(rig.repo, rig.claim.ref, "one")
    rig.publisher(rig.claim, result_for(first))
    second = candidate(rig.repo, rig.claim.ref, "two")
    rig.publisher(reclaim(rig), result_for(second))
    [pr] = rig.gh.prs()
    assert rig.gh.creates() == 1
    assert second in pr["body"] and first not in pr["body"]


def test_never_merges_or_marks_ready(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    for text in ("one", "two"):
        rig.publisher(rig.claim, result_for(candidate(rig.repo, rig.claim.ref, text)))
    assert {tuple(argv[:2]) for argv in rig.gh.calls()} <= {
        ("pr", "list"), ("pr", "create"), ("pr", "edit")}
    flat = [arg for argv in rig.gh.calls() for arg in argv]
    assert not {"merge", "ready", "--ready"} & set(flat)
    for forbidden in (["pr", "merge", "1"], ["pr", "ready", "1"], ["api", "x"]):
        with pytest.raises(PublishError, match="refusing"):
            GhCli(rig.repo).run(forbidden)


def test_body_has_summary_ref_sha_and_checks_table(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    sha = candidate(rig.repo, rig.claim.ref, "one")
    rig.publisher(rig.claim, result_for(sha))
    body = rig.gh.prs()[0]["body"]
    assert "## Summary" in body and rig.claim.ref in body and sha in body
    assert "| Check | Result | SHA |" in body
    assert f"| test | PASS | `{sha}` |" in body


def test_gh_gets_no_awg_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AWG_TOKEN", "awg_secret_never_to_gh")
    rig = make_rig(tmp_path, monkeypatch)
    rig.publisher(rig.claim, result_for(candidate(rig.repo, rig.claim.ref, "one")))
    log = (rig.gh.root / "gh_calls.jsonl").read_text()
    assert "awg_secret_never_to_gh" not in log
