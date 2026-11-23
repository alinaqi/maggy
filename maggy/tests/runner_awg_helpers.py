"""A fake `awg` executable that records argv/env and replays canned JSON (runner tests)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from maggy.runner.awg_fake import FakeAwg

AGENT_SECRET = "awg_agent_s3cr3t_DO_NOT_LEAK"
CI_SECRET = "awg_ci_s3cr3t_DO_NOT_LEAK"

_SCRIPT = """#!{python}
import json, os, sys
root = {root!r}
args = sys.argv[1:]
commands = json.load(open(os.path.join(root, 'responses.json')))
name = next((a for a in args if a in commands), args[-1] if args else '')
with open(os.path.join(root, 'calls.jsonl'), 'a') as log:
    log.write(json.dumps({{'argv': args, 'env_token': os.environ.get('AWG_TOKEN')}}) + '\\n')
reply = commands.get(name, {{'rc': 0, 'stdout': '{{}}', 'stderr': ''}})
sys.stdout.write(reply.get('stdout', ''))
sys.stderr.write(reply.get('stderr', ''))
sys.exit(reply.get('rc', 0))
"""

LEASE = {
    "work_id": "node-1", "display_id": "AWG-7", "attempt_id": "att-1",
    "agent_id": "maggy-runner", "fencing_token": 4, "lease_expires_at": 1700000900.0,
    "version": 3,
    "context": {"goal": "Add login", "description": "Users can log in",
                "acceptance_criteria": ["login works", "logout works"]},
}


class FakeAwgBin:
    """A fake awg binary in `root`; `reply(cmd, ...)` sets what each subcommand returns."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "awg"
        self.path.write_text(_SCRIPT.format(python=sys.executable, root=str(root)))
        self.path.chmod(0o755)
        self.replies: dict = {}
        self._save()

    def reply(self, command: str, payload: object = None, **err: object) -> None:
        stdout = "" if payload is None else json.dumps(payload)
        self.replies[command] = {"rc": err.get("rc", 0), "stdout": stdout,
                                 "stderr": err.get("stderr", "")}
        self._save()

    def calls(self) -> list[dict]:
        log = self.root / "calls.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def _save(self) -> None:
        (self.root / "responses.json").write_text(json.dumps(self.replies))


def token_files(root: Path) -> tuple[Path, Path]:
    agent, ci = root / "agent.token", root / "ci.token"
    agent.write_text(AGENT_SECRET)
    ci.write_text(CI_SECRET)
    return agent, ci


class Clock:
    """A settable clock for FakeAwg lease tests."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def fake_awg(clock: Clock) -> FakeAwg:
    fake = FakeAwg(clock=clock, lease_seconds=60)
    fake.add_item("Add login", capabilities=["maggy-runner"], acceptance_criteria=["works"])
    return fake
