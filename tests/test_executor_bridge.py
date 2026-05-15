"""Tests for chat_executor_bridge — blast routing fidelity."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maggy.services.chat_executor_bridge import (
    _BLAST_THRESHOLD,
    should_route_to_executor,
    task_from_chat,
)


# ── task_from_chat stores blast_score correctly ──


class TestTaskFromChat:
    def _decision(self, blast=5, task_type="general"):
        d = MagicMock()
        d.blast = blast
        d.task_type = task_type
        d.model = "codex"
        return d

    def test_blast_score_key_in_raw(self):
        """Raw dict must use 'blast_score' so executor reads it."""
        task = task_from_chat("implement auth", self._decision(7), "/tmp")
        assert "blast_score" in task.raw
        assert task.raw["blast_score"] == 7

    def test_blast_score_preserved(self):
        """Blast score value must survive round-trip."""
        for score in (1, 4, 7, 10):
            task = task_from_chat("msg", self._decision(score), "/tmp")
            assert task.raw["blast_score"] == score

    def test_task_type_stored(self):
        task = task_from_chat("msg", self._decision(task_type="security"), "/tmp")
        assert task.raw["task_type"] == "security"

    def test_title_truncated(self):
        long_msg = "x" * 200
        task = task_from_chat(long_msg, self._decision(), "/tmp")
        assert len(task.title) <= 120


# ── should_route_to_executor gate ──


class TestShouldRouteToExecutor:
    def _decision(self, blast=5, task_type="general"):
        d = MagicMock()
        d.blast = blast
        d.task_type = task_type
        return d

    def test_routes_at_threshold(self):
        assert should_route_to_executor(self._decision(blast=_BLAST_THRESHOLD))

    def test_routes_above_threshold(self):
        assert should_route_to_executor(self._decision(blast=8))

    def test_skips_below_threshold(self):
        assert not should_route_to_executor(self._decision(blast=3))

    def test_skips_passthrough_search(self):
        assert not should_route_to_executor(self._decision(blast=8, task_type="search"))

    def test_skips_passthrough_docs(self):
        assert not should_route_to_executor(self._decision(blast=8, task_type="docs"))

    def test_skips_passthrough_review(self):
        assert not should_route_to_executor(self._decision(blast=8, task_type="review"))

    def test_allows_general(self):
        assert should_route_to_executor(self._decision(blast=5, task_type="general"))

    def test_allows_tests(self):
        assert should_route_to_executor(self._decision(blast=5, task_type="tests"))


# ── blast_score round-trip via executor_helpers ──


class TestBlastScoreRoundTrip:
    def test_executor_reads_correct_blast(self):
        """Executor must read the blast score stored by task_from_chat."""
        from maggy.services.executor_helpers import blast_score

        d = MagicMock()
        d.blast, d.task_type, d.model = 6, "general", "codex"
        task = task_from_chat("build feature", d, "/tmp")
        assert blast_score(task) == 6

    def test_executor_reads_zero_for_missing(self):
        """Missing blast_score should default to 0."""
        from maggy.services.executor_helpers import blast_score

        task = MagicMock()
        task.raw = {}
        assert blast_score(task) == 0
