"""Opt-in claiming: the runner only takes items that declare `maggy-runner` (RFC §2.4)."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.awg_cli import CliAwgClient
from maggy.runner.awg_client import AwgCliConfig
from maggy.runner.awg_fake import FakeAwg
from maggy.runner.config import REQUIRED
from runner_loop_helpers import CAPS, EDIT_AGENT, make_rig
from tests.runner_awg_helpers import LEASE, FakeAwgBin, token_files


def test_fake_awg_require_leaves_untagged_items_out() -> None:
    awg = FakeAwg()
    awg.add_item("My own personal task, not for the runner")
    assert awg.next_claim(CAPS, ["maggy-runner"]) is None
    assert awg.next_claim(CAPS) is not None, "without require, AWG offers untagged items"


def test_runner_requires_the_maggy_runner_capability() -> None:
    assert REQUIRED == ["maggy-runner"]


def test_runner_leaves_an_untagged_item_alone(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT, capabilities=[])
    assert rig.runner.run_once().outcome == "idle"
    assert rig.awg.items[rig.ref].state == "READY"


def test_cli_next_claim_passes_require_capabilities(tmp_path: Path) -> None:
    fake = FakeAwgBin(tmp_path)
    agent, ci = token_files(tmp_path)
    client = CliAwgClient(AwgCliConfig(binary=fake.path, agent_token_file=agent, ci_token_file=ci))
    fake.reply("next", LEASE)
    client.next_claim(CAPS, ["maggy-runner"])
    assert fake.calls()[0]["argv"] == [
        "--token-file", str(agent), "next", "--claim", "--capabilities=maggy-runner,stage:build",
        "--require-capabilities=maggy-runner", "--json"]
