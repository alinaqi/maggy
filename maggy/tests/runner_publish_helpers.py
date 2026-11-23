"""A local bare remote, a fake `gh` on PATH and worker results for publish tests (no network)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from maggy.runner.awg_fake import FakeAwg
from maggy.runner.awg_types import Claim
from maggy.runner.publish import PublishConfig, Publisher
from maggy.worker.models import CheckResult, WorkerResult
from worker_git_helpers import git, init_repo

# Records argv, keeps PRs in prs.json; anything but pr list/create/edit exits 3.
_GH = """#!{python}
import json, os, sys
root = {root!r}
args = sys.argv[1:]
with open(os.path.join(root, 'gh_calls.jsonl'), 'a') as log:
    log.write(json.dumps({{'argv': args, 'awg_token': os.environ.get('AWG_TOKEN')}}) + '\\n')
path = os.path.join(root, 'prs.json')
prs = json.load(open(path)) if os.path.exists(path) else []
opt = lambda name: args[args.index(name) + 1]
if args[:2] == ['pr', 'list']:
    print(json.dumps([p for p in prs if p['head'] == opt('--head') and p['state'] == 'OPEN']))
elif args[:2] == ['pr', 'create']:
    url = 'https://example.invalid/pr/%d' % (len(prs) + 1)
    prs.append({{'number': len(prs) + 1, 'url': url, 'isDraft': '--draft' in args,
                'state': 'OPEN', 'head': opt('--head'), 'base': opt('--base'),
                'isCrossRepository': False, 'headRepositoryOwner': {{'login': 'me'}},
                'title': opt('--title'), 'body': open(opt('--body-file')).read()}})
    print(url)
elif args[:2] == ['pr', 'edit']:
    pr = next(p for p in prs if p['number'] == int(args[2]))
    pr['body'] = open(opt('--body-file')).read()
    print(pr['url'])
else:
    sys.exit(3)
json.dump(prs, open(path, 'w'))
"""


class FakeGh:
    """A fake `gh` in `root`; put `root` first on PATH."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        path = root / "gh"
        path.write_text(_GH.format(python=sys.executable, root=str(root)))
        path.chmod(0o755)

    def calls(self) -> list[list[str]]:
        log = self.root / "gh_calls.jsonl"
        lines = log.read_text().splitlines() if log.exists() else []
        return [json.loads(line)["argv"] for line in lines]

    def prs(self) -> list[dict]:
        path = self.root / "prs.json"
        return json.loads(path.read_text()) if path.exists() else []

    def creates(self) -> int:
        return sum(1 for argv in self.calls() if argv[:2] == ["pr", "create"])


@dataclass
class Rig:
    awg: FakeAwg
    claim: Claim
    repo: Path
    remote: Path
    gh: FakeGh
    publisher: Publisher


def make_rig(tmp_path: Path, monkeypatch, awg: FakeAwg | None = None) -> Rig:
    awg = awg or FakeAwg(lease_seconds=900)
    awg.add_item("Add login", capabilities=["maggy-runner"])
    repo, remote = tmp_path / "repo", tmp_path / "remote.git"
    repo.mkdir()
    init_repo(repo)
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    gh = FakeGh(tmp_path / "ghbin")
    monkeypatch.setenv("PATH", f"{gh.root}:{os.environ['PATH']}")
    config = PublishConfig(repo=repo, state_dir=tmp_path / "state", base="main")
    claim = awg.next_claim(["maggy-runner"])
    return Rig(awg, claim, repo, remote, gh, Publisher(awg, config))


def candidate(repo: Path, ref: str, text: str) -> str:
    """Commit `text` on maggy/<ref> (created from main if needed); returns the SHA."""
    existing = git(repo, "branch", "--list", f"maggy/{ref}")
    git(repo, "checkout", "-q", *([] if existing else ["-b"]), f"maggy/{ref}")
    (repo / "feature.txt").write_text(text)
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=T", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", text)
    sha = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "main")
    return sha


def result_for(sha: str) -> WorkerResult:
    check = CheckResult(name="test", command="pytest", exit_code=0, passed=True, sha=sha,
                        duration_s=1.0)
    return WorkerResult(outcome="succeeded", candidate_commit=sha, checks=[check],
                        elapsed_s=2.0, agent="fake", model="m", adapter_version="1")


def remote_head(remote: Path, ref: str) -> str:
    listing = git(remote, "ls-remote", str(remote), f"refs/heads/maggy/{ref}")
    return listing.split("\t")[0] if listing else ""


def reclaim(rig: Rig) -> Claim:
    """Give the item back and claim it again: a new attempt."""
    rig.awg.release(rig.claim, "retry")
    rig.claim = rig.awg.next_claim(["maggy-runner"])
    return rig.claim
