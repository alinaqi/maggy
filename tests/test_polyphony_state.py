"""Tests for Polyphony state machine (§4 lifecycle)."""

import pytest
from polyphony.models import Task
from polyphony.state_machine import (
    TASK_STATES,
    TRANSITIONS,
    can_transition,
    transition,
    is_terminal,
)


class TestConstants:
    def test_all_states_present(self):
        expected = {
            "discovered", "claimed", "routed", "provisioned",
            "running", "verifying", "landed", "failed", "blocked",
        }
        assert set(TASK_STATES) == expected

    def test_transitions_keys_are_valid_states(self):
        for state in TRANSITIONS:
            assert state in TASK_STATES


class TestCanTransition:
    def test_discovered_to_claimed(self):
        assert can_transition("discovered", "claimed") is True

    def test_claimed_to_routed(self):
        assert can_transition("claimed", "routed") is True

    def test_routed_to_provisioned(self):
        assert can_transition("routed", "provisioned") is True

    def test_provisioned_to_running(self):
        assert can_transition("provisioned", "running") is True

    def test_running_to_verifying(self):
        assert can_transition("running", "verifying") is True

    def test_running_to_failed(self):
        assert can_transition("running", "failed") is True

    def test_verifying_to_landed(self):
        assert can_transition("verifying", "landed") is True

    def test_verifying_to_failed(self):
        assert can_transition("verifying", "failed") is True

    def test_failed_to_claimed_retry(self):
        assert can_transition("failed", "claimed") is True

    def test_failed_to_blocked(self):
        assert can_transition("failed", "blocked") is True

    def test_invalid_discovered_to_running(self):
        assert can_transition("discovered", "running") is False

    def test_invalid_landed_to_anything(self):
        assert can_transition("landed", "claimed") is False
        assert can_transition("landed", "failed") is False

    def test_invalid_same_state(self):
        assert can_transition("claimed", "claimed") is False


class TestTransition:
    def test_valid_transition_updates_state(self):
        t = Task(title="x", source="local", source_ref="1")
        assert t.state == "discovered"
        t2 = transition(t, "claimed")
        assert t2.state == "claimed"

    def test_invalid_transition_raises(self):
        t = Task(title="x", source="local", source_ref="1")
        with pytest.raises(ValueError, match="Invalid transition"):
            transition(t, "running")

    def test_transition_updates_timestamp(self):
        t = Task(title="x", source="local", source_ref="1")
        old_ts = t.updated_at
        t2 = transition(t, "claimed")
        assert t2.updated_at >= old_ts


class TestIsTerminal:
    def test_landed_is_terminal(self):
        assert is_terminal("landed") is True

    def test_blocked_is_terminal(self):
        assert is_terminal("blocked") is True

    def test_discovered_not_terminal(self):
        assert is_terminal("discovered") is False

    def test_running_not_terminal(self):
        assert is_terminal("running") is False

    def test_failed_not_terminal(self):
        assert is_terminal("failed") is False
