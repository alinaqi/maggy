"""Tests for tool schema — allowlist, typed definitions, validation."""

from __future__ import annotations

import pytest


class TestToolDef:
    def test_tool_def_has_name(self):
        from maggy.pipeline.tool_schema import ToolDef
        t = ToolDef(name="file_read", risk="read", params=[])
        assert t.name == "file_read"

    def test_tool_def_has_risk(self):
        from maggy.pipeline.tool_schema import ToolDef
        t = ToolDef(name="file_write", risk="write", params=[])
        assert t.risk == "write"

    def test_tool_def_risk_must_be_read_or_write(self):
        from maggy.pipeline.tool_schema import ToolDef
        with pytest.raises(ValueError):
            ToolDef(name="x", risk="destructive", params=[])


class TestParamDef:
    def test_param_required(self):
        from maggy.pipeline.tool_schema import ParamDef
        p = ParamDef(name="path", param_type="str", required=True)
        assert p.required is True

    def test_param_default(self):
        from maggy.pipeline.tool_schema import ParamDef
        p = ParamDef(name="n", param_type="int", default=10)
        assert p.default == 10


class TestAllowlist:
    def test_read_tools_exist(self):
        from maggy.pipeline.tool_schema import READ_TOOLS
        assert "file_read" in READ_TOOLS
        assert "grep" in READ_TOOLS
        assert "git_status" in READ_TOOLS

    def test_write_tools_exist(self):
        from maggy.pipeline.tool_schema import WRITE_TOOLS
        assert "file_write" in WRITE_TOOLS
        assert "file_edit" in WRITE_TOOLS
        assert "git_commit" in WRITE_TOOLS

    def test_no_shell_exec(self):
        from maggy.pipeline.tool_schema import TOOL_ALLOWLIST
        assert "shell_exec" not in TOOL_ALLOWLIST

    def test_all_read_tools_have_read_risk(self):
        from maggy.pipeline.tool_schema import READ_TOOLS
        for tool in READ_TOOLS.values():
            assert tool.risk == "read"

    def test_all_write_tools_have_write_risk(self):
        from maggy.pipeline.tool_schema import WRITE_TOOLS
        for tool in WRITE_TOOLS.values():
            assert tool.risk == "write"

    def test_allowlist_is_union(self):
        from maggy.pipeline.tool_schema import (
            READ_TOOLS,
            TOOL_ALLOWLIST,
            WRITE_TOOLS,
        )
        assert set(TOOL_ALLOWLIST) == set(READ_TOOLS) | set(WRITE_TOOLS)


class TestToolCall:
    def test_tool_call_creation(self):
        from maggy.pipeline.tool_schema import ToolCall
        tc = ToolCall(name="file_read", params={"path": "src/main.py"})
        assert tc.name == "file_read"
        assert tc.params["path"] == "src/main.py"

    def test_validate_against_allowlist_passes(self):
        from maggy.pipeline.tool_schema import ToolCall, validate_tool_call
        tc = ToolCall(name="file_read", params={"path": "src/main.py"})
        assert validate_tool_call(tc) is True

    def test_validate_unknown_tool_fails(self):
        from maggy.pipeline.tool_schema import ToolCall, validate_tool_call
        tc = ToolCall(name="shell_exec", params={"command": "rm -rf /"})
        with pytest.raises(ValueError, match="Unknown tool"):
            validate_tool_call(tc)

    def test_validate_missing_required_param(self):
        from maggy.pipeline.tool_schema import ToolCall, validate_tool_call
        tc = ToolCall(name="file_read", params={})
        with pytest.raises(ValueError, match="Missing required"):
            validate_tool_call(tc)
