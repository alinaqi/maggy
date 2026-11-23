"""A child `awg create` left READY is cancelled when its BACKLOG move or task-plan annotation
fails, so a failed plan never leaves a claimable stage:build orphan (Phase 4 review)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.awg_cli import CliAwgClient
from maggy.runner.awg_errors import AwgError
from maggy.runner.awg_types import AwgCliConfig, ChildSpec, Claim
from tests.runner_awg_helpers import FakeAwgBin, token_files

CLAIM = Claim(ref="AWG-7", work_id="n", attempt_id="att-1", fencing_token=4, lease_expires=1.0)


def _cli(tmp_path: Path) -> tuple[CliAwgClient, FakeAwgBin]:
    fake = FakeAwgBin(tmp_path)
    agent, ci = token_files(tmp_path)
    return CliAwgClient(AwgCliConfig(binary=fake.path, agent_token_file=agent,
                                     ci_token_file=ci)), fake


def _create_argvs(tmp_path: Path, failing: str) -> tuple[list[list[str]], AwgError]:
    client, fake = _cli(tmp_path)
    fake.reply("create", {"display_id": "AWG-9"})
    fake.reply(failing, rc=1, stderr="awg: conflict: boom\n")
    with pytest.raises(AwgError) as raised:
        client.create_child(CLAIM, ChildSpec(title="t", capabilities=["stage:build"], plan={}))
    return [call["argv"][2:] for call in fake.calls()], raised.value


def test_cli_child_is_cancelled_when_its_annotation_fails(tmp_path: Path) -> None:
    argvs, error = _create_argvs(tmp_path, "annotate")
    assert error.code == "conflict"
    assert argvs[-1] == ["state", "--reason=maggy plan stage", "--json", "--", "AWG-9",
                         "CANCELLED"]


def test_cli_child_left_ready_is_cancelled_and_the_first_error_raised(tmp_path: Path) -> None:
    argvs, error = _create_argvs(tmp_path, "state")
    assert error.code == "conflict" and "boom" in str(error)
    assert argvs[1][-1] == "BACKLOG"
    assert argvs[-1][-2:] == ["AWG-9", "CANCELLED"]
