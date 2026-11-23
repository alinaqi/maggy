"""Running the awg CLI: argv only, a token FILE per call, JSON out, typed errors.

The token secret is never read here: argv carries only `--token-file <path>`, and the child
env drops AWG_TOKEN so an ambient (e.g. owner) credential can never stand in for the file.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

from maggy.runner.awg_errors import AwgError, AwgUnavailable, parse_failure
from maggy.runner.awg_types import AwgCliConfig, Claim

log = logging.getLogger(__name__)


def command(name: str, options: list[str], ref: str) -> list[str]:
    """`name OPTIONS --json -- REF`: the ref can never be read as an option."""
    return [name, *options, "--json", "--", ref]


def fence(claim: Claim) -> list[str]:
    return [f"--attempt={claim.attempt_id}", f"--fencing-token={claim.fencing_token}"]


class CliBase:
    def __init__(self, config: AwgCliConfig) -> None:
        self.config = config

    def _agent(self, args: list[str]) -> object:
        return self._run(self.config.agent_token_file, args)

    def _ci(self, args: list[str]) -> object:
        return self._run(self.config.ci_token_file, args)

    def _run(self, token_file: Path, args: list[str]) -> object:
        argv = [str(self.config.binary), "--token-file", str(token_file), *args]
        log.debug("awg %s (token file %s)", args[0], token_file.name)
        try:
            done = subprocess.run(argv, capture_output=True, text=True, check=False,
                                  env=_child_env(), timeout=self.config.timeout_s)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AwgUnavailable("unavailable", f"cannot run awg: {type(exc).__name__}") from exc
        if done.returncode != 0:
            raise parse_failure(done.stdout, done.stderr)
        return _decode(done.stdout)


def _child_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key != "AWG_TOKEN"}


def _decode(stdout: str) -> object:
    try:
        return json.loads(stdout)
    except ValueError as exc:
        raise AwgError("bad_output", "awg did not print JSON") from exc
