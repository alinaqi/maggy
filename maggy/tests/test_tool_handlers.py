"""Tests for tool handlers — concrete implementations of allowlisted tools."""

from __future__ import annotations

import pytest


class TestFileRead:
    @pytest.mark.asyncio
    async def test_reads_file(self, tmp_path):
        from maggy.pipeline.tool_handlers import file_read
        f = tmp_path / "hello.py"
        f.write_text("print('hi')")
        result = await file_read(f)
        assert "print('hi')" in result

    @pytest.mark.asyncio
    async def test_rejects_large_file(self, tmp_path):
        from maggy.pipeline.tool_handlers import file_read
        f = tmp_path / "big.txt"
        f.write_text("x" * 60_000)
        result = await file_read(f)
        assert "truncated" in result.lower()

    @pytest.mark.asyncio
    async def test_missing_file(self, tmp_path):
        from maggy.pipeline.tool_handlers import file_read
        result = await file_read(tmp_path / "nope.py")
        assert "error" in result.lower() or "not found" in result.lower()


class TestGrep:
    @pytest.mark.asyncio
    async def test_grep_finds_pattern(self, tmp_path):
        from maggy.pipeline.tool_handlers import grep
        (tmp_path / "a.py").write_text("def hello():\n    pass\n")
        result = await grep("def hello", tmp_path)
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_grep_no_match(self, tmp_path):
        from maggy.pipeline.tool_handlers import grep
        (tmp_path / "a.py").write_text("x = 1")
        result = await grep("zzz_no_match", tmp_path)
        assert result == "" or "no match" in result.lower()


class TestFileWrite:
    @pytest.mark.asyncio
    async def test_writes_file(self, tmp_path):
        from maggy.pipeline.tool_handlers import file_write
        target = tmp_path / "new.py"
        result = await file_write(target, "x = 1\n")
        assert target.read_text() == "x = 1\n"
        assert "wrote" in result.lower() or "written" in result.lower()

    @pytest.mark.asyncio
    async def test_creates_parent_dirs(self, tmp_path):
        from maggy.pipeline.tool_handlers import file_write
        target = tmp_path / "sub" / "deep" / "f.py"
        await file_write(target, "y = 2")
        assert target.exists()

    @pytest.mark.asyncio
    async def test_rejects_oversized_content(self, tmp_path):
        from maggy.pipeline.tool_handlers import file_write
        target = tmp_path / "big.txt"
        result = await file_write(target, "x" * 200_000)
        assert "too large" in result.lower()
        assert not target.exists()


class TestFileEdit:
    @pytest.mark.asyncio
    async def test_replaces_text(self, tmp_path):
        from maggy.pipeline.tool_handlers import file_edit
        f = tmp_path / "a.py"
        f.write_text("x = 1\ny = 2\n")
        result = await file_edit(f, "x = 1", "x = 42")
        assert f.read_text() == "x = 42\ny = 2\n"
        assert "edited" in result.lower()

    @pytest.mark.asyncio
    async def test_old_not_found(self, tmp_path):
        from maggy.pipeline.tool_handlers import file_edit
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        result = await file_edit(f, "zzz_missing", "replaced")
        assert "not found" in result.lower()


class TestGitStatus:
    @pytest.mark.asyncio
    async def test_git_status_runs(self, tmp_path):
        from maggy.pipeline.tool_handlers import git_status
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        result = await git_status(tmp_path)
        assert isinstance(result, str)
