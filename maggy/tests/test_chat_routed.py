"""Tests for routed chat — multi-model routing in ChatManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maggy.services.chat_router import estimate_blast, estimate_type


class TestBlastEstimation:
    """Blast score estimation from message keywords."""

    def test_low_blast_simple_fix(self):
        assert estimate_blast("fix the typo in README") <= 3

    def test_high_blast_security(self):
        assert estimate_blast("design auth system with OAuth") >= 7

    def test_high_blast_architecture(self):
        assert estimate_blast("refactor database schema") >= 5

    def test_medium_blast_feature(self):
        score = estimate_blast("add pagination to the API")
        assert 3 <= score <= 6

    def test_empty_returns_default(self):
        assert estimate_blast("") == 5

    # --- Intent-based scoring ---

    def test_retrieval_find_key_low_blast(self):
        """'find the API key' is retrieval, not mid-complexity."""
        assert estimate_blast("find the API key in ~/Documents") <= 3

    def test_retrieval_show_config(self):
        assert estimate_blast("show me the current config") <= 3

    def test_retrieval_check_env(self):
        assert estimate_blast("check the env variables") <= 3

    def test_retrieval_where_is_file(self):
        assert estimate_blast("where is the routes file") <= 3

    def test_retrieval_list_endpoints(self):
        assert estimate_blast("list all API endpoints") <= 3

    def test_retrieval_read_file(self):
        assert estimate_blast("read the package.json") <= 3

    def test_creation_still_mid(self):
        """create/implement should stay in 4-6 range."""
        score = estimate_blast("create a new user service")
        assert 4 <= score <= 6

    def test_multi_step_high(self):
        """refactor + migrate = high blast."""
        assert estimate_blast("refactor and migrate the database") >= 7

    def test_retrieval_with_action_not_capped(self):
        """'find the bug and fix it' has both retrieval and mutation."""
        score = estimate_blast("find the bug and fix the auth")
        assert score >= 4


class TestTypeEstimation:
    """Task type estimation from message keywords."""

    def test_security_type(self):
        assert estimate_type("fix authentication bug") == "security"

    def test_docs_type(self):
        assert estimate_type("write documentation for API") == "docs"

    def test_test_type(self):
        assert estimate_type("add unit tests with mock fixtures") == "tests"

    def test_general_default(self):
        assert estimate_type("make it faster") == "general"


class TestRoutedEndpoint:
    """API endpoint /send-routed returns routing metadata."""

    @pytest.mark.asyncio
    async def test_send_routed_yields_routing_chunk(self):
        """First SSE chunk should be routing decision."""
        from maggy.services.chat_router import RoutedChat

        mock_routing = MagicMock()
        mock_routing.route.return_value = MagicMock(
            primary=MagicMock(name="claude"),
            reason="blast 8 → claude",
        )
        mock_budget = MagicMock()
        mock_budget.check.return_value = True

        rc = RoutedChat(mock_routing, mock_budget)
        with patch(
            "maggy.services.intent_classifier.classify_intent",
            new=AsyncMock(return_value="security"),
        ), patch(
            "maggy.services.intent_classifier.classify_blast",
            new=AsyncMock(return_value=8),
        ):
            decision = await rc.decide("design auth system", None, None)
        assert decision is not None
        mock_routing.route.assert_called_once()


class TestRewardRecording:
    """Reward recording after routed chat completes."""

    def test_success_records_reward(self):
        """Successful chat records reward=1.0."""
        from maggy.pipeline.hooks import record_outcome
        from maggy.pipeline.models import PipelineResult
        routing = MagicMock()
        result = PipelineResult(
            model="local", backend="pi", blast=5,
            task_type="general", reason="test",
            latency_ms=100, cost_usd=0, tokens_in=0,
            tokens_out=0, success=True,
        )
        record_outcome(routing, result)
        routing.record_outcome.assert_called_once_with(
            "local", "general", 5, 1.0,
        )

    def test_error_records_zero_reward(self):
        """Chat with error records reward=0.0."""
        from maggy.pipeline.hooks import record_outcome
        from maggy.pipeline.models import PipelineResult
        routing = MagicMock()
        result = PipelineResult(
            model="claude", backend="claude", blast=8,
            task_type="security", reason="test",
            latency_ms=100, cost_usd=0, tokens_in=0,
            tokens_out=0, success=False,
        )
        record_outcome(routing, result)
        routing.record_outcome.assert_called_once_with(
            "claude", "security", 8, 0.0,
        )

    def test_no_routing_service_noop(self):
        """No routing service → no crash."""
        from maggy.pipeline.hooks import record_outcome
        from maggy.pipeline.models import PipelineResult
        result = PipelineResult(
            model="claude", backend="claude", blast=0,
            task_type="general", reason="test",
            latency_ms=0, cost_usd=0, tokens_in=0,
            tokens_out=0, success=True,
        )
        record_outcome(None, result)
