"""Tests for inter-task output reviewer."""

from __future__ import annotations

import pytest

from maggy.services.output_reviewer import (
    _parse_review,
    review_output,
)


class TestParseReview:
    def test_parses_score_and_reason(self):
        text = "SCORE: 4\nREASON: Clean implementation"
        result = _parse_review(text)
        assert result.score == 4
        assert result.reason == "Clean implementation"

    def test_parses_score_only(self):
        result = _parse_review("SCORE: 2")
        assert result.score == 2
        assert result.reason == ""

    def test_no_score_returns_default(self):
        result = _parse_review("No structured output here")
        assert result.score == 3
        assert result.reason == ""

    def test_score_out_of_range_clamped(self):
        assert _parse_review("SCORE: 0").score == 1
        assert _parse_review("SCORE: 8").score == 5

    def test_score_from_inline_text(self):
        result = _parse_review("The output is fine. SCORE: 5")
        assert result.score == 5


class TestReviewOutput:
    @pytest.mark.asyncio
    async def test_returns_review_result(self):
        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            from maggy.adapters.pi import RunResult
            return RunResult(
                model=model_name, success=True,
                output="SCORE: 4\nREASON: Looks good",
            )

        from maggy.adapters.pi import PiAdapter
        pi = PiAdapter()
        pi.send_prompt = fake_send
        result = await review_output(pi, "ANALYZE", "some output", "/tmp")
        assert result.score == 4
        assert "Looks good" in result.reason

    @pytest.mark.asyncio
    async def test_failure_returns_passthrough(self):
        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            from maggy.adapters.pi import RunResult
            return RunResult(
                model=model_name, success=False,
                error="model unavailable",
            )

        from maggy.adapters.pi import PiAdapter
        pi = PiAdapter()
        pi.send_prompt = fake_send
        result = await review_output(pi, "IMPLEMENT", "output", "/tmp")
        assert result.score == 3
        assert result.reason == "review unavailable"

    @pytest.mark.asyncio
    async def test_exception_returns_passthrough(self):
        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            raise OSError("connection failed")

        from maggy.adapters.pi import PiAdapter
        pi = PiAdapter()
        pi.send_prompt = fake_send
        result = await review_output(pi, "ANALYZE", "output", "/tmp")
        assert result.score == 3

    @pytest.mark.asyncio
    async def test_uses_local_model(self):
        models_used: list[str] = []

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            models_used.append(model_name)
            from maggy.adapters.pi import RunResult
            return RunResult(
                model=model_name, success=True,
                output="SCORE: 4\nREASON: ok",
            )

        from maggy.adapters.pi import PiAdapter
        pi = PiAdapter()
        pi.send_prompt = fake_send
        await review_output(pi, "ANALYZE", "output", "/tmp")
        assert models_used == ["local"]

    @pytest.mark.asyncio
    async def test_prompt_contains_step_and_output(self):
        prompts: list[str] = []

        async def fake_send(
            model_name, prompt, wd, max_turns=20, timeout=600,
        ):
            prompts.append(prompt)
            from maggy.adapters.pi import RunResult
            return RunResult(
                model=model_name, success=True,
                output="SCORE: 3",
            )

        from maggy.adapters.pi import PiAdapter
        pi = PiAdapter()
        pi.send_prompt = fake_send
        await review_output(
            pi, "WRITE TESTS", "test_add_user passed", "/tmp",
        )
        assert "WRITE TESTS" in prompts[0]
        assert "test_add_user passed" in prompts[0]
