"""Tests for cross-model checkpoint serializer."""

from __future__ import annotations

from maggy.services.checkpoint import (
    Checkpoint,
    create_checkpoint,
)


class TestCheckpoint:
    def test_serialize_round_trip(self):
        cp = Checkpoint(
            goal="Fix auth bug",
            progress=["Found root cause"],
            source_model="claude",
        )
        data = cp.serialize()
        restored = Checkpoint.deserialize(data)
        assert restored.goal == "Fix auth bug"
        assert restored.source_model == "claude"
        assert len(restored.progress) == 1

    def test_serialize_sets_timestamp(self):
        cp = Checkpoint(goal="test")
        data = cp.serialize()
        restored = Checkpoint.deserialize(data)
        assert restored.created_at != ""

    def test_to_prompt_format(self):
        cp = Checkpoint(
            goal="Add logout button",
            constraints=["No breaking changes"],
            progress=["Created component"],
            working_state="Testing phase",
            file_context=["src/auth.ts"],
        )
        prompt = cp.to_prompt()
        assert "Add logout button" in prompt
        assert "No breaking changes" in prompt
        assert "Created component" in prompt
        assert "Testing phase" in prompt
        assert "src/auth.ts" in prompt

    def test_to_prompt_minimal(self):
        cp = Checkpoint(goal="Simple task")
        prompt = cp.to_prompt()
        assert "Simple task" in prompt
        assert "confirm you understand" in prompt


class TestCreateCheckpoint:
    def test_helper_function(self):
        cp = create_checkpoint(
            goal="Refactor DB layer",
            progress=["Extracted interface"],
            model="gpt",
            working_state="mid-refactor",
            files=["db.py", "models.py"],
            constraints=["Keep API stable"],
        )
        assert cp.goal == "Refactor DB layer"
        assert cp.source_model == "gpt"
        assert len(cp.file_context) == 2

    def test_defaults(self):
        cp = create_checkpoint(
            goal="Test", progress=[], model="claude",
        )
        assert cp.constraints == []
        assert cp.file_context == []
