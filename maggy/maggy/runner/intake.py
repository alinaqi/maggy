"""`maggy run intake`: pull labelled GitHub issues into AWG as runner-claimable items.

Wraps `awg sync github OWNER/REPO --label L --capability C... --json`. Only issues carrying
the label are imported (no label, no intake), and new items require the runner's
capabilities. `awg sync` needs the workspace admin scope, so it runs with the user's own
AWG credential, never the runner's tokens; GitHub is read with the user's own `gh` auth.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer

from maggy.harness.loader import resolve_profile
from maggy.runner.awg_errors import AwgError, AwgUnavailable, parse_failure
from maggy.runner.config import CAPABILITIES
from maggy.worker.launch import Refused

GITHUB_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9_.][A-Za-z0-9_.-]{0,99}$")


@dataclass
class IntakeOptions:
    repo: str = typer.Option(..., "--repo", help="GitHub OWNER/REPO to pull issues from.")
    label: str | None = typer.Option(None, "--label", help="Opt-in label (default intake.label).")
    project: str | None = typer.Option(None, "--project", help="AWG project key for new items.")
    checkout: Path = typer.Option(Path("."), "--checkout",
                                  help="Local checkout whose profile supplies intake.*.")
    awg_bin: Path | None = typer.Option(None, "--awg-bin", help="awg executable (default: PATH).")


def sync_argv(opts: IntakeOptions) -> list[str]:
    """`sync github` argv (without the binary); Refused on a bad repo or no label."""
    if not GITHUB_REPO.match(opts.repo):
        raise Refused(f"--repo must be OWNER/REPO, got {opts.repo!r}")
    intake = resolve_profile(opts.checkout).profile.intake
    label = opts.label or intake.label
    if not label:
        raise Refused("no intake label: pass --label or set intake.label in the profile")
    caps = [f"--capability={cap}" for cap in intake.capabilities or CAPABILITIES]
    project = [f"--project={opts.project}"] if opts.project else []
    return ["sync", "github", f"--label={label}", *caps, *project, "--json", "--", opts.repo]


def run_sync(binary: Path, argv: list[str]) -> dict:
    try:
        done = subprocess.run([str(binary), *argv], capture_output=True, text=True,
                              check=False, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AwgUnavailable("unavailable", f"cannot run awg: {type(exc).__name__}") from exc
    if done.returncode != 0:
        raise parse_failure(done.stdout, done.stderr)
    try:
        return dict(json.loads(done.stdout))
    except (ValueError, TypeError) as exc:
        raise AwgError("bad_output", "awg sync did not print a JSON object") from exc


def summary(report: dict) -> list[str]:
    """One count line, then `<outcome>\\t#<issue>\\t<ref>` per created/updated item."""
    counts = " ".join(f"{key} {report.get(key, 0)}" for key in ("created", "updated", "skipped"))
    refs = report.get("refs") or {}
    rows = [f"{outcome}\t#{row.get('issue')}\t{row.get('ref')}"
            for outcome in ("created", "updated") for row in refs.get(outcome) or []]
    return [counts, *rows]
