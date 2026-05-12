"""Tests for cascade execution — quality-gate-based model escalation."""

from __future__ import annotations

import pytest

from maggy.adapters.pi import PiAdapter, RunResult
from maggy.services.cascade import cascade_execute


class TestCascadeNoEscalation:
    @pytest.mark.asyncio
    async def test_first_model_passes(self):
        pi = PiAdapter()
        calls: list[str] = []

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            calls.append(model_name)
            return RunResult(model=model_name, success=True, output="good")

        pi.send_prompt = fake_send

        async def good_gate(output: str) -> int:
            return 4

        result = await cascade_execute(
            pi, ["local", "gpt", "claude"], "test", "/tmp", good_gate,
        )
        assert result.model == "local"
        assert not result.escalated
        assert len(calls) == 1


class TestCascadeEscalation:
    @pytest.mark.asyncio
    async def test_low_quality_escalates(self):
        pi = PiAdapter()
        calls: list[str] = []

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            calls.append(model_name)
            return RunResult(model=model_name, success=True, output="ok")

        pi.send_prompt = fake_send
        scores = iter([2, 4])

        async def improving_gate(output: str) -> int:
            return next(scores)

        result = await cascade_execute(
            pi, ["local", "gpt", "claude"], "test", "/tmp",
            improving_gate,
        )
        assert result.model == "gpt"
        assert result.escalated
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_max_3_attempts(self):
        pi = PiAdapter()
        calls: list[str] = []

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            calls.append(model_name)
            return RunResult(model=model_name, success=True, output="bad")

        pi.send_prompt = fake_send

        async def always_bad(output: str) -> int:
            return 1

        result = await cascade_execute(
            pi, ["local", "gpt", "claude"], "test", "/tmp", always_bad,
        )
        assert len(result.attempts) == 3
        # All scored equally — returns best (first with highest score)
        assert len(calls) == 3


class TestCascadeFailure:
    @pytest.mark.asyncio
    async def test_send_failure_escalates(self):
        pi = PiAdapter()
        calls: list[str] = []

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            calls.append(model_name)
            if model_name == "local":
                return RunResult(
                    model=model_name, success=False, error="crash",
                )
            return RunResult(model=model_name, success=True, output="ok")

        pi.send_prompt = fake_send

        async def ok_gate(output: str) -> int:
            return 4

        result = await cascade_execute(
            pi, ["local", "gpt"], "test", "/tmp", ok_gate,
        )
        assert result.model == "gpt"
        assert result.escalated

    @pytest.mark.asyncio
    async def test_single_model_no_escalation(self):
        pi = PiAdapter()

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            return RunResult(model=model_name, success=True, output="ok")

        pi.send_prompt = fake_send

        async def low_gate(output: str) -> int:
            return 2

        result = await cascade_execute(
            pi, ["claude"], "test", "/tmp", low_gate,
        )
        assert result.model == "claude"
        assert len(result.attempts) == 1


class TestCascadeAttemptTracking:
    @pytest.mark.asyncio
    async def test_attempts_recorded(self):
        pi = PiAdapter()

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            return RunResult(model=model_name, success=True, output="ok")

        pi.send_prompt = fake_send
        scores = iter([1, 4])

        async def gate(output: str) -> int:
            return next(scores)

        result = await cascade_execute(
            pi, ["local", "gpt"], "test", "/tmp", gate,
        )
        assert len(result.attempts) == 2
        assert result.attempts[0].model == "local"
        assert result.attempts[0].score == 1
        assert result.attempts[1].model == "gpt"
        assert result.attempts[1].score == 4
