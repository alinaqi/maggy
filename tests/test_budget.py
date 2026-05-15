"""Tests for token budget manager."""

import pytest
from pathlib import Path

from maggy.budget import BudgetManager
from maggy.config import MaggyConfig, BudgetConfig, StorageConfig


@pytest.fixture
def manager(tmp_path: Path) -> BudgetManager:
    cfg = MaggyConfig(
        budget=BudgetConfig(daily_limit_usd=10.0, warning_threshold=0.8),
        storage=StorageConfig(path=str(tmp_path / "maggy.db")),
    )
    return BudgetManager(cfg)


class TestBudgetTracking:
    def test_initial_spend_zero(self, manager):
        assert manager.today_spend() == 0.0

    def test_record_and_read(self, manager):
        manager.record_spend("anthropic", "claude", 1.5)
        assert manager.today_spend() == 1.5

    def test_multiple_records(self, manager):
        manager.record_spend("anthropic", "claude", 1.0)
        manager.record_spend("openai", "gpt-4o", 0.5)
        assert manager.today_spend() == 1.5

    def test_filter_by_provider(self, manager):
        manager.record_spend("anthropic", "claude", 1.0)
        manager.record_spend("openai", "gpt-4o", 0.5)
        assert manager.today_spend("anthropic") == 1.0
        assert manager.today_spend("openai") == 0.5


class TestBudgetStatus:
    def test_ok_status(self, manager):
        manager.record_spend("anthropic", "claude", 1.0)
        status = manager.budget_status()
        assert status["status"] == "ok"
        assert status["spent_today_usd"] == 1.0

    def test_warning_status(self, manager):
        manager.record_spend("anthropic", "claude", 8.5)
        status = manager.budget_status()
        assert status["status"] == "warning"

    def test_exhausted_status(self, manager):
        manager.record_spend("anthropic", "claude", 10.0)
        status = manager.budget_status()
        assert status["status"] == "exhausted"


class TestByProvider:
    def test_breakdown(self, manager):
        manager.record_spend("anthropic", "claude", 2.0)
        manager.record_spend("openai", "gpt-4o", 1.0)
        breakdown = manager.by_provider()
        providers = {d["provider"] for d in breakdown}
        assert "anthropic" in providers
        assert "openai" in providers


class TestIsExhausted:
    def test_not_exhausted(self, manager):
        assert not manager.is_exhausted()

    def test_exhausted(self, manager):
        manager.record_spend("anthropic", "claude", 10.0)
        assert manager.is_exhausted()
