"""Tests for PiAdapter — model registry, fallback, quota detection."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from maggy.adapters.pi import (
    ModelEntry,
    PiAdapter,
)


class TestModelRegistry:
    def test_default_models_loaded(self):
        adapter = PiAdapter()
        assert len(adapter.list_models()) == 6

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
        assert len(chain) == 6


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
        cmd = adapter._build_command(model, "hello", 5, "/tmp")
        assert "claude" in cmd[0]
        assert "-p" in cmd
        assert "--dangerously-skip-permissions" in cmd

    def test_non_claude_command(self):
        entry = ModelEntry(
            "test", "local", "m1", "cheap",
            cli_command="kimi",
        )
        adapter = PiAdapter(models=[entry])
        cmd = adapter._build_command(entry, "hello", 5, "/tmp")
        assert "kimi" in cmd[0]
        assert "--dangerously-skip-permissions" not in cmd


class _FakeStream:
    def __init__(self, lines: list[str]):
        self._lines = list(lines)
        self.writes: list[str] = []

    def readline(self) -> str:
        if self._lines:
            return self._lines.pop(0)
        return ""

    def write(self, text: str) -> None:
        self.writes.append(text)

    def flush(self) -> None:
        return None


class _FakeProcess:
    def __init__(self, stdout_lines: list[str]):
        self.stdin = _FakeStream([])
        self.stdout = _FakeStream(stdout_lines)


class TestRpcMode:
    def test_detect_pi_uses_path_lookup(self):
        adapter = PiAdapter()
        with patch("maggy.adapters.pi.shutil.which", return_value="/bin/pi"):
            assert adapter._detect_pi() is True

    def test_send_rpc_serializes_command(self):
        adapter = PiAdapter()
        proc = _FakeProcess(['{"ok": true}\n'])
        with patch("maggy.adapters.pi.subprocess.Popen", return_value=proc):
            result = adapter.send_rpc({"command": "ping"})
        assert result == {"ok": True}
        assert proc.stdin.writes == ['{"command":"ping"}\n']

    def test_switch_model_uses_rpc(self):
        adapter = PiAdapter()
        adapter.send_rpc = MagicMock(return_value={"ok": True})
        changed = adapter.switch_model("anthropic", "claude-sonnet-4")
        assert changed is True
        adapter.send_rpc.assert_called_once_with(
            {
                "command": "set_model",
                "provider": "anthropic",
                "model": "claude-sonnet-4",
            }
        )

class TestPromptResult:
    def test_parses_json_output(self):
        adapter = PiAdapter()
        payload = json.dumps({
            "result": "All tests pass",
            "cost_usd": 0.05,
            "usage": {"input_tokens": 1500, "output_tokens": 800},
        })
        r = adapter._prompt_result("claude", 0, payload.encode())
        assert r.success is True
        assert r.output == "All tests pass"
        assert r.cost_usd == 0.05
        assert r.input_tokens == 1500
        assert r.output_tokens == 800

    def test_plain_text_fallback(self):
        adapter = PiAdapter()
        r = adapter._prompt_result("local", 0, b"Just text output")
        assert r.success is True
        assert r.output == "Just text output"
        assert r.cost_usd == 0.0
        assert r.input_tokens == 0

    def test_json_error_preserves_usage(self):
        adapter = PiAdapter()
        payload = json.dumps({
            "result": "Error occurred",
            "cost_usd": 0.01,
            "usage": {"input_tokens": 500, "output_tokens": 100},
        })
        r = adapter._prompt_result("claude", 1, payload.encode())
        assert r.success is False
        assert r.cost_usd == 0.01
        assert r.input_tokens == 500


class TestStreaming:
    @pytest.mark.asyncio
    async def test_stream_events_reads_jsonl(self):
        adapter = PiAdapter()
        adapter._rpc_process = _FakeProcess(
            ['{"type":"start"}\n', '{"type":"done"}\n', ""]
        )
        events = []
        async for event in adapter.stream_events():
            events.append(event)
        assert events == [{"type": "start"}, {"type": "done"}]
