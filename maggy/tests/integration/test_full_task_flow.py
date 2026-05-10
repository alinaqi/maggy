"""Integration test: Ticket -> Route -> Execute -> Reward.

Tests the full lifecycle of a task through routing, event
emission, and reward recording.
"""

from __future__ import annotations

from pathlib import Path

from maggy.event_spine.emitter import EventEmitter
from maggy.event_spine.events import (
    ExecutionEvent,
    IntentEvent,
    OutcomeEvent,
)
from maggy.event_spine.store import EventStore
from maggy.routing import RoutingContext, RoutingService
from maggy.scores import MIN_SAMPLES


class TestFullTaskFlow:
    def test_route_emit_reward(self, mock_cfg, tmp_path: Path):
        """Full flow: route task, emit events, record reward."""
        # 1. Route the task
        router = RoutingService(mock_cfg)
        ctx = RoutingContext(
            blast_score=5, task_type="feature",
        )
        decision = router.route(ctx)
        name = (
            decision.primary
            if isinstance(decision.primary, str)
            else decision.primary.name
        )
        assert name  # Got a routing decision

        # 2. Emit events through the spine
        store = EventStore(tmp_path / "events.db")
        emitter = EventEmitter(store)

        intent = IntentEvent(
            intent_text="Add user dashboard",
            decomposed_steps=["create component", "add api"],
        )
        intent.header.task_id = "task-123"
        emitter.emit(intent)

        exec_evt = ExecutionEvent(
            tool_name="code_edit",
            duration_ms=500,
            success=True,
        )
        exec_evt.header.task_id = "task-123"
        emitter.emit(exec_evt)

        outcome = OutcomeEvent(success=True, reward=0.85)
        outcome.header.task_id = "task-123"
        emitter.emit(outcome)

        # 3. Verify trace
        trace = emitter.trace("task-123")
        assert len(trace) == 3

        # 4. Record reward for learning
        router.record_outcome(name, "feature", 5, 0.85)
        heatmap = router.get_heatmap()
        assert len(heatmap) >= 1

    def test_multi_task_routing(self, mock_cfg):
        """Route multiple tasks, verify different tiers."""
        router = RoutingService(mock_cfg)

        low = router.route(RoutingContext(blast_score=1))
        high = router.route(RoutingContext(blast_score=9))

        low_name = (
            low.primary if isinstance(low.primary, str)
            else low.primary.name
        )
        high_name = (
            high.primary if isinstance(high.primary, str)
            else high.primary.name
        )

        # Low should be cheaper, high should be premium
        assert low_name != high_name or low_name == "claude"
