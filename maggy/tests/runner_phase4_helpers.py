"""Phase 4 exit rig: the Phase 3 rig (real awg, temp HOME/AWG_HOME, bare origin, fake gh) plus
two replay agents installed as user adapters: `fakeauthor` (agents.default: spec author and
planner) and `fakereview` (agents.prefer.review). Builds use `fakeedit` (worker.adapter)."""

from __future__ import annotations

import json

from runner_exit_helpers import ExitRig
from runner_spec_helpers import Agent
from worker_git_helpers import fake_adapter_data
from worker_helpers import write_adapter

AMBIGUOUS = "Apply the new discount rules"
QUESTION = "Which discount rules apply: the percentage, the threshold and the products?"
ANSWER = "10% off orders over 100 EUR, all products. Record the rule in feature.txt."
CRITERIA = ("Orders over 100 EUR get 10% off", "The discount rule is recorded in feature.txt")


def install_agents(rig: ExitRig) -> tuple[Agent, Agent]:
    """(author, reviewer) replay agents, wired into the personal profile and adapters dir."""
    author = Agent(rig.root / "author", "fakeauthor")
    reviewer = Agent(rig.root / "reviewer", "fakereview")
    adapters = rig.home / ".maggy" / "adapters"
    for agent in (author, reviewer):
        write_adapter(adapters, fake_adapter_data(agent.root / "agent.py", name=agent.name))
    profile_file = rig.home / ".maggy" / "harness.yaml"
    data = json.loads(profile_file.read_text())
    data["agents"] = {"default": "fakeauthor", "prefer": {"review": "fakereview"}}
    profile_file.write_text(json.dumps(data))
    return author, reviewer


def ambiguous_issue(number: int) -> dict:
    stamp = "2026-11-01T00:00:00Z"
    return {"node_id": f"I_{number}", "number": number, "title": AMBIGUOUS,
            "html_url": f"https://example.invalid/acme/shop/issues/{number}",
            "body": f"{AMBIGUOUS}.", "state": "open", "assignees": [],
            "labels": [{"name": "factory"}], "user": {"login": "me"},
            "created_at": stamp, "updated_at": stamp}


def two_task_plan() -> dict:
    """T1 writes feature.txt (AC1, AC2 by unit tests); T2 depends on T1."""
    def entry(criterion: str, test_name: str) -> dict:
        return {"criterion_id": criterion, "task": "T1", "fixture": "an empty repo",
                "action": "apply the rule", "expected": f"{criterion} holds",
                "evidence": "unit", "regression_test_name": test_name}
    tasks = [{"key": "T1", "title": "Record the discount rule", "description": "Write it.",
              "files": ["feature.txt"], "depends_on": []},
             {"key": "T2", "title": "Document the rule", "description": "Docs.",
              "files": ["README.md"], "depends_on": ["T1"]}]
    return {"tasks": tasks, "test_plan": [entry("AC1", "test_discount_over_100"),
                                          entry("AC2", "test_rule_recorded")]}


def shown(rig: ExitRig, ref: str) -> dict:
    return dict(rig.awg("show", ref, "--json"))


def comment_bodies(rig: ExitRig, ref: str) -> list[str]:
    """The item's comment thread, from the `awg show --json` context bundle."""
    comments = (shown(rig, ref).get("context") or {}).get("comments") or []
    return [str(c.get("body", "")) for c in comments]


def answer_as_human(rig: ExitRig, ref: str) -> None:
    rig.awg("comment", ref, ANSWER, "--json")
    rig.awg("state", ref, "READY", "--reason=answered", "--json")


def children_by_title(rig: ExitRig) -> dict[str, dict]:
    titles = {task["title"] for task in two_task_plan()["tasks"]}
    return {i["title"]: i for i in rig.awg("list", "--json")["items"] if i["title"] in titles}


def build_prompts(rig: ExitRig) -> list[str]:
    """Prompts the build agent (the `fakeedit` adapter) was given, oldest first."""
    log = rig.root / "build-prompts.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
