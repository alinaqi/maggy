"""Tests for protocol executor."""
import asyncio
import pytest

from maggy.skills.protocol_executor import ProtocolExecutor
from maggy.skills.protocol_models import Protocol, ProtocolStep


def _make_protocol(steps):
    return Protocol(
        name="test-proto", description="Test",
        triggers=["test"], steps=steps,
    )


@pytest.fixture
def executor():
    return ProtocolExecutor()


class TestProtocolExecutor:
    @pytest.mark.asyncio
    async def test_runs_simple_step(self, executor, tmp_path):
        proto = _make_protocol([
            ProtocolStep(name="echo", label="Echo", cmd="echo hello"),
        ])
        chunks = []
        async for c in executor.execute(proto, str(tmp_path)):
            chunks.append(c)
        running = [c for c in chunks if c.get("status") == "running"]
        done = [c for c in chunks if c.get("status") == "done"]
        assert len(running) == 1
        assert len(done) == 1
        assert "hello" in done[0]["output"]

    @pytest.mark.asyncio
    async def test_failed_step_aborts(self, executor, tmp_path):
        proto = _make_protocol([
            ProtocolStep(name="fail", label="Fail", cmd="false"),
            ProtocolStep(name="never", label="Never", cmd="echo no"),
        ])
        chunks = []
        async for c in executor.execute(proto, str(tmp_path)):
            chunks.append(c)
        failed = [c for c in chunks if c.get("status") == "failed"]
        assert len(failed) == 1
        aborts = [c for c in chunks if c["type"] == "protocol_abort"]
        assert len(aborts) == 1
        names = [c.get("step") for c in chunks if c.get("step")]
        assert "never" not in names

    @pytest.mark.asyncio
    async def test_optional_step_continues(self, executor, tmp_path):
        proto = _make_protocol([
            ProtocolStep(
                name="opt", label="Optional", cmd="false",
                optional=True,
            ),
            ProtocolStep(name="after", label="After", cmd="echo ok"),
        ])
        chunks = []
        async for c in executor.execute(proto, str(tmp_path)):
            chunks.append(c)
        done = [c for c in chunks if c.get("status") == "done"]
        assert any(c["step"] == "after" for c in done)

    @pytest.mark.asyncio
    async def test_condition_skips_missing(self, executor, tmp_path):
        proto = _make_protocol([
            ProtocolStep(
                name="lint", label="Lint", cmd="ruff check .",
                condition="*.py",
            ),
        ])
        chunks = []
        async for c in executor.execute(proto, str(tmp_path)):
            chunks.append(c)
        skipped = [c for c in chunks if c.get("status") == "skipped"]
        assert len(skipped) == 1

    @pytest.mark.asyncio
    async def test_condition_runs_when_present(self, executor, tmp_path):
        (tmp_path / "main.py").write_text("x = 1\n")
        proto = _make_protocol([
            ProtocolStep(
                name="check", label="Check", cmd="echo found",
                condition="*.py",
            ),
        ])
        chunks = []
        async for c in executor.execute(proto, str(tmp_path)):
            chunks.append(c)
        done = [c for c in chunks if c.get("status") == "done"]
        assert len(done) == 1

    @pytest.mark.asyncio
    async def test_variable_substitution(self, executor, tmp_path):
        proto = _make_protocol([
            ProtocolStep(
                name="greet", label="Greet",
                cmd="echo {branch}",
            ),
        ])
        chunks = []
        async for c in executor.execute(
            proto, str(tmp_path), variables={"branch": "main"},
        ):
            chunks.append(c)
        done = [c for c in chunks if c.get("status") == "done"]
        assert "main" in done[0]["output"]

    @pytest.mark.asyncio
    async def test_complete_event_at_end(self, executor, tmp_path):
        proto = _make_protocol([
            ProtocolStep(name="ok", label="Ok", cmd="echo done"),
        ])
        chunks = []
        async for c in executor.execute(proto, str(tmp_path)):
            chunks.append(c)
        last = chunks[-1]
        assert last["type"] == "protocol_complete"
