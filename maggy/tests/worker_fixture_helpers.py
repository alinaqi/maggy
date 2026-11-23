"""Loads the recorded worker-CLI output fixtures and their meta.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from maggy.worker.parsers import RawRun

FIXTURES = Path(__file__).parent / "fixtures" / "worker"


def load_meta(cli: str) -> dict:
    return yaml.safe_load((FIXTURES / cli / "meta.yaml").read_text())


def all_cases() -> list[tuple[str, str]]:
    clis = sorted(p.parent.name for p in FIXTURES.glob("*/meta.yaml"))
    return [(cli, case) for cli in clis for case in load_meta(cli)["cases"]]


def raw_run(cli: str, case: str) -> RawRun:
    entry = load_meta(cli)["cases"][case]
    stdout = (FIXTURES / cli / entry["file"]).read_text()
    return RawRun(stdout=stdout, stderr=entry["stderr"], exit_code=entry["exit_code"])


def run_case(cli: str, case: str):
    """Parse one fixture the way the runner will; returns (parsed, expect)."""
    from maggy.worker.parsers import parse_run

    meta = load_meta(cli)
    parsed = parse_run(meta["parser"], raw_run(cli, case), meta["quota_patterns"])
    return parsed, meta["cases"][case]["expect"]
