"""Tests for BudgetManager — spend tracking and status."""

from __future__ import annotations

from maggy.budget import ProviderBudget, TaskSpendTracker
from maggy.config import BudgetConfig
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


class TestProviderBudgets:
    def test_provider_exhaustion_uses_provider_limit(self, mock_cfg):
        mock_cfg.budget = BudgetConfig(
            daily_limit_usd=20.0,
            providers=[
                ProviderBudget("moonshot", 1.0, "kimi"),
                ProviderBudget("openai", 5.0, "gpt"),
            ],
        )
        bm = BudgetManager(mock_cfg)
        bm.record_spend("moonshot", "kimi", 1.1)
        assert bm.is_provider_exhausted("moonshot")
        assert not bm.is_provider_exhausted("openai")

    def test_cheapest_available_skips_exhausted_provider(self, mock_cfg):
        mock_cfg.budget = BudgetConfig(
            providers=[
                ProviderBudget("moonshot", 1.0, "kimi"),
                ProviderBudget("openai", 5.0, "gpt"),
            ],
        )
        bm = BudgetManager(mock_cfg)
        bm.record_spend("moonshot", "kimi", 1.0)
        assert bm.cheapest_available() == "gpt"


class TestTokenTracking:
    def test_initial_tokens_zero(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        tokens = bm.today_tokens()
        assert tokens == {"input": 0, "output": 0}

    def test_record_and_read_tokens(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 0.5, 1000, 500)
        bm.record_spend("openai", "gpt-4o", 0.3, 2000, 800)
        tokens = bm.today_tokens()
        assert tokens["input"] == 3000
        assert tokens["output"] == 1300

    def test_tokens_by_provider(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 0.5, 1000, 500)
        bm.record_spend("openai", "gpt", 0.3, 2000, 800)
        tokens = bm.today_tokens("anthropic")
        assert tokens["input"] == 1000

    def test_budget_status_includes_tokens(self, mock_cfg):
        bm = BudgetManager(mock_cfg)
        bm.record_spend("anthropic", "claude", 0.5, 1500, 600)
        status = bm.budget_status()
        assert status["input_tokens"] == 1500
        assert status["output_tokens"] == 600


class TestTaskSpendTracker:
    def test_records_total_cost(self) -> None:
        tracker = TaskSpendTracker(5.0)
        tracker.record(1.5)
        tracker.record(0.5)
        assert tracker.total() == 2.0

    def test_detects_exceeded_spend(self) -> None:
        tracker = TaskSpendTracker(2.0)
        tracker.record(2.0)
        assert tracker.is_exceeded()

    def test_tracks_edit_loops(self) -> None:
        tracker = TaskSpendTracker(5.0)
        for _ in range(4):
            tracker.record_edit("maggy/services/planner.py")
        tracker.record_edit("maggy/budget.py")
        assert tracker.detect_loop() == ["maggy/services/planner.py"]

    def test_budget_config_has_task_limit(self) -> None:
        cfg = BudgetConfig(max_spend_per_task=3.5)
        assert cfg.max_spend_per_task == 3.5
