"""Stable-branch push: only maggy/*, force-with-lease, fenced (RFC §2.4, §2.6.3, §2.6.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.awg_errors import FenceStale, LeaseLost
from maggy.runner.awg_fake import FakeAwg
from maggy.runner.awg_types import Claim
from maggy.runner.publish import PublishConfig, publisher_for
from maggy.runner.publish_git import PublishError, branch_for, push_branch
from runner_publish_helpers import candidate, make_rig, reclaim, remote_head, result_for
from worker_git_helpers import git


class StaleAwg(FakeAwg):
    def heartbeat(self, claim: Claim) -> Claim:
        raise FenceStale("stale_fencing_token", "fencing token is not the live lease")


def test_pushes_candidate_only_to_its_maggy_branch(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    sha = candidate(rig.repo, rig.claim.ref, "one")
    rig.publisher(rig.claim, result_for(sha))
    assert remote_head(rig.remote, rig.claim.ref) == sha
    refs = git(rig.remote, "for-each-ref", "--format=%(refname)").splitlines()
    assert refs == [f"refs/heads/maggy/{rig.claim.ref}"]


def test_non_maggy_branches_are_refused(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    sha = git(rig.repo, "rev-parse", "HEAD")
    for branch in ("main", "refs/heads/main", "maggy", "maggy/../main", "maggy/a:main"):
        with pytest.raises(PublishError, match="refusing"):
            push_branch(rig.repo, branch, (sha, ""))
    with pytest.raises(Exception, match="unsafe"):
        branch_for("../main")
    assert git(rig.remote, "for-each-ref") == ""


def test_force_with_lease_rejects_unexpectedly_moved_remote(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    first = candidate(rig.repo, rig.claim.ref, "one")
    rig.publisher(rig.claim, result_for(first))
    intruder = candidate(rig.repo, "intruder", "someone else")
    git(rig.repo, "push", "-q", "-f", "origin", f"maggy/intruder:maggy/{rig.claim.ref}")
    second = candidate(rig.repo, rig.claim.ref, "two")
    with pytest.raises(PublishError, match="push"):
        rig.publisher(reclaim(rig), result_for(second))
    assert remote_head(rig.remote, rig.claim.ref) == intruder
    assert rig.gh.creates() == 1, "no PR step after a rejected push"


def test_lease_check_with_explicit_expectation(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    sha = candidate(rig.repo, rig.claim.ref, "one")
    branch = branch_for(rig.claim.ref)
    with pytest.raises(PublishError, match="push"):
        push_branch(rig.repo, branch, (sha, sha))  # expects it there, but it is absent
    push_branch(rig.repo, branch, (sha, ""))
    assert remote_head(rig.remote, rig.claim.ref) == sha


def test_rerun_with_same_sha_is_a_no_op_push(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    sha = candidate(rig.repo, rig.claim.ref, "one")
    rig.publisher(rig.claim, result_for(sha))
    outcome = rig.publisher(reclaim(rig), result_for(sha))
    assert outcome["push"]["pushed"] is False
    assert remote_head(rig.remote, rig.claim.ref) == sha


def test_stale_fence_skips_push_pr_and_intent(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch, awg=StaleAwg(lease_seconds=900))
    sha = candidate(rig.repo, rig.claim.ref, "one")
    with pytest.raises(LeaseLost):
        rig.publisher(rig.claim, result_for(sha))
    assert remote_head(rig.remote, rig.claim.ref) == ""
    assert rig.gh.calls() == [] and rig.awg.annotations(rig.claim.ref) == []


def test_publisher_for_uses_the_remote_default_branch(tmp_path: Path, monkeypatch) -> None:
    rig = make_rig(tmp_path, monkeypatch)
    git(rig.remote, "symbolic-ref", "HEAD", "refs/heads/trunk")
    git(rig.repo, "push", "-q", "origin", "main:trunk")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(rig.remote), str(clone))
    assert publisher_for(rig.awg, clone, tmp_path / "s").config.base == "trunk"
    assert publisher_for(rig.awg, rig.repo, tmp_path / "s").config == PublishConfig(
        repo=rig.repo, state_dir=tmp_path / "s", base="main")
