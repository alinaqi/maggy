"""Tests for tool sandbox — path validation, symlink resolution."""

from __future__ import annotations

import os

import pytest


class TestPathValidation:
    def test_valid_path_in_working_dir(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("x = 1")
        sb = ToolSandbox(str(tmp_path))
        result = sb.validate_path("src/main.py")
        assert result == tmp_path / "src" / "main.py"

    def test_rejects_path_traversal(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
        sb = ToolSandbox(str(tmp_path))
        with pytest.raises(ToolSandboxError, match="escapes sandbox"):
            sb.validate_path("../../etc/passwd")

    def test_rejects_absolute_path_outside(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
        sb = ToolSandbox(str(tmp_path))
        with pytest.raises(ToolSandboxError, match="escapes sandbox"):
            sb.validate_path("/etc/passwd")

    def test_rejects_env_file(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
        (tmp_path / ".env").write_text("SECRET=x")
        sb = ToolSandbox(str(tmp_path))
        with pytest.raises(ToolSandboxError, match="Secret file"):
            sb.validate_path(".env")

    def test_rejects_dotfile_except_gitignore(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
        sb = ToolSandbox(str(tmp_path))
        with pytest.raises(ToolSandboxError, match="Dotfile"):
            sb.validate_path(".secret_config")

    def test_allows_gitignore(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox
        (tmp_path / ".gitignore").write_text("*.pyc")
        sb = ToolSandbox(str(tmp_path))
        result = sb.validate_path(".gitignore")
        assert result.name == ".gitignore"

    def test_rejects_symlink_escape(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
        link = tmp_path / "escape"
        link.symlink_to("/etc")
        sb = ToolSandbox(str(tmp_path))
        with pytest.raises(ToolSandboxError, match="escapes sandbox"):
            sb.validate_path("escape/passwd")


class TestToolCallValidation:
    def test_valid_read_tool(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox
        from maggy.pipeline.tool_schema import ToolCall
        (tmp_path / "main.py").write_text("x = 1")
        sb = ToolSandbox(str(tmp_path))
        tc = ToolCall(name="file_read", params={"path": "main.py"})
        result = sb.validate_tool_call(tc)
        assert result.name == "file_read"

    def test_rejects_unknown_tool(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
        from maggy.pipeline.tool_schema import ToolCall
        sb = ToolSandbox(str(tmp_path))
        tc = ToolCall(name="shell_exec", params={"cmd": "rm -rf /"})
        with pytest.raises(ToolSandboxError, match="not in allowlist"):
            sb.validate_tool_call(tc)

    def test_validates_path_param(self, tmp_path):
        from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
        from maggy.pipeline.tool_schema import ToolCall
        sb = ToolSandbox(str(tmp_path))
        tc = ToolCall(
            name="file_read",
            params={"path": "../../etc/passwd"},
        )
        with pytest.raises(ToolSandboxError, match="escapes sandbox"):
            sb.validate_tool_call(tc)
