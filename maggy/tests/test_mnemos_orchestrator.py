"""Tests for orchestrator signals."""

from maggy.mnemos.models import CheckpointData, ConflictRecord, FatigueState
from maggy.mnemos.orchestrator import (
    OrchestratorSignal,
    emit_checkpoint_signal,
    emit_delegation_signal,
    emit_fatigue_report,
    emit_merge_conflict_signal,
    emit_rem_signal,
    read_orchestrator_signals,
)


class TestOrchestratorSignal:
    def test_auto_timestamp(self):
        s = OrchestratorSignal(
            signal_type="TEST", payload={},
        )
        assert s.timestamp != ""

    def test_default_source(self):
        s = OrchestratorSignal(
            signal_type="TEST", payload={},
        )
        assert s.source_agent == "primary"


class TestEmitFatigueReport:
    def test_creates_signal(self, tmp_mnemos_dir):
        fs = FatigueState(score=0.5, token_util=0.5)
        sig = emit_fatigue_report(fs, tmp_mnemos_dir)
        assert sig.signal_type == "FATIGUE_REPORT"
        assert sig.payload["score"] == 0.5


class TestEmitCheckpoint:
    def test_creates_signal(self, tmp_mnemos_dir):
        cp = CheckpointData(
            task_id="t1", fatigue=0.6,
            summary="test", graph_json={},
        )
        sig = emit_checkpoint_signal(cp, tmp_mnemos_dir)
        assert sig.signal_type == "CHECKPOINT_WRITTEN"


class TestEmitRem:
    def test_creates_signal(self, tmp_mnemos_dir):
        stats = {"compressed": 5}
        sig = emit_rem_signal(stats, tmp_mnemos_dir)
        assert sig.signal_type == "REM_COMPLETED"


class TestEmitDelegation:
    def test_creates_signal(self, tmp_mnemos_dir):
        sig = emit_delegation_signal(
            "task-1", ["auth"], tmp_mnemos_dir,
        )
        assert sig.signal_type == "DELEGATION_REQUEST"
        assert sig.payload["task_id"] == "task-1"


class TestEmitMergeConflict:
    def test_creates_signal(self, tmp_mnemos_dir):
        conflicts = [
            ConflictRecord(
                node_a_id="a", node_b_id="b",
                conflict_type="CONTENT", resolution="kept a",
            ),
        ]
        sig = emit_merge_conflict_signal(conflicts, tmp_mnemos_dir)
        assert sig.signal_type == "MERGE_CONFLICT"
        assert sig.payload["count"] == 1


class TestReadSignals:
    def test_roundtrip(self, tmp_mnemos_dir):
        fs = FatigueState(score=0.5, token_util=0.5)
        emit_fatigue_report(fs, tmp_mnemos_dir)
        signals = read_orchestrator_signals(tmp_mnemos_dir)
        assert len(signals) == 1

    def test_empty(self, tmp_mnemos_dir):
        assert read_orchestrator_signals(tmp_mnemos_dir) == []
