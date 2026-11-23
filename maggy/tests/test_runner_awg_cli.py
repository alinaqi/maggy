"""CliAwgClient: argv construction, JSON parsing and credential split (RFC §2.4, §2.6.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.awg_cli import CliAwgClient
from maggy.runner.awg_client import AwgClient, AwgCliConfig, Claim, EvidenceSpec
from tests.runner_awg_helpers import LEASE, FakeAwgBin, token_files


@pytest.fixture
def awg(tmp_path: Path) -> tuple[CliAwgClient, FakeAwgBin, Path, Path]:
    fake = FakeAwgBin(tmp_path)
    agent, ci = token_files(tmp_path)
    client = CliAwgClient(AwgCliConfig(binary=fake.path, agent_token_file=agent,
                                       ci_token_file=ci))
    return client, fake, agent, ci


def _claim() -> Claim:
    return Claim(ref="AWG-7", work_id="node-1", attempt_id="att-1", fencing_token=4,
                 lease_expires=1.0, version=3)


def test_next_claim_builds_argv_and_parses_lease(awg) -> None:
    client, fake, agent, _ = awg
    fake.reply("next", LEASE)
    claim = client.next_claim(["maggy-runner", "stage:build"])
    assert fake.calls()[0]["argv"] == [
        "--token-file", str(agent), "next", "--claim", "--capabilities=maggy-runner,stage:build", "--json"]
    assert (claim.ref, claim.attempt_id, claim.fencing_token) == ("AWG-7", "att-1", 4)
    assert (claim.version, claim.title, claim.lease_expires) == (3, "Add login", 1700000900.0)
    assert claim.acceptance_criteria == ["login works", "logout works"]
    assert "Users can log in" in claim.context and claim.description == "Users can log in"


def test_next_claim_returns_none_when_nothing_is_ready(awg) -> None:
    client, fake, _, _ = awg
    fake.reply("next", rc=1, stderr="awg: conflict: no claimable work is ready\n")
    assert client.next_claim(["maggy-runner"]) is None


def test_lifecycle_calls_carry_fence_and_agent_token(awg) -> None:
    client, fake, agent, _ = awg
    for name in ("heartbeat", "submit", "release", "block", "comment"):
        fake.reply(name, {"display_id": "AWG-7", "state": "ACTIVE"})
    client.heartbeat(claim := _claim())
    client.submit(claim, "did it", "abc123")
    client.release(claim, "-gave up")
    client.block(claim, "which db?")
    client.handoff(claim, "-resume from branch maggy/AWG-7")
    argvs = [call["argv"] for call in fake.calls()]
    fence = ["--attempt=att-1", "--fencing-token=4"]
    assert argvs[0] == ["--token-file", str(agent), "heartbeat", *fence, "--json", "--", "AWG-7"]
    assert argvs[1] == ["--token-file", str(agent), "submit", *fence, "--summary=did it",
                        "--sha=abc123", "--json", "--", "AWG-7"]
    assert argvs[2][-4:] == ["--reason=-gave up", "--json", "--", "AWG-7"]
    assert argvs[3][2:] == ["block", *fence, "--reason=which db?", "--human", "--json",
                            "--", "AWG-7"]
    assert argvs[4][2:] == ["comment", "--json", "--", "AWG-7",
                            "[handoff att-1] -resume from branch maggy/AWG-7"]
    assert all(argv[:2] == ["--token-file", str(agent)] for argv in argvs)


def test_evidence_alone_uses_the_ci_token(awg) -> None:
    client, fake, agent, ci = awg
    fake.reply("evidence", {"id": "ev-1", "trust_class": 3})
    spec = EvidenceSpec(kind="test", verdict="PASS", commit_sha="abc123",
                        meta={"spec_version": "3"}, validation="val-1")
    assert client.evidence(_claim(), spec) == {"id": "ev-1", "trust_class": 3}
    [evidence] = (call["argv"] for call in fake.calls())
    assert evidence == ["--token-file", str(ci), "evidence", "--kind=test", "--verdict=PASS",
                        "--commit-sha=abc123", "--validation=val-1", "--meta=spec_version=3",
                        "--json", "--", "AWG-7"]


def test_show_merges_validations_and_comments(awg) -> None:
    client, fake, agent, _ = awg
    fake.reply("show", {"work": {"display_id": "AWG-7", "version": 3}, "explain": {}})
    fake.reply("proof", {"validations": [{"id": "val-1", "kind": "test", "required": True}]})
    fake.reply("comments", {"items": [{"body": "[handoff att-1] resume"}]})
    shown = client.show("AWG-7")
    assert shown["work"]["version"] == 3
    assert shown["validations"] == [{"id": "val-1", "kind": "test", "required": True}]
    assert shown["comments"] == [{"body": "[handoff att-1] resume"}]
    argvs = [call["argv"] for call in fake.calls()]
    assert argvs == [["--token-file", str(agent), name, "--json", "--", "AWG-7"]
                     for name in ("show", "proof", "comments")]


def test_annotate_is_keyed_and_annotations_parse(awg) -> None:
    client, fake, _, _ = awg
    fake.reply("annotate", {"id": "an-1", "key": "pr-intent"})
    fake.reply("annotations", [{"key": "pr-intent", "data": {"branch": "maggy/AWG-7"}}])
    client.annotate(_claim(), "pr-intent", {"branch": "maggy/AWG-7"})
    listed = client.annotations("AWG-7")
    assert fake.calls()[0]["argv"][2:] == [
        "annotate", "--kind=custom", "--title=pr-intent", "--key=pr-intent",
        '--data={"branch": "maggy/AWG-7"}', "--json", "--", "AWG-7"]
    assert fake.calls()[1]["argv"][2:] == ["annotations", "--json", "--", "AWG-7"]
    assert listed[0]["data"] == {"branch": "maggy/AWG-7"}


def test_clients_satisfy_the_protocol(awg) -> None:
    assert isinstance(awg[0], AwgClient)


def test_same_file_for_both_credentials_is_refused(tmp_path: Path) -> None:
    agent, _ = token_files(tmp_path)
    with pytest.raises(ValueError, match="separate"):
        AwgCliConfig(binary=tmp_path / "awg", agent_token_file=agent, ci_token_file=agent)
