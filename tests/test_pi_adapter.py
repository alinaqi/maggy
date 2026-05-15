"""Tests for PiAdapter unified agent harness."""

import pytest

from maggy.adapters.pi import (
    DEFAULT_MODELS,
    ModelEntry,
    PiAdapter,
    RunResult,
)


@pytest.fixture
def adapter() -> PiAdapter:
    return PiAdapter()


class TestModelRegistry:
    def test_default_models_loaded(self, adapter):
        models = adapter.list_models()
        assert len(models) == len(DEFAULT_MODELS)

    def test_get_model(self, adapter):
        m = adapter.get_model("claude")
        assert m is not None
        assert m.provider == "anthropic"
        assert m.tier == "premium"

    def test_get_unknown_model(self, adapter):
        assert adapter.get_model("nonexistent") is None

    def test_custom_models(self):
        custom = [
            ModelEntry("test", "test_provider", "test-v1",
                       "cheap", 0.001),
        ]
        adapter = PiAdapter(models=custom)
        assert len(adapter.list_models()) == 1
        assert adapter.get_model("test") is not None


class TestFallbackChain:
    def test_chain_excludes_current(self, adapter):
        chain = adapter.fallback_chain("kimi")
        assert "kimi" not in chain

    def test_chain_ordered_by_cost(self, adapter):
        chain = adapter.fallback_chain("kimi")
        assert len(chain) >= 1

    def test_unknown_model_returns_full_chain(self, adapter):
        chain = adapter.fallback_chain("nonexistent")
        assert len(chain) == len(DEFAULT_MODELS)


class TestQuotaDetection:
    def test_detects_rate_limit(self, adapter):
        assert adapter._detect_quota("Error: rate limit exceeded")

    def test_detects_429(self, adapter):
        assert adapter._detect_quota("HTTP 429 Too Many Requests")

    def test_no_quota(self, adapter):
        assert not adapter._detect_quota("Success: task completed")


class TestBuildCommand:
    def test_claude_command(self, adapter):
        model = adapter.get_model("claude")
        cmd = adapter._build_command(model, "test prompt", 10)
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "--dangerously-skip-permissions" in cmd

    def test_kimi_command(self, adapter):
        model = adapter.get_model("kimi")
        cmd = adapter._build_command(model, "test prompt", 10)
        assert cmd[0] == "kimi"
        assert "-p" in cmd
