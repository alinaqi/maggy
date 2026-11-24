"""Publish a candidate: push maggy/<ref> and open or update its draft PR (RFC §2.4, §2.6.3/5).

Each external action is fenced (STOP + live lease), preceded by an intent annotation keyed
`<ref>:<attempt>:<action>:<sha>` and followed by a `<key>:result` annotation. Re-runs and
crash recovery reconcile from external state: a remote already at the SHA is not re-pushed,
and the PR is found by its stable head branch and edited rather than created again.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from maggy.runner.awg_client import AwgClient
from maggy.runner.awg_types import Claim, annotation_key
from maggy.runner.publish_body import pr_title, render_body
from maggy.runner.publish_gh import GhCli, PrRequest
from maggy.runner.publish_settle import settle_intents
from maggy.runner.publish_git import (PublishError, branch_for, default_base, push_branch,
                                      remote_sha)
from maggy.runner.session import verify_live
from maggy.worker.models import WorkerResult


@dataclass(frozen=True)
class PublishConfig:
    repo: Path
    state_dir: Path
    base: str = "main"


class Publisher:
    """The runner's PR step: `Publisher(awg, config)(claim, result)` -> {push, pr} outcomes."""

    def __init__(self, awg: AwgClient, config: PublishConfig) -> None:
        self.awg, self.config, self.gh = awg, config, GhCli(config.repo)

    def __call__(self, claim: Claim, result: WorkerResult) -> dict:
        sha = result.candidate_commit
        if not sha:
            raise PublishError("no candidate commit to publish")
        push = self._step(claim, ("push", sha), lambda: self._push(claim, sha))
        pr = self._step(claim, ("pr", sha), lambda: self._pr(claim, result))
        return {"push": push, "pr": pr}

    def settle(self, claim: Claim) -> list[str]:
        """Record results for intents a crashed runner left dangling (crash recovery)."""
        return settle_intents(self, claim)

    def _step(self, claim: Claim, what: tuple[str, str], perform: Callable[[], dict]) -> dict:
        action, sha = what
        key = f"{claim.ref}:{claim.attempt_id}:{action}:{sha}"
        verify_live(self.awg, claim, self.config.state_dir)
        self.awg.annotate(claim, key, {"phase": "intent", "action": action, "sha": sha})
        outcome = perform()
        record = {"phase": "result", "action": action, "sha": sha, **outcome}
        self.awg.annotate(claim, f"{key}:result", record)
        return outcome

    def _push(self, claim: Claim, sha: str) -> dict:
        branch = branch_for(claim.ref)
        remote = remote_sha(self.config.repo, branch)
        if remote == sha:
            return {"pushed": False, "sha": sha}
        expected = expected_remote(self.awg.annotations(claim.ref), claim.ref, remote)
        push_branch(self.config.repo, branch, (sha, expected))
        return {"pushed": True, "sha": sha}

    def _pr(self, claim: Claim, result: WorkerResult) -> dict:
        body = self._body_file(claim, result)
        request = PrRequest(branch_for(claim.ref), self.config.base, pr_title(claim), body)
        existing = self.gh.find(request.head)
        action = "edited" if existing else "created"
        if existing:
            self.gh.edit(int(existing["number"]), body)
        else:
            self.gh.create(request)
            existing = self.gh.find(request.head) or {}
        return {"action": action, "number": existing.get("number"), "url": existing.get("url")}

    def _body_file(self, claim: Claim, result: WorkerResult) -> Path:
        path = self.config.state_dir / "attempts" / claim.attempt_id / "pr-body.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_body(claim, result))
        return path


def expected_remote(annotations: list[dict], ref: str, remote: str) -> str:
    """The lease value: `remote` when it is absent or a SHA we pushed (or meant to), else
    our last known SHA, so a remote that moved unexpectedly makes the push fail."""
    known = [a.get("data", {}).get("sha", "") for a in annotations
             if annotation_key(a).startswith(f"{ref}:") and a.get("data", {}).get("action") == "push"]
    if not remote or remote in known:
        return remote
    return known[-1] if known else ""


def publisher_for(awg: AwgClient, repo: Path, state_dir: Path) -> Publisher:
    """The Publisher for `repo`, targeting origin's default branch."""
    return Publisher(awg, PublishConfig(repo=repo, state_dir=state_dir, base=default_base(repo)))
