"""Commit-bound evidence: bound to the item's CI `test` validation, attached once (RFC §2.4)."""

from __future__ import annotations

from pathlib import Path

from runner_loop_helpers import EDIT_AGENT, CAPS, make_rig
from runner_publish_helpers import result_for

from maggy.runner.evidence import attach_evidence
from maggy.runner.session import Session

VALIDATIONS = [{"id": "val-test", "kind": "test", "required": True, "min_trust": 3},
               {"id": "val-ac", "kind": "acceptance", "required": True, "min_trust": 2}]


def test_runner_binds_check_evidence_to_the_test_validation(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT)
    rig.awg.items[rig.ref].validations = [dict(v) for v in VALIDATIONS]
    assert rig.runner.run_once().outcome == "submitted"
    [evidence] = rig.awg.items[rig.ref].evidence
    assert evidence["validation"] == "val-test" and evidence["producer"] == "ci"


def test_evidence_without_a_test_validation_is_unbound(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT)
    rig.runner.run_once()
    [evidence] = rig.awg.items[rig.ref].evidence
    assert evidence["validation"] is None


def test_evidence_is_attached_once_and_recorded_as_intent_and_result(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT)
    session = Session(rig.awg, rig.awg.next_claim(CAPS), rig.runner.config)
    result = result_for("a" * 40)
    attach_evidence(session, result)
    attach_evidence(session, result)  # a roll-forward re-runs conclude
    assert len(rig.awg.items[rig.ref].evidence) == 1
    keys = [a["key"] for a in rig.awg.annotations(rig.ref)]
    prefix = f"{rig.ref}:{session.claim.attempt_id}:evidence:test:{'a' * 40}"
    assert [k for k in keys if ":evidence:" in k] == [prefix, f"{prefix}:result"]
