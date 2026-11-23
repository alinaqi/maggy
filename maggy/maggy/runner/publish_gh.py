"""Draft-PR provider over the `gh` CLI: list, create --draft and edit only (never merge/ready)."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from maggy.runner.publish_git import PublishError
from maggy.worker.env import allowlisted

ALLOWED = frozenset({("pr", "list"), ("pr", "create"), ("pr", "edit")})
FORBIDDEN = frozenset({"merge", "ready", "--ready", "--auto"})
PR_FIELDS = "number,url,isDraft,state,isCrossRepository,headRepositoryOwner"
GH_AUTH = ("GH_TOKEN", "GH_HOST", "GH_ENTERPRISE_TOKEN", "GH_CONFIG_DIR")


@dataclass(frozen=True)
class PrRequest:
    head: str
    base: str
    title: str
    body_file: Path


class GhCli:
    def __init__(self, repo: Path, binary: str = "gh", timeout_s: float = 120.0) -> None:
        self.repo, self.binary, self.timeout_s = repo, binary, timeout_s

    def run(self, args: list[str]) -> str:
        """`gh <args>` for an allowed subcommand; PublishError on refusal or failure."""
        if tuple(args[:2]) not in ALLOWED or FORBIDDEN & set(args):
            raise PublishError(f"refusing gh {' '.join(args[:2])}: only pr list/create/edit")
        try:
            done = subprocess.run([self.binary, *args], cwd=self.repo, env=_gh_env(),
                                  capture_output=True, text=True, check=False,
                                  stdin=subprocess.DEVNULL, timeout=self.timeout_s)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PublishError(f"gh {args[1]} could not run: {exc}") from exc
        if done.returncode != 0:
            raise PublishError(f"gh {args[1]} failed: {done.stderr.strip()[:300]}")
        return done.stdout

    def find(self, head: str) -> dict | None:
        """The open same-repository PR whose head is `head`, if any. `--head` matches the
        branch name only, so a fork's PR from a branch named maggy/<ref> would match too;
        it is never adopted (edited, or recorded as ours)."""
        out = self.run(["pr", "list", "--head", head, "--state", "open", "--json", PR_FIELDS])
        ours = [pr for pr in json.loads(out or "[]") if pr.get("isCrossRepository") is False]
        return ours[0] if ours else None

    def create(self, request: PrRequest) -> None:
        self.run(["pr", "create", "--draft", "--head", request.head, "--base", request.base,
                  "--title", request.title, "--body-file", str(request.body_file)])

    def edit(self, number: int, body_file: Path) -> None:
        self.run(["pr", "edit", str(number), "--body-file", str(body_file)])


def _gh_env() -> dict[str, str]:
    """The scrubbed allowlist plus the user's own gh auth settings (never AWG tokens)."""
    own = {key: os.environ[key] for key in GH_AUTH if key in os.environ}
    return {**allowlisted(os.environ), **own}
