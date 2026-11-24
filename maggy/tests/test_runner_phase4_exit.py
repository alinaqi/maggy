"""Phase 4 exit: an ambiguous ticket through intake -> spec (ONE question, WAITING_HUMAN) ->
human answer -> spec approved -> plan graph with VALIDATIONs -> first child built to a draft
PR with CI-trust evidence, all against the REAL awg CLI with recorded agent replies.

Skips (with the reason) only when no awg CLI with the runner flags is available.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from runner_exit_helpers import ExitRig, find_awg, make_exit_rig
from runner_phase4_helpers import (
    CRITERIA, QUESTION, ambiguous_issue, answer_as_human, build_prompts, children_by_title,
    comment_bodies, install_agents, shown, two_task_plan,
)
from runner_publish_helpers import remote_head
from runner_spec_helpers import draft, fenced, review

from maggy.harness.cli.awg_tokens import ensure_awg
from maggy.harness.cli.env import ToolEnv

AWG_BIN, SKIP_REASON = find_awg()
pytestmark = pytest.mark.skipif(AWG_BIN is None, reason=f"real awg unavailable: {SKIP_REASON}")


@pytest.fixture
def rig(tmp_path: Path, monkeypatch) -> ExitRig:
    rig, env = make_exit_rig(tmp_path, AWG_BIN)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AWG_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    assert not ensure_awg(ToolEnv(home=rig.home), [])[1]
    return rig


def _run_once(rig: ExitRig) -> list[str]:
    done = rig.maggy("run", "--once", "--repo", str(rig.repo), "--awg-bin", str(rig.awg_bin))
    assert done.returncode == 0, done.stderr
    return done.stdout.strip().split("\t")


def _intake(rig: ExitRig) -> str:
    rig.gh.issues([ambiguous_issue(7)])
    done = rig.maggy("run", "intake", "--repo", "acme/shop", "--label", "factory",
                     "--awg-bin", str(rig.awg_bin), "--checkout", str(rig.repo))
    assert done.returncode == 0, done.stderr
    [item] = rig.awg("list", "--json")["items"]
    assert item["execution_policy"]["capabilities"] == [
        "maggy-runner", "stage:spec", "project:repo"]
    return str(item["display_id"])


def _ask_one_question(rig: ExitRig, ref: str, agents: tuple) -> None:
    author, reviewer = agents
    author.queue([fenced(draft("Apply the discount rules"))])
    reviewer.queue([fenced(review("needs_clarification", QUESTION))])
    out = _run_once(rig)
    assert out[:2] == ["waiting_human", ref], out
    assert shown(rig, ref)["work"]["state"] == "WAITING_HUMAN"
    asked = [body for body in comment_bodies(rig, ref) if "?" in body]
    assert asked == [QUESTION], comment_bodies(rig, ref)


def _approve_spec(rig: ExitRig, ref: str, agents: tuple) -> None:
    author, reviewer = agents
    author.queue([fenced(draft(*CRITERIA))])
    reviewer.queue([fenced(review("ready"))])
    out = _run_once(rig)
    assert out[:2] == ["spec_approved", ref], out
    assert any("10% off orders over 100 EUR" in p for p in author.prompts()[-1:])
    work = shown(rig, ref)["work"]
    assert work["acceptance_criteria"] == [f"[AC{n}] {t}" for n, t in enumerate(CRITERIA, 1)]
    assert "stage:plan" in work["execution_policy"]["capabilities"]
    [approval] = [d for d in rig.awg("decisions", ref, "--json")
                  if (d.get("properties") or {}).get("key") == "spec-approved"]
    assert approval["properties"]["data"]["spec_version"] >= 1
    requirements = shown(rig, ref)["context"]["requirements"]
    assert sorted(r["title"] for r in requirements) == sorted(CRITERIA)


def _plan(rig: ExitRig, ref: str, author) -> dict[str, dict]:
    author.queue([fenced(two_task_plan())])
    out = _run_once(rig)
    assert out[:2] == ["planned", ref], out
    children = children_by_title(rig)
    first, second = children["Record the discount rule"], children["Document the rule"]
    assert first["state"] == "READY" and second["state"] == "READY"
    assert "stage:build" in first["execution_policy"]["capabilities"]
    proof = rig.awg("proof", first["display_id"], "--json")
    titles = [v["title"] for v in proof["validations"]]
    assert any(t.startswith("[AC1] test_discount_over_100") for t in titles), titles
    assert any(t.startswith("[AC2] test_rule_recorded") for t in titles), titles
    return children


def _build_first(rig: ExitRig, child: str) -> None:
    out = _run_once(rig)
    assert out[:2] == ["submitted", child], out
    prompt = build_prompts(rig)[-1]  # the task-plan annotation, read from real awg rows
    assert "Test plan for this task" in prompt and "test_discount_over_100" in prompt
    sha = out[2]
    proof = rig.awg("proof", child, "--json", token="runner-agent")
    ci = [e for v in proof["validations"] for e in v["evidence"]
          if e["producer"] == "maggy-runner-ci"]
    assert ci and all(e["trust_class"] == 3 and e["commit_sha"] == sha for e in ci)
    assert remote_head(rig.remote, child) == sha
    [pr] = rig.gh.prs()
    assert pr["isDraft"] and pr["head"] == f"maggy/{child}"


def test_ambiguous_ticket_question_answer_spec_plan_build(rig: ExitRig) -> None:
    agents = install_agents(rig)
    ref = _intake(rig)
    _ask_one_question(rig, ref, agents)
    assert _run_once(rig)[0] == "idle", "a WAITING_HUMAN item is never claimed"
    answer_as_human(rig, ref)
    _approve_spec(rig, ref, agents)
    children = _plan(rig, ref, agents[0])
    _build_first(rig, children["Record the discount rule"]["display_id"])
