"""Assemble a Runner for `maggy run` from the repo profile and the runner's AWG credentials."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import typer

from maggy.harness.loader import resolve_profile
from maggy.runner.awg_cli import CliAwgClient
from maggy.runner.awg_types import AwgCliConfig
from maggy.runner.config import RunnerConfig
from maggy.runner.loop import Runner
from maggy.runner.publish import publisher_for
from maggy.worker.adapter_loader import load_adapter
from maggy.worker.assemble import default_state_dir
from maggy.worker.git_ops import run_git
from maggy.worker.launch import Refused, resolve_launch

STATE_HELP = "Runner state dir (default ~/.maggy)."


@dataclass
class RunCliOptions:
    once: bool = typer.Option(False, "--once", help="Process at most one item, then exit.")
    project: str | None = typer.Option(None, "--project", help="Project key (default: repo name).")
    adapter: str | None = typer.Option(None, "--adapter", help="Adapter (default: worker.adapter).")
    repo: Path = typer.Option(Path("."), "--repo", help="Git repository the items belong to.")
    state_dir: Path | None = typer.Option(None, "--state-dir", help=STATE_HELP)
    awg_bin: Path | None = typer.Option(None, "--awg-bin", help="awg executable (default: PATH).")


def state_of(state_dir: Path | None) -> Path:
    return state_dir or default_state_dir()


def build_runner(opts: RunCliOptions) -> Runner:
    """Refused when no adapter is configured, a launch would be refused, or tokens are missing."""
    state = state_of(opts.state_dir)
    repo = Path(run_git(opts.repo, ["rev-parse", "--show-toplevel"]))
    profile = resolve_profile(repo).profile
    name = opts.adapter or profile.worker.adapter or profile.agents.default
    if not name:
        raise Refused("no adapter: pass --adapter or set worker.adapter in the profile")
    adapter = load_adapter(name)
    resolve_launch(adapter, profile, profile.worker.permission)
    client = CliAwgClient(_awg_config(state, opts.awg_bin))
    config = RunnerConfig(repo=repo, state_dir=state, adapter=adapter, profile=profile,
                          project=opts.project or repo.name,
                          pr_step=publisher_for(client, repo, state))
    return Runner(client, config)


def runner_token_files(state: Path) -> tuple[Path, Path]:
    """<state>/tokens/runner-agent.token (lifecycle) and runner-ci.token (evidence only),
    as minted by `maggy harness init`; Refused naming whichever is missing."""
    agent, ci = (state / "tokens" / f"{name}.token" for name in ("runner-agent", "runner-ci"))
    missing = [str(path) for path in (agent, ci) if not path.is_file()]
    if missing:
        raise Refused(f"missing AWG token file(s): {', '.join(missing)} "
                      "(run `maggy harness init`)")
    return agent, ci


def awg_binary(awg_bin: Path | None) -> Path:
    return awg_bin or Path(shutil.which("awg") or "awg")


def _awg_config(state: Path, awg_bin: Path | None) -> AwgCliConfig:
    agent, ci = runner_token_files(state)
    return AwgCliConfig(binary=awg_binary(awg_bin), agent_token_file=agent, ci_token_file=ci)
