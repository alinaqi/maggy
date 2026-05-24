"""Tests for pipeline data models."""

from maggy.pipeline.models import PipelineContext, PipelineResult


class TestPipelineContext:
    def test_required_fields(self):
        ctx = PipelineContext(
            session_id="abc123",
            message="hello world",
            project_key="myproj",
            working_dir="/tmp/work",
        )
        assert ctx.session_id == "abc123"
        assert ctx.message == "hello world"
        assert ctx.project_key == "myproj"
        assert ctx.working_dir == "/tmp/work"

    def test_optional_defaults(self):
        ctx = PipelineContext(
            session_id="x", message="y",
            project_key="", working_dir="/tmp",
        )
        assert ctx.blast_override is None
        assert ctx.task_type_override is None
        assert ctx.allowed_models is None

    def test_overrides(self):
        ctx = PipelineContext(
            session_id="x", message="y",
            project_key="", working_dir="/tmp",
            blast_override=7,
            task_type_override="security",
            allowed_models=["claude", "deepseek-pro"],
        )
        assert ctx.blast_override == 7
        assert ctx.task_type_override == "security"
        assert ctx.allowed_models == ["claude", "deepseek-pro"]


class TestPipelineResult:
    def test_required_fields(self):
        r = PipelineResult(
            model="claude", backend="claude",
            blast=5, task_type="general",
            reason="default", latency_ms=1200.0,
            cost_usd=0.03, tokens_in=500,
            tokens_out=200, success=True,
        )
        assert r.model == "claude"
        assert r.backend == "claude"
        assert r.blast == 5
        assert r.latency_ms == 1200.0
        assert r.success is True

    def test_optional_defaults(self):
        r = PipelineResult(
            model="kimi", backend="pi",
            blast=2, task_type="search",
            reason="low blast", latency_ms=300.0,
            cost_usd=0.001, tokens_in=100,
            tokens_out=50, success=True,
        )
        assert r.error == ""
        assert r.fallback_used == ""

    def test_error_result(self):
        r = PipelineResult(
            model="deepseek-flash", backend="pi",
            blast=3, task_type="general",
            reason="cheap", latency_ms=5000.0,
            cost_usd=0.0, tokens_in=0,
            tokens_out=0, success=False,
            error="CLI timed out",
            fallback_used="claude",
        )
        assert r.success is False
        assert r.error == "CLI timed out"
        assert r.fallback_used == "claude"
