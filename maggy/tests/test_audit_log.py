"""Tests for council audit log (SQLite)."""

import pytest
from pathlib import Path

from maggy.council.models import (
    BlastAnalysis, DeliberationResult, ExecutionDecision,
    ReviewerVote, ValidationClassification
)


@pytest.fixture
def log_db(tmp_path):
    from maggy.council.audit_log import AuditLog
    return AuditLog(tmp_path / "audit.db")


def _sample_deliberation() -> DeliberationResult:
    votes = [
        ReviewerVote("ds", 1, "APPROVE", "solid"),
        ReviewerVote("kimi", 1, "APPROVE", "lgtm"),
    ]
    return DeliberationResult(
        final_votes=votes, rounds_needed=1, threshold=2
    )


def _sample_blast() -> BlastAnalysis:
    return BlastAnalysis(2, 5, 1, 0.85)


def _sample_decision() -> ExecutionDecision:
    return ExecutionDecision("AUTO_EXECUTE", "low blast, objective")


class TestAuditLogRecord:
    def test_record_and_retrieve(self, log_db):
        log_db.record(
            "test-session", _sample_deliberation(),
            _sample_blast(), _sample_decision()
        )
        rows = log_db.recent(limit=5)
        assert len(rows) == 1
        assert rows[0]["action"] == "AUTO_EXECUTE"
        assert rows[0]["session_id"] == "test-session"

    def test_multiple_records(self, log_db):
        for i in range(3):
            log_db.record(
                f"sess-{i}", _sample_deliberation(),
                _sample_blast(), _sample_decision()
            )
        rows = log_db.recent(limit=10)
        assert len(rows) == 3

    def test_recent_respects_limit(self, log_db):
        for i in range(5):
            log_db.record(
                f"sess-{i}", _sample_deliberation(),
                _sample_blast(), _sample_decision()
            )
        rows = log_db.recent(limit=2)
        assert len(rows) == 2

    def test_filter_by_session(self, log_db):
        log_db.record(
            "alpha", _sample_deliberation(),
            _sample_blast(), _sample_decision()
        )
        log_db.record(
            "beta", _sample_deliberation(),
            _sample_blast(), _sample_decision()
        )
        rows = log_db.recent(limit=10, session_id="alpha")
        assert len(rows) == 1
        assert rows[0]["session_id"] == "alpha"

    def test_stats(self, log_db):
        log_db.record(
            "s1", _sample_deliberation(),
            _sample_blast(), _sample_decision()
        )
        stats = log_db.stats()
        assert stats["total"] == 1
        assert stats["auto_executed"] >= 0
