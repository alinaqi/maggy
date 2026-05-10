"""Tests for heartbeat scheduler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from maggy.heartbeat.scheduler import HeartbeatScheduler, Job


# ── Job dataclass ────────────────────────────────────────────────────────


class TestJob:
    def test_defaults(self):
        fn = AsyncMock()
        job = Job(name="test", fn=fn, interval_seconds=60)
        assert job.name == "test"
        assert job.interval_seconds == 60
        assert job.run_count == 0
        assert job.last_run == ""
        assert job.last_error == ""
        assert job.enabled is True

    def test_is_due_no_last_run(self):
        fn = AsyncMock()
        job = Job(name="test", fn=fn, interval_seconds=60)
        assert job.is_due() is True

    def test_is_due_after_interval(self):
        from datetime import datetime, timezone, timedelta
        fn = AsyncMock()
        job = Job(name="test", fn=fn, interval_seconds=60)
        past = datetime.now(timezone.utc) - timedelta(seconds=120)
        job.last_run = past.isoformat()
        assert job.is_due() is True

    def test_not_due_before_interval(self):
        from datetime import datetime, timezone
        fn = AsyncMock()
        job = Job(name="test", fn=fn, interval_seconds=3600)
        job.last_run = datetime.now(timezone.utc).isoformat()
        assert job.is_due() is False


# ── Scheduler ────────────────────────────────────────────────────────────


class TestSchedulerRegister:
    def test_register_job(self):
        sched = HeartbeatScheduler()
        fn = AsyncMock()
        sched.register("refresh", fn, 1800)
        assert "refresh" in sched._jobs

    def test_register_duplicate_raises(self):
        sched = HeartbeatScheduler()
        fn = AsyncMock()
        sched.register("dupe", fn, 60)
        with pytest.raises(ValueError, match="already registered"):
            sched.register("dupe", fn, 60)

    def test_status_returns_list(self):
        sched = HeartbeatScheduler()
        fn = AsyncMock()
        sched.register("a", fn, 60)
        sched.register("b", fn, 120)
        result = sched.status()
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"a", "b"}


class TestSchedulerTick:
    @pytest.mark.asyncio
    async def test_tick_runs_due_jobs(self):
        sched = HeartbeatScheduler()
        fn = AsyncMock()
        sched.register("job1", fn, 0)
        await sched.tick()
        fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tick_skips_disabled(self):
        sched = HeartbeatScheduler()
        fn = AsyncMock()
        sched.register("disabled", fn, 0)
        sched._jobs["disabled"].enabled = False
        await sched.tick()
        fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_tick_records_error(self):
        sched = HeartbeatScheduler()
        fn = AsyncMock(side_effect=RuntimeError("boom"))
        sched.register("fail", fn, 0)
        await sched.tick()
        assert "boom" in sched._jobs["fail"].last_error

    @pytest.mark.asyncio
    async def test_tick_increments_count(self):
        sched = HeartbeatScheduler()
        fn = AsyncMock()
        sched.register("counter", fn, 0)
        await sched.tick()
        await sched.tick()
        assert sched._jobs["counter"].run_count == 2


class TestSchedulerTrigger:
    @pytest.mark.asyncio
    async def test_trigger_runs_job(self):
        sched = HeartbeatScheduler()
        fn = AsyncMock(return_value=None)
        sched.register("manual", fn, 9999)
        result = await sched.trigger("manual")
        fn.assert_awaited_once()
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_trigger_unknown_raises(self):
        sched = HeartbeatScheduler()
        with pytest.raises(KeyError, match="nope"):
            await sched.trigger("nope")


class TestSchedulerLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        sched = HeartbeatScheduler()
        fn = AsyncMock()
        sched.register("tick_job", fn, 0)
        await sched.start()
        assert sched._task is not None
        await asyncio.sleep(0.05)
        await sched.stop()
        assert sched._task is None
        assert fn.await_count >= 1


# ── Jobs ─────────────────────────────────────────────────────────────────


class TestJobs:
    @pytest.mark.asyncio
    async def test_refresh_history_calls_analyze(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from maggy.heartbeat.jobs import refresh_history
        history = MagicMock()
        app = SimpleNamespace(state=SimpleNamespace(history=history))
        await refresh_history(app)
        history.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_history_skips_none(self):
        from types import SimpleNamespace
        from maggy.heartbeat.jobs import refresh_history
        app = SimpleNamespace(state=SimpleNamespace(history=None))
        await refresh_history(app)  # no error

    @pytest.mark.asyncio
    async def test_self_improve_calls_analyze(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from maggy.heartbeat.jobs import self_improve
        intro = MagicMock()
        app = SimpleNamespace(state=SimpleNamespace(introspector=intro))
        await self_improve(app)
        intro.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_self_improve_skips_none(self):
        from types import SimpleNamespace
        from maggy.heartbeat.jobs import self_improve
        app = SimpleNamespace(state=SimpleNamespace(introspector=None))
        await self_improve(app)  # no error
