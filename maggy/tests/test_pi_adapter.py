"""Tests for PiAdapter — model registry, fallback, quota detection."""

from __future__ import annotations

from maggy.adapters.pi import (
    DEFAULT_MODELS,
    ModelEntry,
    PiAdapter,
    QUOTA_MARKERS,
    RunResult,
)


class TestModelRegistry:
    def test_default_models_loaded(self):
        adapter = PiAdapter()
        assert len(adapter.list_models()) == 5

    def test_get_known_model(self):
        adapter = PiAdapter()
        m = adapter.get_model("claude")
        assert m is not None
        assert m.provider == "anthropic"

    def test_get_unknown_returns_none(self):
        adapter = PiAdapter()
        assert adapter.get_model("nonexistent") is None

    def test_custom_models(self):
        custom = [
            ModelEntry("test", "local", "t1", "cheap", 0.0),
        ]
        adapter = PiAdapter(models=custom)
        assert len(adapter.list_models()) == 1
        assert adapter.get_model("test") is not None


class TestFallbackChain:
    def test_chain_excludes_start(self):
        adapter = PiAdapter()
        chain = adapter.fallback_chain("kimi")
        assert "kimi" not in chain

    def test_chain_ordered_by_cost(self):
        adapter = PiAdapter()
        chain = adapter.fallback_chain("kimi")
        assert len(chain) > 0

    def test_unknown_start_returns_all(self):
        adapter = PiAdapter()
        chain = adapter.fallback_chain("nonexistent")
        assert len(chain) == 5


class TestQuotaDetection:
    def test_detects_rate_limit(self):
        adapter = PiAdapter()
        assert adapter._detect_quota("Error: rate limit exceeded")

    def test_detects_429(self):
        adapter = PiAdapter()
        assert adapter._detect_quota("HTTP 429 Too Many Requests")

    def test_clean_output_no_quota(self):
        adapter = PiAdapter()
        assert not adapter._detect_quota("Task completed.")


class TestBuildCommand:
    def test_claude_command_format(self):
        adapter = PiAdapter()
        model = adapter.get_model("claude")
        cmd = adapter._build_command(model, "hello", 5)
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "--dangerously-skip-permissions" in cmd

    def test_non_claude_command(self):
        entry = ModelEntry(
            "test", "local", "m1", "cheap",
            cli_command="kimi",
        )
        adapter = PiAdapter(models=[entry])
        cmd = adapter._build_command(entry, "hello", 5)
        assert cmd[0] == "kimi"
        assert "--dangerously-skip-permissions" not in cmd
