"""AWG graph calls the spec stage needs: update, node create, decision (fake + CLI)."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.awg_cli import CliAwgClient
from maggy.runner.awg_fake import FakeAwg
from maggy.runner.awg_types import AwgCliConfig, Claim, NodeSpec, WorkUpdate
from tests.runner_awg_helpers import FakeAwgBin, token_files


def _claimed() -> tuple[FakeAwg, Claim]:
    fake = FakeAwg()
    fake.add_item("Spec me", capabilities=["maggy-runner", "stage:spec"])
    claim = fake.next_claim(["maggy-runner", "stage:spec"])
    assert claim is not None
    return fake, claim


def test_fake_update_bumps_version_and_replaces_fields() -> None:
    fake, claim = _claimed()
    before = fake.items[claim.ref].version
    done = fake.update(claim, WorkUpdate(acceptance_criteria=["x"]))
    item = fake.items[claim.ref]
    assert item.acceptance_criteria == ["x"] and done["version"] == item.version > before
    fake.update(claim, WorkUpdate(capabilities=["maggy-runner", "stage:plan"]))
    assert item.capabilities == {"maggy-runner", "stage:plan"}
    assert item.acceptance_criteria == ["x"]


def test_fake_nodes_and_decisions_are_recorded() -> None:
    fake, claim = _claimed()
    node = fake.create_node(claim, NodeSpec(type="REQUIREMENT", title="t", data={"id": "AC1"}))
    fake.decision(claim, "spec-approved", {"spec_version": 4})
    assert node["type"] == "REQUIREMENT" and node["parent"] == claim.ref
    assert [n["type"] for n in fake.nodes] == ["REQUIREMENT", "DECISION"]
    assert fake.nodes[1]["data"] == {"spec_version": 4}


def _cli(tmp_path: Path) -> tuple[CliAwgClient, FakeAwgBin]:
    fake = FakeAwgBin(tmp_path)
    agent, ci = token_files(tmp_path)
    return CliAwgClient(AwgCliConfig(binary=fake.path, agent_token_file=agent,
                                     ci_token_file=ci)), fake


def _claim() -> Claim:
    return Claim(ref="AWG-7", work_id="n", attempt_id="att-1", fencing_token=4, lease_expires=1.0)


def test_cli_update_node_and_decision_argv(tmp_path: Path) -> None:
    client, fake = _cli(tmp_path)
    for name in ("update", "node", "decision"):
        fake.reply(name, {"display_id": "AWG-7", "version": 5})
    client.update(_claim(), WorkUpdate(acceptance_criteria=["a b"], capabilities=["c"]))
    client.create_node(_claim(), NodeSpec(type="REQUIREMENT", title="-t", data={"k": 1}))
    client.decision(_claim(), "spec-approved", {"spec_version": 5})
    argvs = [call["argv"][2:] for call in fake.calls()]
    assert argvs[0] == ["update", "--ac=a b", "--capability=c", "--json", "--", "AWG-7"]
    assert argvs[1] == ["node", "create", "--type=REQUIREMENT", "--parent=AWG-7",
                        '--data={"k": 1}', "--json", "--", "-t"]
    assert argvs[2] == ["decision", "--key=spec-approved", '--data={"spec_version": 5}',
                        "--json", "--", "AWG-7"]
