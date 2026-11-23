"""Spec-stage rigs: FakeAwg, a throwaway repo and two fake agent CLIs replaying recorded replies.

Each fake agent pops its next reply from <root>/queue.json and logs the prompt it got to
<root>/prompts.jsonl, so tests can check what the author and the reviewer were shown.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.runner.awg_fake import FakeAwg
from maggy.runner.loop import Runner, RunnerConfig
from maggy.worker.adapter_spec import AdapterSpec
from worker_git_helpers import fake_adapter_data, init_repo, profile_data, write_script

SPEC_CAPS = ["maggy-runner", "stage:spec", "project:demo"]

REPLAY_AGENT = """
import json, sys
from pathlib import Path
root = Path({root!r})
queue = json.loads((root / "queue.json").read_text())
with (root / "prompts.jsonl").open("a") as log:
    log.write(json.dumps(sys.argv[-1]) + "\\n")
reply = queue.pop(0) if queue else "no reply recorded"
(root / "queue.json").write_text(json.dumps(queue))
print(reply)
"""


def fenced(data: object) -> str:
    """A reply carrying `data` as the single fenced json block the runner asks for."""
    return f"Here is my answer.\n\n```json\n{json.dumps(data)}\n```\n"


def draft(*texts: str) -> dict:
    criteria = [{"id": f"AC{n}", "text": text, "kind": "functional", "testable": True}
                for n, text in enumerate(texts, start=1)]
    return {"acceptance_criteria": criteria, "open_questions": [], "assumptions": [],
            "risk_paths": []}


def review(verdict: str, question: object = None, issues: list | None = None) -> dict:
    return {"verdict": verdict, "question": question, "issues": issues or []}


class Agent:
    """One fake agent CLI with its own reply queue and prompt log."""

    def __init__(self, root: Path, name: str) -> None:
        self.root, self.name = root, name
        root.mkdir(parents=True)
        self.queue([])
        script = write_script(root, "agent", REPLAY_AGENT.format(root=str(root)))
        self.adapter = AdapterSpec.model_validate(fake_adapter_data(script, name=name))

    def queue(self, replies: list[str]) -> None:
        (self.root / "queue.json").write_text(json.dumps(replies))

    def prompts(self) -> list[str]:
        log = self.root / "prompts.jsonl"
        lines = log.read_text().splitlines() if log.exists() else []
        return [json.loads(line) for line in lines]


@dataclass
class SpecRig:
    runner: Runner
    awg: FakeAwg
    ref: str
    author: Agent
    reviewer: Agent
    state: Path


def make_spec_rig(tmp_path: Path, description: str = "Let users export data.") -> SpecRig:
    awg = FakeAwg(lease_seconds=900)
    ref = awg.add_item("Export data", capabilities=SPEC_CAPS)
    awg.items[ref].description = description
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("Use pytest. Keep functions small.\n")
    init_repo(repo)
    author, reviewer = Agent(tmp_path / "author", "fakeauthor"), Agent(tmp_path / "rev", "fakereview")
    config = RunnerConfig(repo=repo, state_dir=tmp_path / "state", adapter=author.adapter,
                          profile=_profile(), project="demo", heartbeat_s=30.0,
                          adapters={a.name: a.adapter for a in (author, reviewer)})
    return SpecRig(Runner(awg, config), awg, ref, author, reviewer, tmp_path / "state")


def _profile() -> HarnessProfile:
    data = profile_data()
    data["agents"] = {"default": "fakeauthor", "prefer": {"review": "fakereview"}}
    return HarnessProfile.model_validate(data)


def answer(rig: SpecRig, body: str) -> None:
    """A human answers on the item and moves it back to READY."""
    item = rig.awg.items[rig.ref]
    item.comments.append({"body": body, "author": "human"})
    item.state = "READY"

