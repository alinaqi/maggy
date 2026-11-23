"""A fake `gh` for the Phase 3 exit test: issues for `awg sync github`, draft PRs for the
runner, and a `hold` switch that parks `gh pr list` so the runner can be killed mid-publish."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from runner_publish_helpers import FakeGh

# `gh api` serves issues.json (for awg sync); `pr list` hangs while `hold` exists; the rest
# is the runner tests' FakeGh (pr list/create/edit), renamed gh_pr.
_GH = """#!{python}
import json, os, sys, time
root = {root!r}
args = sys.argv[1:]
if args[:1] == ['api']:
    if 'comments' not in args[2]:
        for issue in json.load(open(os.path.join(root, 'issues.json'))):
            print(json.dumps(issue))
    sys.exit(0)
if args[:2] == ['pr', 'list'] and os.path.exists(os.path.join(root, 'hold')):
    open(os.path.join(root, 'holding'), 'w').write(str(os.getpid()))
    time.sleep(120)
os.execv(sys.executable, [sys.executable, os.path.join(root, 'gh_pr'), *args])
"""


class ExitGh(FakeGh):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        (root / "gh").rename(root / "gh_pr")
        (root / "gh").write_text(_GH.format(python=sys.executable, root=str(root)))
        (root / "gh").chmod(0o755)
        self.issues([])

    def issues(self, issues: list[dict]) -> None:
        (self.root / "issues.json").write_text(json.dumps(issues))


def issue(number: int, labels: list[str]) -> dict:
    stamp = "2026-11-01T00:00:00Z"
    return {"node_id": f"I_{number}", "number": number, "title": f"Add feature {number}",
            "html_url": f"https://example.invalid/acme/shop/issues/{number}",
            "body": "Write feature.txt.", "state": "open", "assignees": [],
            "labels": [{"name": name} for name in labels], "user": {"login": "me"},
            "created_at": stamp, "updated_at": stamp}
