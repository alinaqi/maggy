"""AWG calls the plan stage needs: child items, links, validations, state, decisions (fake + CLI)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.awg_cli import CliAwgClient
from maggy.runner.awg_errors import AwgError
from maggy.runner.awg_fake import FakeAwg
from maggy.runner.awg_types import (
    AwgCliConfig, ChildSpec, Claim, EdgeSpec, NodeSpec, ValidationSpec,
)
from tests.runner_awg_helpers import FakeAwgBin, token_files

CAPS = ["maggy-runner", "stage:plan"]


def _claimed() -> tuple[FakeAwg, Claim]:
    fake = FakeAwg()
    fake.add_item("Plan me", capabilities=CAPS)
    claim = fake.next_claim(CAPS)
    assert claim is not None
    return fake, claim


def _child(fake: FakeAwg, claim: Claim, title: str) -> str:
    made = fake.create_child(claim, ChildSpec(title=title, capabilities=["stage:build"],
                                              plan={"files": ["a.py"]}))
    return made["display_id"]


def test_fake_children_start_backlog_with_their_task_plan() -> None:
    fake, claim = _claimed()
    ref = _child(fake, claim, "step 1")
    item = fake.items[ref]
    assert item.state == "BACKLOG" and item.parent == claim.ref
    assert fake.annotations(ref)[0]["idempotency_key"] == "task-plan"
    assert fake.annotations(ref)[0]["data"] == {"files": ["a.py"]}
    fake.set_state(ref, "READY")
    assert item.state == "READY"


def test_fake_links_refuse_cycles_and_gate_claims() -> None:
    fake, claim = _claimed()
    one, two = _child(fake, claim, "one"), _child(fake, claim, "two")
    fake.link(claim, EdgeSpec(source=two, type="DEPENDS_ON", target=one))
    with pytest.raises(AwgError) as raised:
        fake.link(claim, EdgeSpec(source=one, type="DEPENDS_ON", target=two))
    assert raised.value.code == "dependency_cycle"
    for ref in (one, two):
        fake.set_state(ref, "READY")
    assert fake.next_claim(["stage:build"]).ref == one
    assert fake.next_claim(["stage:build"]) is None  # two waits on one


def test_fake_validations_decisions_and_requirements() -> None:
    fake, claim = _claimed()
    node = fake.create_node(claim, _requirement())
    ref = _child(fake, claim, "one")
    fake.add_validation(claim, ValidationSpec(work=ref, kind="test", title="t", min_trust=3,
                                              requirement=node["id"]))
    fake.decision(claim, "spec-approved", {"spec_version": 2})
    assert fake.items[ref].validations[0]["requirement"] == node["id"]
    assert fake.decisions(claim.ref) == [{"id": "N-2", "key": "spec-approved",
                                          "data": {"spec_version": 2}}]
    assert fake.requirements(claim.ref) == [{"id": node["id"], "title": "r", "criterion": "AC1"}]


def _requirement() -> NodeSpec:
    return NodeSpec(type="REQUIREMENT", title="r", data={"id": "AC1"})


def _cli(tmp_path: Path) -> tuple[CliAwgClient, FakeAwgBin]:
    fake = FakeAwgBin(tmp_path)
    agent, ci = token_files(tmp_path)
    return CliAwgClient(AwgCliConfig(binary=fake.path, agent_token_file=agent,
                                     ci_token_file=ci)), fake


CLAIM = Claim(ref="AWG-7", work_id="n", attempt_id="att-1", fencing_token=4, lease_expires=1.0)
FENCE = ["--attempt=att-1", "--fencing-token=4"]


def test_cli_child_link_validation_state_argv(tmp_path: Path) -> None:
    client, fake = _cli(tmp_path)
    for name in ("create", "state", "annotate", "link", "validation"):
        fake.reply(name, {"display_id": "AWG-9", "id": "V-1"})
    client.create_child(CLAIM, ChildSpec(title="-step", capabilities=["a", "b"], plan={"k": 1}))
    client.link(CLAIM, EdgeSpec(source="AWG-9", type="DEPENDS_ON", target="AWG-8"))
    client.add_validation(CLAIM, ValidationSpec(work="AWG-9", kind="test", title="t",
                                                min_trust=3, requirement="R-1"))
    client.set_state("AWG-9", "READY")
    argvs = [call["argv"][2:] for call in fake.calls()]
    assert argvs[0] == ["create", "--parent=AWG-7", "--capability=a", "--capability=b", *FENCE,
                        "--json", "--", "-step"]
    assert argvs[1] == ["state", "--reason=maggy plan stage", "--json", "--", "AWG-9", "BACKLOG"]
    assert argvs[2][:2] == ["annotate", "--kind=custom"] and argvs[2][-1] == "AWG-9"
    assert argvs[3] == ["link", "--lease=AWG-7", *FENCE, "--json", "--", "AWG-9", "DEPENDS_ON",
                        "AWG-8"]
    assert argvs[4] == ["validation", "add", "--kind=test", "--title=t", "--min-trust=3",
                        "--requirement=R-1", "--json", "--", "AWG-9"]
    assert argvs[5] == ["state", "--reason=maggy plan stage", "--json", "--", "AWG-9", "READY"]


def test_cli_decisions_and_requirements_are_normalised(tmp_path: Path) -> None:
    client, fake = _cli(tmp_path)
    fake.reply("decisions", [{"id": "D-1", "properties": {"key": "k", "data": {"a": 1}}}])
    fake.reply("show", {"work": {}, "context": {"requirements": [{"id": "R-1", "title": "r"}]}})
    assert client.decisions("AWG-7") == [{"id": "D-1", "key": "k", "data": {"a": 1}}]
    assert client.requirements("AWG-7") == [{"id": "R-1", "title": "r", "criterion": None}]


def test_cli_set_capabilities_is_an_unfenced_update(tmp_path: Path) -> None:
    client, fake = _cli(tmp_path)
    fake.reply("update", {"display_id": "AWG-9", "version": 3})
    client.set_capabilities("AWG-9", ["maggy-runner", "stage:build"])
    assert fake.calls()[0]["argv"][2:] == ["update", "--capability=maggy-runner",
                                           "--capability=stage:build", "--json", "--", "AWG-9"]
