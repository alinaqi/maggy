"""CliAwgClient maps awg failures to typed errors and never leaks token secrets."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from maggy.runner.awg_cli import CliAwgClient
from maggy.runner.awg_client import (
    AwgCliConfig,
    AwgError,
    AwgUnavailable,
    Claim,
    EvidenceSpec,
    FenceStale,
    LeaseLost,
    NotFound,
    Unauthorized,
)
from tests.runner_awg_helpers import AGENT_SECRET, CI_SECRET, LEASE, FakeAwgBin, token_files

CLAIM = Claim(ref="AWG-7", work_id="n", attempt_id="att-1", fencing_token=4,
              lease_expires=1.0, version=1)


def _client(tmp_path: Path, binary: Path | None = None) -> tuple[CliAwgClient, FakeAwgBin]:
    fake = FakeAwgBin(tmp_path)
    agent, ci = token_files(tmp_path)
    config = AwgCliConfig(binary=binary or fake.path, agent_token_file=agent, ci_token_file=ci)
    return CliAwgClient(config), fake


@pytest.mark.parametrize(("reply", "error"), [
    ({"stderr": "awg: stale_fencing_token: fencing token is not the live lease\n"}, FenceStale),
    ({"stderr": "awg: no lease held on AWG-7 from this machine; claim it first\n"}, LeaseLost),
    ({"stderr": "awg: unauthorized: bad token\n"}, Unauthorized),
    ({"stderr": "awg: forbidden: scope\n"}, Unauthorized),
    ({"stderr": "awg: not_found: no such work\n"}, NotFound),
    ({"stderr": "awg: unavailable: db busy\n"}, AwgUnavailable),
    ({"stdout": json.dumps({"error": {"code": "stale_fencing_token", "message": "x"}})},
     FenceStale),
    ({"stderr": "Traceback: boom\n"}, AwgError),
])
def test_failures_map_to_typed_errors(tmp_path: Path, reply: dict, error: type) -> None:
    client, fake = _client(tmp_path)
    fake.replies["heartbeat"] = {"rc": 1, **reply}
    fake._save()
    with pytest.raises(error):
        client.heartbeat(CLAIM)


def test_fence_stale_is_a_lease_loss() -> None:
    assert issubclass(FenceStale, LeaseLost)


def test_unparseable_success_output_is_an_error(tmp_path: Path) -> None:
    client, fake = _client(tmp_path)
    fake.replies["show"] = {"rc": 0, "stdout": "not json"}
    fake._save()
    with pytest.raises(AwgError, match="JSON"):
        client.show("AWG-7")


def test_missing_binary_is_unavailable(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, binary=tmp_path / "missing-awg")
    with pytest.raises(AwgUnavailable):
        client.show("AWG-7")


def test_no_secret_in_argv_env_or_logs(tmp_path: Path, monkeypatch, caplog) -> None:
    monkeypatch.setenv("AWG_TOKEN", "ambient-owner-token")
    client, fake = _client(tmp_path)
    fake.reply("next", LEASE)
    fake.reply("heartbeat", rc=1, stderr="awg: unauthorized: bad token\n")
    caplog.set_level(logging.DEBUG)
    claim = client.next_claim(["maggy-runner"])
    client.evidence(claim, EvidenceSpec(kind="test", verdict="PASS", commit_sha="abc"))
    with pytest.raises(Unauthorized) as raised:
        client.heartbeat(claim)
    recorded = json.dumps(fake.calls()) + caplog.text + str(raised.value)
    assert AGENT_SECRET not in recorded and CI_SECRET not in recorded
    assert all(call["env_token"] is None for call in fake.calls())
    assert "ambient-owner-token" not in recorded
