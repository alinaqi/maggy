"""Phase 5 exit: the factory doc's coupon scenario end to end against the REAL awg CLI and
real browsers: ticket -> ONE question -> answer -> AC1-AC3 approved -> T1-T3 plan with
VALIDATIONs -> builds proven RED on base / GREEN on the candidate -> verify (AC1/AC2 browser
checks, AC3 visual at 390x844 + 1440x900: baseline PENDING, human approval, rerun passes,
vision reviewer) -> draft PR with the per-criterion evidence table -> CI-trust proof.

Skips (with the reason) when no awg CLI with the runner flags or no browser is available.
Set MAGGY_COUPON_RECORD=<dir> to keep the PR body and `awg proof --json` output.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from coupon_helpers import ANSWER, CRITERIA, QUESTION, TESTS, TICKET, coupon_plan, spec_draft
from coupon_rig import FakeCouncil, approve_baselines, caps, prepare, run_once, verify_once
from runner_exit_helpers import ExitRig, find_awg, make_exit_rig
from runner_phase4_helpers import comment_bodies, install_agents, shown
from runner_spec_helpers import fenced, review
from verify_helpers import FakeVision, browser  # noqa: F401 - the skip-or-run fixture

from maggy.harness.cli.awg_tokens import ensure_awg
from maggy.harness.cli.env import ToolEnv

AWG_BIN, SKIP_REASON = find_awg()
pytestmark = pytest.mark.skipif(AWG_BIN is None, reason=f"real awg unavailable: {SKIP_REASON}")


@pytest.fixture
def rig(tmp_path: Path, monkeypatch, browser) -> ExitRig:
    rig, env = make_exit_rig(tmp_path, AWG_BIN)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AWG_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    assert not ensure_awg(ToolEnv(home=rig.home), [])[1]
    prepare(rig)
    return rig


def _intake(rig: ExitRig) -> str:
    stamp = "2026-11-01T00:00:00Z"
    rig.gh.issues([{"node_id": "I_12", "number": 12, "title": TICKET, "state": "open",
                    "html_url": "https://example.invalid/acme/shop/issues/12",
                    "body": f"{TICKET}.", "assignees": [], "labels": [{"name": "factory"}],
                    "user": {"login": "me"}, "created_at": stamp, "updated_at": stamp}])
    done = rig.maggy("run", "intake", "--repo", "acme/shop", "--label", "factory",
                     "--awg-bin", str(rig.awg_bin), "--checkout", str(rig.repo))
    assert done.returncode == 0, done.stderr
    [item] = rig.awg("list", "--json")["items"]
    return str(item["display_id"])


def _spec(rig: ExitRig, ref: str, agents: tuple) -> None:
    author, reviewer = agents
    author.queue([fenced(spec_draft(False)), fenced(spec_draft(True))])
    reviewer.queue([fenced(review("needs_clarification", QUESTION)), fenced(review("ready"))])
    assert run_once(rig)[:2] == ["waiting_human", ref]
    assert [b for b in comment_bodies(rig, ref) if "?" in b] == [QUESTION]
    rig.awg("comment", ref, ANSWER, "--json")
    rig.awg("state", ref, "READY", "--reason=answered", "--json")
    assert run_once(rig)[:2] == ["spec_approved", ref]
    assert ANSWER in author.prompts()[-1]
    work = shown(rig, ref)["work"]
    assert work["acceptance_criteria"] == [f"[{cid}] {text}" for cid, text in CRITERIA.items()]


def _plan(rig: ExitRig, ref: str, author) -> list[str]:
    author.queue([fenced(coupon_plan())])
    assert run_once(rig)[:2] == ["planned", ref]
    titles = [t["title"] for t in coupon_plan()["tasks"]]
    items = {i["title"]: i for i in rig.awg("list", "--json")["items"]}
    children = [str(items[title]["display_id"]) for title in titles]
    for child, cid in zip(children, TESTS, strict=True):
        validations = rig.awg("proof", child, "--json")["validations"]
        assert any(v["title"].startswith(f"[{cid}] {TESTS[cid]}") for v in validations)
    return children


def _build(rig: ExitRig, ref: str, children: list[str]) -> None:
    """Each child's planned regression test is proven RED on base and GREEN on its
    candidate: only then is the CI-trust PASS on its `[AC] test` validation attached."""
    for child, cid in zip(children, TESTS, strict=True):
        outcome, built, sha = run_once(rig)
        assert (outcome, built) == ("submitted", child), (outcome, built)
        proof = rig.awg("proof", child, "--json", token="runner-agent")
        [planned] = [v for v in proof["validations"]
                     if v["title"].startswith(f"[{cid}] {TESTS[cid]}:")]
        assert planned["status"] == "PASS", planned
        assert [(e["trust_class"], e["commit_sha"]) for e in planned["evidence"]] == [(3, sha)]
    assert "stage:verify" in caps(rig, ref)


def _verify(rig: ExitRig, ref: str) -> str:
    vision, council = FakeVision("pass"), FakeCouncil()
    first = verify_once(rig, ([vision], council))
    assert first.outcome == "waiting_human", first
    assert shown(rig, ref)["work"]["state"] == "WAITING_HUMAN" and not vision.calls
    assert approve_baselines(rig, ref) == ["baseline-approved:AC3:desktop",
                                           "baseline-approved:AC3:mobile"]
    second = verify_once(rig, ([vision], council))
    assert second.outcome == "submitted", second
    assert sorted(c.viewport for c in vision.calls) == ["desktop", "mobile"]
    assert council.requests[-1].criteria == tuple(shown(rig, ref)["work"]["acceptance_criteria"])
    return second.detail


def _pr_body(rig: ExitRig, ref: str, sha: str) -> str:
    [pr] = [p for p in rig.gh.prs() if p["head"] == f"maggy/{ref}"]
    body = pr["body"]
    assert pr["isDraft"] and f"- Tested commit: `{sha}`" in body
    for cid in CRITERIA:
        assert f"| {cid} | passed |" in body, body
    assert "| Release impact | - | - | - | No high-risk paths" in body and "Gate: open" in body
    return body


def _proof(rig: ExitRig, ref: str, sha: str) -> None:
    proof = rig.awg("proof", ref, "--json", token="runner-agent")
    assert proof["work"]["revision_sha"] == sha and proof["validations"]
    assert (proof["verdict"], proof["work"]["state"]) == ("PASS", "DONE")
    for validation in proof["validations"]:
        ci = [e for e in validation["evidence"] if e["trust_class"] == 3
              and e["commit_sha"] == sha and e["verdict"] == "PASS"]
        assert ci, validation


def _record(rig: ExitRig, body: str, refs: list[str]) -> None:
    """With MAGGY_COUPON_RECORD: the PR body and `awg proof --json` of parent + children."""
    out = os.environ.get("MAGGY_COUPON_RECORD")
    if out:
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "pr-body.md").write_text(body)
        proofs = {ref: rig.awg("proof", ref, "--json", token="runner-agent") for ref in refs}
        (Path(out) / "proof.json").write_text(json.dumps(proofs, indent=2))


def test_coupon_ticket_runs_end_to_end(rig: ExitRig) -> None:
    agents = install_agents(rig)
    ref = _intake(rig)
    _spec(rig, ref, agents)
    children = _plan(rig, ref, agents[0])
    _build(rig, ref, children)
    sha = _verify(rig, ref)
    body = _pr_body(rig, ref, sha)
    _proof(rig, ref, sha)
    _record(rig, body, [ref, *children])
