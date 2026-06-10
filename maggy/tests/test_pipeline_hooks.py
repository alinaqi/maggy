"""Tests for pipeline post-send hooks."""

from unittest.mock import MagicMock

from maggy.pipeline.hooks import record_outcome, record_spend
from maggy.pipeline.models import PipelineResult


def _result(**kw):
    defaults = dict(
        model="claude", backend="claude", blast=5,
        task_type="general", reason="default",
        latency_ms=1000, cost_usd=0.03,
        tokens_in=500, tokens_out=200, success=True,
    )
    defaults.update(kw)
    return PipelineResult(**defaults)


class TestRecordSpend:
    def test_records_cost(self):
        budget = MagicMock()
        record_spend(budget, _result(cost_usd=0.05, tokens_in=100, tokens_out=50))
        budget.record_spend.assert_called_once_with(
            "anthropic", "claude", 0.05, 100, 50,
        )

    def test_skips_when_no_budget(self):
        record_spend(None, _result())

    def test_skips_zero_cost(self):
        budget = MagicMock()
        record_spend(budget, _result(cost_usd=0.0, tokens_in=0, tokens_out=0))
        budget.record_spend.assert_not_called()


class TestRecordOutcome:
    def test_records_success(self):
        routing = MagicMock()
        record_outcome(routing, _result(success=True, blast=7))
        routing.record_outcome.assert_called_once_with(
            "claude", "general", 7, 1.0,
        )

    def test_records_failure(self):
        routing = MagicMock()
        record_outcome(routing, _result(success=False, blast=3))
        routing.record_outcome.assert_called_once_with(
            "claude", "general", 3, 0.0,
        )

    def test_skips_when_no_routing(self):
        record_outcome(None, _result())
