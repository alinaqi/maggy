"""Integration test: Quota -> Checkpoint -> Switch -> Continue.

Tests fatigue-based checkpointing and model switching.
"""

from __future__ import annotations

from maggy.fatigue import create_profile
from maggy.services.checkpoint import Checkpoint, create_checkpoint


class TestModelFallback:
    def test_fatigue_triggers_checkpoint(self):
        """When fatigue is high, checkpoint and switch."""
        profile = create_profile("claude")
        profile.tokens_used = 170_000
        profile.turns = 40

        assert profile.should_checkpoint()

        # Create checkpoint
        cp = create_checkpoint(
            goal="Refactor auth module",
            progress=["Extracted interface", "Updated tests"],
            model="claude",
            working_state="Mid-refactor, 3 files changed",
            files=["auth.py", "test_auth.py"],
        )

        # Serialize for handoff
        data = cp.serialize()
        restored = Checkpoint.deserialize(data)
        assert restored.goal == "Refactor auth module"
        assert restored.source_model == "claude"

        # Generate prompt for next model
        prompt = restored.to_prompt()
        assert "Refactor auth module" in prompt
        assert "Mid-refactor" in prompt

    def test_cross_model_checkpoint_round_trip(self):
        """Checkpoint survives serialization across models."""
        cp = create_checkpoint(
            goal="Fix API pagination",
            progress=["Found bug in offset calc"],
            model="gpt",
            constraints=["Don't break existing tests"],
            files=["api/routes.py"],
        )

        # Simulate model switch: serialize -> transfer -> restore
        serialized = cp.serialize()
        new_model_cp = Checkpoint.deserialize(serialized)

        assert new_model_cp.source_model == "gpt"
        prompt = new_model_cp.to_prompt()
        assert "Don't break existing tests" in prompt

    def test_fresh_model_low_fatigue(self):
        """A fresh model should not be fatigued."""
        profile = create_profile("kimi")
        assert not profile.should_checkpoint()
        assert profile.fatigue_score == 0.0
