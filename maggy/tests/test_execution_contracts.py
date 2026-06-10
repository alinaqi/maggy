"""Tests for execution contracts — strict-agentic mode."""

from __future__ import annotations


class TestExecutionContract:
    def test_strict_rejects_planning_only(self):
        from maggy.pipeline.contracts import ExecutionContract
        c = ExecutionContract(mode="strict-agentic")
        response = "Here's what you should do:\n1. Open the file\n2. Edit it"
        assert c.validate_response(response) is False

    def test_strict_accepts_action_response(self):
        from maggy.pipeline.contracts import ExecutionContract
        c = ExecutionContract(mode="strict-agentic")
        response = "I've updated src/main.py and ran the tests. All passing."
        assert c.validate_response(response) is True

    def test_strict_accepts_tool_calls(self):
        from maggy.pipeline.contracts import ExecutionContract
        c = ExecutionContract(mode="strict-agentic")
        response = (
            "```tool_call\n"
            '{"name": "file_read", "params": {"path": "x.py"}}\n'
            "```\n"
        )
        assert c.validate_response(response) is True

    def test_advisory_accepts_everything(self):
        from maggy.pipeline.contracts import ExecutionContract
        c = ExecutionContract(mode="advisory")
        response = "Here's what you should do:\n1. Step one"
        assert c.validate_response(response) is True

    def test_hybrid_accepts_everything(self):
        from maggy.pipeline.contracts import ExecutionContract
        c = ExecutionContract(mode="hybrid")
        response = "I recommend you do this..."
        assert c.validate_response(response) is True

    def test_default_mode_is_strict(self):
        from maggy.pipeline.contracts import ExecutionContract
        c = ExecutionContract()
        assert c.mode == "strict-agentic"

    def test_strict_accepts_short_answer(self):
        from maggy.pipeline.contracts import ExecutionContract
        c = ExecutionContract(mode="strict-agentic")
        response = "The function is at line 42 in utils.py."
        assert c.validate_response(response) is True

    def test_strict_accepts_empty(self):
        from maggy.pipeline.contracts import ExecutionContract
        c = ExecutionContract(mode="strict-agentic")
        assert c.validate_response("") is True
