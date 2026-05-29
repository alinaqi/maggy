"""End-to-end integration tests for the autonomous agent pipeline.

Each test exercises the full chain: parser → sandbox → executor → steering
→ contracts → approval, validating real cross-module interactions.
"""

from __future__ import annotations

import pytest

from maggy.pipeline.tool_schema import ToolCall
from maggy.pipeline.tool_sandbox import ToolSandbox, ToolSandboxError
from maggy.pipeline.tool_parser import parse_tool_calls, extract_text_and_calls
from maggy.pipeline.tool_executor import ToolExecutor, ToolResult
from maggy.pipeline.steering import needs_steering, steering_injection
from maggy.pipeline.contracts import ExecutionContract
from maggy.services.approval import ApprovalStore, ApprovalRequest
from maggy.skills.selective import (
    build_skill_index,
    match_for_task,
    build_selective_context,
)
from maggy.skills.models import Skill, SkillMetadata


def _make_skill(name: str, desc: str, when: str, content: str) -> Skill:
    return Skill(
        metadata=SkillMetadata(
            name=name, description=desc, when_to_use=when,
        ),
        content=content,
        source="test",
        source_path="/tmp/test",
    )


class TestParseToExecute:
    """E2E: model text → parser → sandbox → executor → result."""

    @pytest.mark.asyncio
    async def test_file_write_round_trip(self, tmp_path):
        model_output = (
            "I'll create a config file.\n"
            "```tool_call\n"
            '{"name": "file_write", "params": '
            '{"path": "config.py", "content": "DEBUG = True"}}\n'
            "```\n"
        )
        parsed = extract_text_and_calls(model_output)
        assert len(parsed["calls"]) == 1
        assert "create a config" in parsed["text"]

        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        results = await ex.execute_round(parsed["calls"])

        assert len(results) == 1
        assert results[0].success is True
        assert (tmp_path / "config.py").read_text() == "DEBUG = True"

    @pytest.mark.asyncio
    async def test_file_read_round_trip(self, tmp_path):
        (tmp_path / "app.py").write_text("print('hello')")
        model_output = (
            '```tool_call\n{"name": "file_read", '
            '"params": {"path": "app.py"}}\n```'
        )
        calls = parse_tool_calls(model_output)
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        results = await ex.execute_round(calls)

        assert results[0].success is True
        assert "hello" in results[0].output

    @pytest.mark.asyncio
    async def test_multiple_tools_in_one_response(self, tmp_path):
        model_output = (
            "```tool_call\n"
            '{"name": "file_write", "params": '
            '{"path": "a.py", "content": "x = 1"}}\n'
            "```\n"
            "```tool_call\n"
            '{"name": "file_write", "params": '
            '{"path": "b.py", "content": "y = 2"}}\n'
            "```\n"
        )
        calls = parse_tool_calls(model_output)
        assert len(calls) == 2

        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        results = await ex.execute_round(calls)

        assert all(r.success for r in results)
        assert (tmp_path / "a.py").read_text() == "x = 1"
        assert (tmp_path / "b.py").read_text() == "y = 2"


