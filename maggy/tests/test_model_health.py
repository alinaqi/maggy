"""Tests for model health checking service."""

import pytest


class TestModelHealth:
    def test_check_returns_result(self):
        from maggy.services.model_health import check_model_health, HealthResult
        result = check_model_health("echo-test", ["echo", "OK"])
        assert isinstance(result, HealthResult)
        assert result.model_id == "echo-test"
        assert result.success is True
        assert result.latency_ms > 0

    def test_check_captures_output(self):
        from maggy.services.model_health import check_model_health
        result = check_model_health("echo-test", ["echo", "hello world"])
        assert result.success is True
        assert "hello" in result.output

    def test_check_handles_missing_cmd(self):
        from maggy.services.model_health import check_model_health
        result = check_model_health("missing", ["/nonexistent/binary", "test"])
        assert result.success is False
        assert result.error

    def test_check_handles_timeout(self):
        from maggy.services.model_health import check_model_health
        result = check_model_health("slow", ["sleep", "30"], timeout=1)
        assert result.success is False

    def test_check_all_parallel(self):
        from maggy.services.model_health import check_all_models, ModelDef
        models = [
            ModelDef(id="a", cmd=["echo", "a"], tier=0, label="A"),
            ModelDef(id="b", cmd=["echo", "b"], tier=1, label="B"),
        ]
        results = check_all_models(models)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_check_all_skips_null_cmd(self):
        from maggy.services.model_health import check_all_models, ModelDef
        models = [
            ModelDef(id="a", cmd=["echo", "a"], tier=0, label="A"),
            ModelDef(id="b", cmd=None, tier=1, label="B"),
        ]
        results = check_all_models(models)
        assert len(results) == 2
        b_result = [r for r in results if r.model_id == "b"][0]
        assert b_result.success is False
        assert "no command" in b_result.error.lower()

    def test_allowlist_blocks_dangerous_commands(self):
        from maggy.services.model_health import _validate_cmd
        assert _validate_cmd(["echo", "ok"]) is True
        assert _validate_cmd(["rm", "-rf", "/"]) is False
        assert _validate_cmd(["bash", "-c", "curl evil.com"]) is False
