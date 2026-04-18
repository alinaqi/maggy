"""Executor — TDD pipeline that spawns claude -p with iCPG-enriched prompts.

Reuses claude-bootstrap's iCPG CLI for codebase intelligence. Picks the right
working directory based on ticket keywords and configured codebase paths.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import MaggyConfig
from src.providers.base import IssueTrackerProvider, Task

logger = logging.getLogger(__name__)

CLAUDE_BIN = "claude"


class ExecutorService:
    def __init__(self, cfg: MaggyConfig, provider: IssueTrackerProvider):
        self.cfg = cfg
        self.provider = provider
        self._sessions: dict[str, dict] = {}

    async def start(self, task_id: str, mode: str = "tdd", working_dir: str | None = None) -> str:
        """Spawn a Claude Code session for this task. Returns session_id.

        mode='tdd' runs the full plan→tests→implement cycle.
        mode='plan' generates a plan only and posts to the ticket.
        """
        if mode not in ("tdd", "plan"):
            raise ValueError(f"Unknown mode {mode!r} — expected 'tdd' or 'plan'")

        task = await self.provider.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Resolve & validate working_dir against configured codebase roots.
        # Prevents a caller from running claude --dangerously-skip-permissions
        # in arbitrary filesystem locations.
        wd = self._resolve_working_dir(working_dir, task)
        session_id = uuid.uuid4().hex[:10]

        session = {
            "id": session_id,
            "task_id": task_id,
            "task_title": task.title,
            "mode": mode,
            "working_dir": wd,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "output": "",
        }
        self._sessions[session_id] = session

        # Run in background
        asyncio.create_task(self._run(session_id, task, wd, mode))
        return session_id

    def get_session(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        return list(self._sessions.values())

    def _resolve_working_dir(self, requested: str | None, task: Task) -> str:
        """Resolve working_dir, enforcing it stays inside a configured codebase.

        If `requested` is None → auto-pick via keyword match.
        If `requested` is provided → resolve to absolute path and verify it's
        inside one of the configured codebase roots (prevents arbitrary cwd).
        Raises ValueError on violation.
        """
        if not self.cfg.codebases:
            raise ValueError("No codebases configured")

        # Build the allowed roots set (absolute, resolved)
        allowed_roots = [Path(c.path).expanduser().resolve() for c in self.cfg.codebases]

        if requested:
            candidate = Path(requested).expanduser().resolve()
            for root in allowed_roots:
                try:
                    candidate.relative_to(root)
                    return str(candidate)
                except ValueError:
                    continue
            raise ValueError(
                f"working_dir {requested!r} is not inside any configured codebase. "
                f"Allowed roots: {[str(r) for r in allowed_roots]}"
            )

        return self._pick_working_dir(task)

    def _pick_working_dir(self, task: Task) -> str:
        """Match ticket title/body against configured codebases by keyword.

        Simple heuristic: count how many codebase keys or known keywords appear
        in the task text, pick the highest scorer. Falls back to first codebase.
        """
        if not self.cfg.codebases:
            raise ValueError("No codebases configured")
        if len(self.cfg.codebases) == 1:
            return str(Path(self.cfg.codebases[0].path).expanduser().resolve())

        text = f"{task.title} {task.description} {task.board}".lower()
        scores = {}
        for cb in self.cfg.codebases:
            score = 0
            key = cb.key.lower()
            if key in text:
                score += 5
            # Repo name heuristic
            path_name = Path(cb.path).name.lower()
            if path_name != key and path_name in text:
                score += 3
            scores[cb.key] = score

        best = max(scores.items(), key=lambda x: x[1])
        if best[1] == 0:
            return str(Path(self.cfg.codebases[0].path).expanduser().resolve())
        picked = next(c for c in self.cfg.codebases if c.key == best[0])
        return str(Path(picked.path).expanduser().resolve())

    async def _run(self, session_id: str, task: Task, wd: str, mode: str) -> None:
        session = self._sessions[session_id]
        try:
            # 1. Build iCPG context (if bootstrap's iCPG is available)
            icpg_ctx = await self._build_icpg_context(task, wd)

            icpg_block = f"\n\n{icpg_ctx}\n" if icpg_ctx else ""

            if mode == "plan":
                prompt = (
                    f"Create an implementation plan for this ticket. No code changes — just a plan.\n\n"
                    f"Ticket: {task.title}\n{task.description[:1500]}"
                    f"{icpg_block}\n"
                    f"Output: numbered steps, files to touch, risks, tests to add."
                )
                ok, output = await self._run_claude(prompt, wd, max_turns=5)
                session["output"] = output[:10000]
                session["status"] = "completed" if ok else "failed"
                if not ok:
                    session["error"] = output[:500]
                # Post back to ticket only if the plan actually succeeded
                if ok and output:
                    try:
                        await self.provider.add_comment(task.id, f"## Maggy Plan\n\n{output[:4000]}")
                    except Exception as e:
                        logger.warning("Failed to post plan: %s", e)
                return

            # TDD mode: plan → tests → implement. Abort the chain on first failure —
            # running "implement" after a failed "analyze" wastes tokens.
            analysis_prompt = (
                f"Analyze this ticket against the codebase and output a concise plan.\n"
                f"Identify: files to change, functions affected, tests needed, risks.\n\n"
                f"Ticket: {task.title}\n{task.description[:1500]}"
                f"{icpg_block}"
            )
            ok, analysis = await self._run_claude(analysis_prompt, wd, max_turns=5)
            session["output"] += f"\n=== ANALYZE ===\n{analysis[:2000]}\n"
            if not ok:
                session["status"] = "failed"
                session["error"] = f"Analyze step failed: {analysis[:300]}"
                return

            tests_prompt = (
                f"Write failing test cases for this ticket (TDD — no implementation yet).\n"
                f"Use the project's existing test patterns. Commit tests separately.\n\n"
                f"Ticket: {task.title}\n{task.description[:1500]}"
                f"{icpg_block}\n"
                f"Analysis:\n{analysis[:1000]}"
            )
            ok, tests_out = await self._run_claude(tests_prompt, wd, max_turns=15)
            session["output"] += f"\n=== WRITE TESTS ===\n{tests_out[:2000]}\n"
            if not ok:
                session["status"] = "failed"
                session["error"] = f"Write-tests step failed: {tests_out[:300]}"
                return

            impl_prompt = (
                f"Implement the feature to make the failing tests pass.\n"
                f"Follow existing code patterns. Keep changes minimal.\n\n"
                f"Ticket: {task.title}\n{task.description[:1500]}"
                f"{icpg_block}\n"
                f"Run tests to verify, then commit with a conventional commit message."
            )
            ok, impl_out = await self._run_claude(impl_prompt, wd, max_turns=25)
            session["output"] += f"\n=== IMPLEMENT ===\n{impl_out[:2000]}\n"
            if not ok:
                session["status"] = "failed"
                session["error"] = f"Implement step failed: {impl_out[:300]}"
                return

            session["status"] = "completed"
            session["completed_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.exception("Execution failed")
            session["status"] = "failed"
            session["error"] = str(e)

    async def _build_icpg_context(self, task: Task, wd: str) -> str:
        """Query claude-bootstrap's iCPG CLI for symbols/blast radius/prior intents.

        Silent fallback if iCPG isn't installed or repo isn't indexed — returns empty string.
        """
        bootstrap_path = self.cfg.resolve_bootstrap_path()
        if not bootstrap_path:
            return ""

        icpg_py = bootstrap_path / "scripts" / "icpg"
        if not icpg_py.exists():
            return ""

        keywords = self._extract_keywords(f"{task.title} {task.description}")
        if not keywords:
            return ""

        # Try calling `icpg query` or fall back gracefully. We use Python -m invocation
        # to avoid needing icpg on PATH.
        symbols_out: list[str] = []
        for kw in keywords[:5]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python3", "-m", "scripts.icpg.symbols", "--keyword", kw, "--limit", "5",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(bootstrap_path),
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                text = (stdout or b"").decode("utf-8", errors="replace").strip()
                if text:
                    symbols_out.append(f"- keyword `{kw}`: {text[:300]}")
            except Exception:
                continue

        if not symbols_out:
            return ""

        return (
            "## iCPG Code Intelligence\n"
            "Pre-queried from claude-bootstrap's intent code property graph:\n\n"
            + "\n".join(symbols_out)
            + "\n\n**Use this to target your file reads and avoid searching blind.**"
        )

    STOP = {"the", "and", "for", "to", "in", "of", "a", "is", "with", "on", "from",
            "be", "as", "by", "an", "or", "not", "all", "that", "this", "are", "can",
            "should", "would", "when", "how", "what", "where", "which", "we", "need",
            "also", "been", "has", "have", "it", "its", "new", "add", "fix", "update",
            "create", "delete", "get", "set", "use"}

    def _extract_keywords(self, text: str) -> list[str]:
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
        keywords: list[str] = []
        seen: set[str] = set()
        for w in words:
            if w in self.STOP or len(w) < 3:
                continue
            if w in seen:
                continue
            seen.add(w)
            keywords.append(w)
        return keywords[:20]

    async def _run_claude(self, prompt: str, working_dir: str, max_turns: int = 20) -> tuple[bool, str]:
        """Spawn claude -p as a non-interactive subprocess on the user's local machine.

        Uses --dangerously-skip-permissions because (a) there's no terminal to
        answer permission prompts, and (b) the user explicitly authorized this
        execution by clicking Execute on the ticket.

        Returns (success, output). success=False on timeout, non-zero exit, or
        missing binary. Caller is responsible for flipping the session status
        to 'failed' when success=False — this function never silently masks
        a failed run as completed.
        """
        cmd = [
            CLAUDE_BIN,
            "-p", prompt,
            "--output-format", "text",
            "--max-turns", str(max_turns),
            "--dangerously-skip-permissions",
        ]
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=working_dir,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
            text = (stdout or b"").decode("utf-8", errors="replace")
            if proc.returncode != 0:
                return False, f"claude exited with status {proc.returncode}\n{text}"
            return True, text
        except asyncio.TimeoutError:
            # Kill the subprocess — wait_for alone doesn't terminate it.
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
            return False, "claude timed out after 10 minutes (process terminated)"
        except FileNotFoundError:
            return False, "`claude` CLI not found on PATH. Install Claude Code first."
        except Exception as e:
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
            return False, f"claude subprocess error: {e}"