class TestSandboxBlocksInPipeline:
    """E2E: parser extracts calls, sandbox blocks dangerous ones."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path):
        model_output = (
            '```tool_call\n{"name": "file_read", '
            '"params": {"path": "../../etc/passwd"}}\n```'
        )
        calls = parse_tool_calls(model_output)
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        results = await ex.execute_round(calls)

        assert len(results) == 1
        assert results[0].success is False
        assert "sandbox" in results[0].output.lower()

    @pytest.mark.asyncio
    async def test_secret_file_blocked(self, tmp_path):
        model_output = (
            '```tool_call\n{"name": "file_read", '
            '"params": {"path": ".env"}}\n```'
        )
        calls = parse_tool_calls(model_output)
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        results = await ex.execute_round(calls)

        assert results[0].success is False
        assert "secret" in results[0].output.lower()

    @pytest.mark.asyncio
    async def test_dotfile_blocked(self, tmp_path):
        model_output = (
            '```tool_call\n{"name": "file_read", '
            '"params": {"path": ".bashrc"}}\n```'
        )
        calls = parse_tool_calls(model_output)
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))
        results = await ex.execute_round(calls)

        assert results[0].success is False
        assert "dotfile" in results[0].output.lower()

    @pytest.mark.asyncio
    async def test_unknown_tool_rejected_by_parser(self):
        model_output = (
            '```tool_call\n{"name": "shell_exec", '
            '"params": {"cmd": "rm -rf /"}}\n```'
        )
        calls = parse_tool_calls(model_output)
        assert len(calls) == 0


class TestSteeringContractPipeline:
    """E2E: response → steering check → contract validation."""

    def test_advisory_detected_and_contract_rejects(self):
        response = (
            "Here's what you should do:\n"
            "1. Open config.py\n"
            "2. Change DEBUG to False\n"
            "3. Run tests"
        )
        assert needs_steering(response) is True

        contract = ExecutionContract(mode="strict-agentic")
        assert contract.validate_response(response) is False

    def test_action_response_passes_both(self):
        response = (
            "I've updated config.py to set DEBUG=False.\n"
            "```tool_call\n"
            '{"name": "file_edit", "params": {"path": "config.py", '
            '"old": "DEBUG = True", "new": "DEBUG = False"}}\n'
            "```\n"
            "Tests pass."
        )
        assert needs_steering(response) is False

        contract = ExecutionContract(mode="strict-agentic")
        assert contract.validate_response(response) is True

    def test_steering_injection_text_is_actionable(self):
        injection = steering_injection()
        assert "execute" in injection.lower()
        assert "advise" in injection.lower()

    def test_permissive_contract_allows_advisory(self):
        response = "You should update the config file."
        contract = ExecutionContract(mode="permissive")
        assert contract.validate_response(response) is True


class TestWriteToApprovalPipeline:
    """E2E: write tool → executor → approval store → REST query."""

    @pytest.mark.asyncio
    async def test_write_creates_approval_record(self, tmp_path):
        store = ApprovalStore(str(tmp_path / "approvals.db"))
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path), approval_store=store)

        model_output = (
            '```tool_call\n{"name": "file_write", "params": '
            '{"path": "new.py", "content": "x = 42"}}\n```'
        )
        calls = parse_tool_calls(model_output)
        results = await ex.execute_round(calls)

        assert results[0].success is True

        history = store.history()
        assert len(history) == 1
        assert history[0].action == "file_write"
        assert history[0].risk == "write"

    @pytest.mark.asyncio
    async def test_read_does_not_create_approval(self, tmp_path):
        (tmp_path / "data.py").write_text("val = 1")
        store = ApprovalStore(str(tmp_path / "approvals.db"))
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path), approval_store=store)

        calls = [ToolCall("file_read", {"path": "data.py"})]
        await ex.execute_round(calls)

        history = store.history()
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_approval_resolve_cycle(self, tmp_path):
        store = ApprovalStore(str(tmp_path / "approvals.db"))
        req = ApprovalRequest(
            action="file_write", risk="write",
            context="test write", status="pending",
        )
        store.save(req)

        pending = store.pending()
        assert len(pending) == 1
        assert pending[0].status == "pending"

        store.resolve(req.id, "approved", "human")

        pending_after = store.pending()
        assert len(pending_after) == 0

        history = store.history()
        assert len(history) == 1
        assert history[0].status == "approved"
        assert history[0].resolved_by == "human"


class TestSelectiveSkillPipeline:
    """E2E: task → skill matching → index/context building."""

    def test_match_and_build_context(self):
        skills = [
            _make_skill(
                "git-workflow", "Git branching and PR workflow",
                "when working with git", "Always use feature branches.",
            ),
            _make_skill(
                "testing", "TDD and test patterns",
                "when writing tests", "Write tests first.",
            ),
            _make_skill(
                "security", "Security best practices",
                "when handling auth or secrets",
                "Never store secrets in code.",
            ),
        ]
        matched = match_for_task("write tests for auth", skills)
        assert len(matched) >= 1
        names = [s.metadata.name for s in matched]
        assert "testing" in names

        context = build_selective_context(matched)
        assert "[Skills]" in context
        assert "testing" in context.lower()

    def test_index_contains_only_names_and_descriptions(self):
        skills = [
            _make_skill(
                "deployment", "Deploy to production",
                "when deploying", "Full deployment procedure here.",
            ),
        ]
        index = build_skill_index(skills)
        assert "deployment" in index.lower()
        assert "Deploy to production" in index
        assert "Full deployment procedure" not in index

    def test_empty_task_returns_no_skills(self):
        skills = [
            _make_skill("a", "desc", "when", "content"),
        ]
        matched = match_for_task("", skills)
        assert len(matched) == 0

    def test_max_three_skills_returned(self):
        skills = [
            _make_skill(
                f"skill-{i}", f"testing skill {i}",
                "testing", f"content {i}",
            )
            for i in range(10)
        ]
        matched = match_for_task("testing", skills)
        assert len(matched) <= 3


class TestBackupRollback:
    """E2E: file_write with backup → verify rollback on failure."""

    @pytest.mark.asyncio
    async def test_backup_created_on_write(self, tmp_path):
        (tmp_path / "existing.py").write_text("original")
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))

        calls = [
            ToolCall(
                "file_write",
                {"path": "existing.py", "content": "modified"},
            ),
        ]
        results = await ex.execute_round(calls)
        assert results[0].success is True

        backup_dir = tmp_path / ".maggy-backup"
        assert backup_dir.exists()

    @pytest.mark.asyncio
    async def test_file_edit_round_trip(self, tmp_path):
        (tmp_path / "target.py").write_text("x = 1\ny = 2\n")
        sb = ToolSandbox(str(tmp_path))
        ex = ToolExecutor(sb, str(tmp_path))

        model_output = (
            '```tool_call\n{"name": "file_edit", "params": '
            '{"path": "target.py", "old": "x = 1", "new": "x = 99"}}'
            "\n```"
        )
        calls = parse_tool_calls(model_output)
        results = await ex.execute_round(calls)

        assert results[0].success is True
        content = (tmp_path / "target.py").read_text()
        assert "x = 99" in content
        assert "y = 2" in content


class TestApprovalRestEndpoints:
    """E2E: approval store → FastAPI routes → HTTP responses."""

    @pytest.fixture
    def client(self, tmp_path):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from maggy.api.routes_approval import router

        app = FastAPI()
        app.include_router(router)
        app.state.approval_store = ApprovalStore(
            str(tmp_path / "approvals.db"),
        )
        return TestClient(app)

    def test_pending_empty(self, client):
        resp = client.get("/api/approval/pending")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_full_approval_cycle_via_http(self, client, tmp_path):
        store = client.app.state.approval_store
        req = ApprovalRequest(
            action="file_write", risk="write",
            context="write test.py", status="pending",
        )
        store.save(req)

        resp = client.get("/api/approval/pending")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == req.id

        resp = client.post(f"/api/approval/{req.id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        resp = client.get("/api/approval/pending")
        assert len(resp.json()["items"]) == 0

        resp = client.get("/api/approval/history")
        history = resp.json()["items"]
        assert len(history) == 1
        assert history[0]["resolved_by"] == "human"

    def test_reject_via_http(self, client, tmp_path):
        store = client.app.state.approval_store
        req = ApprovalRequest(
            action="git_commit", risk="write",
            context="commit msg", status="pending",
        )
        store.save(req)

        resp = client.post(f"/api/approval/{req.id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_approve_nonexistent_404(self, client):
        resp = client.post("/api/approval/doesnotexist/approve")
        assert resp.status_code == 404
