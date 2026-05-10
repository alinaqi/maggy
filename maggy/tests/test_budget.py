"""Tests for BudgetManager — spend tracking and status."""

from __future__ import annotations

from maggy.budget import BudgetManager


class TestBudgetTracking:
    def test_initial_spend_is_zero(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        assert bm.today_spend() == 0.0

    def test_record_and_read(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 0.5)
        assert bm.today_spend() >= 0.5

    def test_multiple_records_sum(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 0.3)
        bm.record_spend("openai", "gpt-4o", 0.2)
        assert bm.today_spend() >= 0.5


class TestBudgetStatus:
    def test_ok_status(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 1.0)
        status = bm.budget_status()
        assert status["status"] == "ok"

    def test_warning_status(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 8.5)
        status = bm.budget_status()
        assert status["status"] == "warning"

    def test_exhausted_status(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 10.0)
        status = bm.budget_status()
        assert status["status"] == "exhausted"


class TestByProvider:
    def test_breakdown(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 0.5)
        bm.record_spend("openai", "gpt-4o", 0.3)
        breakdown = bm.by_provider()
        assert len(breakdown) == 2
        providers = {r["provider"] for r in breakdown}
        assert "anthropic" in providers
        assert "openai" in providers


class TestIsExhausted:
    def test_not_exhausted(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        assert not bm.is_exhausted()

    def test_exhausted(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 11.0)
        assert bm.is_exhausted()
