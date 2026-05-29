"""Tests for tool parser — extracts typed JSON tool calls from model output."""

from __future__ import annotations


class TestParseToolCalls:
    def test_parses_single_tool_call(self):
        from maggy.pipeline.tool_parser import parse_tool_calls
        text = (
            "Let me read the file.\n"
            "```tool_call\n"
            '{"name": "file_read", "params": {"path": "src/main.py"}}\n'
            "```\n"
        )
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0].name == "file_read"
        assert calls[0].params["path"] == "src/main.py"

    def test_parses_multiple_tool_calls(self):
        from maggy.pipeline.tool_parser import parse_tool_calls
        text = (
            "```tool_call\n"
            '{"name": "file_read", "params": {"path": "a.py"}}\n'
            "```\n"
            "Some text in between.\n"
            "```tool_call\n"
            '{"name": "grep", "params": {"pattern": "def main", "path": "src"}}\n'
            "```\n"
        )
        calls = parse_tool_calls(text)
        assert len(calls) == 2
        assert calls[0].name == "file_read"
        assert calls[1].name == "grep"

    def test_returns_empty_for_no_tool_calls(self):
        from maggy.pipeline.tool_parser import parse_tool_calls
        text = "Here is my analysis of the code..."
        calls = parse_tool_calls(text)
        assert calls == []

    def test_ignores_regular_code_blocks(self):
        from maggy.pipeline.tool_parser import parse_tool_calls
        text = (
            "```python\n"
            "def main():\n"
            "    pass\n"
            "```\n"
        )
        calls = parse_tool_calls(text)
        assert calls == []

    def test_skips_invalid_json(self):
        from maggy.pipeline.tool_parser import parse_tool_calls
        text = (
            "```tool_call\n"
            "not valid json\n"
            "```\n"
        )
        calls = parse_tool_calls(text)
        assert calls == []

    def test_skips_tool_not_in_allowlist(self):
        from maggy.pipeline.tool_parser import parse_tool_calls
        text = (
            "```tool_call\n"
            '{"name": "shell_exec", "params": {"command": "rm -rf /"}}\n'
            "```\n"
        )
        calls = parse_tool_calls(text)
        assert calls == []

    def test_extracts_text_around_tools(self):
        from maggy.pipeline.tool_parser import (
            extract_text_and_calls,
        )
        text = (
            "I'll read the file first.\n"
            "```tool_call\n"
            '{"name": "file_read", "params": {"path": "x.py"}}\n'
            "```\n"
            "Done."
        )
        parts = extract_text_and_calls(text)
        assert parts["text"].strip().startswith("I'll read")
        assert len(parts["calls"]) == 1
