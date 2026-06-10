"""Tests for multi-round deliberation engine."""

import pytest
from unittest.mock import AsyncMock, patch

from maggy.council.models import (
    ContextPackage, ReviewerVote, DeliberationResult
)


def _make_ctx() -> ContextPackage:
    return ContextPackage(
        goal="add user endpoint",
        plan_text="create GET /users route",
        code_diff="+ @app.get('/users')",
    )


def _vote(rid: str, verdict: str, rnd: int = 1) -> ReviewerVote:
    return ReviewerVote(
        reviewer_id=rid, round_num=rnd, verdict=verdict,
        reasoning=f"{rid} says {verdict.lower()}"
    )


class TestCheckConsensus:
    def test_all_approve(self):
        from maggy.council.deliberation import _check_consensus
        votes = [_vote("a", "APPROVE"), _vote("b", "APPROVE")]
        assert _check_consensus(votes) is True

    def test_all_reject(self):
        from maggy.council.deliberation import _check_consensus
        votes = [_vote("a", "REJECT"), _vote("b", "REJECT")]
        assert _check_consensus(votes) is True

    def test_mixed(self):
        from maggy.council.deliberation import _check_consensus
        votes = [_vote("a", "APPROVE"), _vote("b", "REJECT")]
        assert _check_consensus(votes) is False


class TestBuildResult:
    def test_from_votes(self):
        from maggy.council.deliberation import _build_result
        votes = [_vote("a", "APPROVE"), _vote("b", "APPROVE")]
        log = [{"round": 1, "votes": votes}]
        r = _build_result(votes, 1, log, threshold=2)
        assert r.approved
        assert r.rounds_needed == 1


class TestParseVote:
    def test_parse_approve(self):
        from maggy.council.deliberation import _parse_vote
        raw = "APPROVE\nLooks correct and safe."
        v = _parse_vote("ds", 1, raw)
        assert v.verdict == "APPROVE"

    def test_parse_reject(self):
        from maggy.council.deliberation import _parse_vote
        raw = "REJECT\nMissing error handling."
        v = _parse_vote("kimi", 2, raw)
        assert v.verdict == "REJECT"

    def test_parse_ambiguous_defaults_reject(self):
        from maggy.council.deliberation import _parse_vote
        raw = "I think it could work but I'm not sure."
        v = _parse_vote("codex", 1, raw)
        assert v.verdict == "REJECT"


class TestDeliberationRun:
    @pytest.mark.asyncio
    async def test_consensus_round1(self):
        from maggy.council.deliberation import Deliberation

        async def mock_query(reviewer_id, prompt):
            return "APPROVE\nAll good."

        d = Deliberation(query_fn=mock_query)
        ctx = _make_ctx()
        result = await d.run(ctx, ["a", "b", "c"], threshold=2)
        assert result.approved
        assert result.rounds_needed == 1
        assert result.consensus

    @pytest.mark.asyncio
    async def test_disagreement_goes_to_round2(self):
        from maggy.council.deliberation import Deliberation

        call_count = {"n": 0}

        async def mock_query(reviewer_id, prompt):
            call_count["n"] += 1
            if call_count["n"] <= 3:
                if reviewer_id == "c":
                    return "REJECT\nNot safe."
                return "APPROVE\nFine."
            return "APPROVE\nConvinced now."

        d = Deliberation(query_fn=mock_query)
        ctx = _make_ctx()
        result = await d.run(ctx, ["a", "b", "c"], threshold=2)
        assert result.approved
        assert result.rounds_needed <= 3

    @pytest.mark.asyncio
    async def test_all_reject_not_approved(self):
        from maggy.council.deliberation import Deliberation

        async def mock_query(reviewer_id, prompt):
            return "REJECT\nBad approach."

        d = Deliberation(query_fn=mock_query)
        ctx = _make_ctx()
        result = await d.run(ctx, ["a", "b", "c"], threshold=2)
        assert not result.approved
        assert result.consensus
        assert result.rounds_needed == 1

    @pytest.mark.asyncio
    async def test_threshold_1_of_3(self):
        from maggy.council.deliberation import Deliberation

        async def mock_query(reviewer_id, prompt):
            return "APPROVE\nOk." if reviewer_id == "a" else "REJECT\nNo."

        d = Deliberation(query_fn=mock_query)
        ctx = _make_ctx()
        result = await d.run(ctx, ["a", "b", "c"], threshold=1)
        assert result.approved
