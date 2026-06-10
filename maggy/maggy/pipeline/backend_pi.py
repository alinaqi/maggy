"""Pi backend — wraps PiAdapter for non-Claude CLI models."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncGenerator

from maggy.pipeline.contracts import ExecutionContract
from maggy.pipeline.steering import needs_steering, steering_injection
from maggy.pipeline.tool_executor import ToolExecutor
from maggy.pipeline.tool_parser import extract_text_and_calls
from maggy.pipeline.tool_sandbox import ToolSandbox

if TYPE_CHECKING:
    from maggy.adapters.pi import PiAdapter
    from maggy.services.approval import ApprovalStore
    from maggy.services.chat_models import ChatSession

logger = logging.getLogger(__name__)

_PI_MODELS = frozenset({
    "deepseek", "kimi", "local", "qwen", "gemini", "codex", "grok",
    "deepseek-flash", "deepseek-pro", "gemini-flash", "gemini-flash-lite",
    "gemini-pro-search", "gpt",
})


class PiBackend:
    name = "pi"

    def __init__(
        self, pi: PiAdapter,
        approval_store: ApprovalStore | None = None,
        contract: ExecutionContract | None = None,
    ) -> None:
        self._pi = pi
        self._approval_store = approval_store
        self._contract = contract or ExecutionContract()

    def handles(self, model: str) -> bool:
        return model.lower() in _PI_MODELS

    async def execute(
        self,
        model: str,
        message: str,
        session: ChatSession,
        working_dir: str,
        project_key: str,
    ) -> AsyncGenerator[dict, None]:
        ctx = _build_context(working_dir, project_key)
        hist = getattr(session, "history_context", "") or ""
        if hist:
            session.history_context = ""
            ctx += f"[Previous conversation context]\n{hist}\n[/Previous conversation context]\n\n"
        chat_hist = _recent_messages(session, max_turns=10)
        if chat_hist:
            ctx += f"{chat_hist}\n\n"
        result = await self._pi.send_prompt(
            model, ctx + message, working_dir,
        )
        if not result.success:
            yield {"type": "error", "content": result.error or "Pi model failed"}
            return
        output = result.output or ""
        output = await self._run_tools(output, working_dir)
        if not self._contract.validate_response(output):
            output = await self._steer_if_needed(
                output, model, ctx + message, working_dir,
            )
        elif needs_steering(output):
            output = await self._steer_if_needed(
                output, model, ctx + message, working_dir,
            )
        yield {"type": "text", "content": output}
        yield {
            "type": "result",
            "cost_usd": result.cost_usd,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }

    async def _run_tools(
        self, output: str, working_dir: str,
        max_rounds: int = 3,
    ) -> str:
        sandbox = ToolSandbox(working_dir)
        executor = ToolExecutor(
            sandbox, working_dir,
            approval_store=self._approval_store,
        )
        for _ in range(max_rounds):
            parsed = extract_text_and_calls(output)
            if not parsed["calls"]:
                break
            results = await executor.execute_round(parsed["calls"])
            tool_output = "\n".join(
                f"[{r.tool_name}] {'OK' if r.success else 'FAIL'}: {r.output[:500]}"
                for r in results
            )
            output = f"{parsed['text']}\n\n## Tool Results\n{tool_output}"
        executor._cleanup_backups()
        return output

    async def _steer_if_needed(
        self, output: str, model: str,
        full_prompt: str, working_dir: str,
    ) -> str:
        if not needs_steering(output):
            return output
        logger.info("Steering: response was advise-only, re-prompting")
        steer_prompt = (
            f"{full_prompt}\n\n"
            f"[Previous response was advise-only]\n{output[:1000]}\n"
            f"[/Previous response]\n\n{steering_injection()}"
        )
        retry = await self._pi.send_prompt(
            model, steer_prompt, working_dir,
        )
        if retry.success and retry.output:
            return await self._run_tools(retry.output, working_dir)
        return output


def _recent_messages(session, max_turns: int = 10) -> str:
    msgs = getattr(session, "messages", None) or []
    if not msgs:
        return ""
    recent = msgs[-max_turns:]
    lines = ["[Recent conversation]"]
    for m in recent:
        role = getattr(m, "role", "user")
        content = getattr(m, "content", "") or ""
        content = content[:500]
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    lines.append("[/Recent conversation]")
    return "\n".join(lines)


def _build_context(working_dir: str, project_key: str) -> str:
    base = (
        "You are Maggy, an autonomous AI engineering agent. "
        "Execute tasks directly — read files, edit code, run commands and tests. "
        "Never tell the user what to do; do it yourself and report the result. "
        f"Working directory: {working_dir}\n\n"
        "When you need to execute actions, emit structured tool calls:\n"
        "```tool_call\n"
        '{"name": "file_read", "params": {"path": "src/main.py"}}\n'
        "```\n"
        "Available tools: file_read, grep, git_status, git_diff, "
        "git_log, test_run, file_write, file_edit, git_commit.\n\n"
    )
    try:
        from maggy.skills.injector import match_skills
        from maggy.skills.registry import SkillRegistry
        from maggy.skills.selective import build_skill_index
        reg = SkillRegistry()
        reg.load_global()
        if project_key:
            reg.load_project(project_key, working_dir)
        skills = reg.resolve(project_key or None)
        matched = match_skills(skills, working_dir)
        index = build_skill_index(matched)
        if index:
            return f"{base}{index}\n\n"
    except Exception as e:
        logger.debug("Pi skill injection skipped: %s", e)
    return base
