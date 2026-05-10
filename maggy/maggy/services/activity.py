"""CLI activity scanner — detects running sessions and recent prompts."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ActiveSession:
    """A currently running CLI session."""

    cli: str
    session_id: str
    project: str
    project_path: str
    status: str  # "running" | "agent"
    last_prompt: str
    agent_name: str
    team_name: str
    pid: int


@dataclass
class RecentPrompt:
    """A recent user prompt from CLI history."""

    cli: str
    text: str
    project: str
    timestamp: str
    session_id: str


class ActivityService:
    """Scans CLI histories and processes."""

    def get_activity(self) -> dict:
        sessions = _scan_processes()
        prompts = _recent_prompts()
        return {
            "sessions": [asdict(s) for s in sessions],
            "recent": [asdict(p) for p in prompts],
        }


# ── Process scanning ──────────────────────────────


def _scan_processes() -> list[ActiveSession]:
    """Find running claude/codex/kimi processes."""
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True,
            text=True, timeout=5,
        )
        lines = result.stdout.splitlines()
    except (subprocess.SubprocessError, OSError):
        return []
    return _parse_claude_processes(
        [l for l in lines if "claude" in l.lower()],
    )


def _parse_claude_processes(
    lines: list[str],
) -> list[ActiveSession]:
    """Parse ps aux lines for Claude CLI sessions."""
    sessions: list[ActiveSession] = []
    for line in lines:
        if not _is_cli_process(line):
            continue
        pid = _extract_pid(line)
        if not pid:
            continue
        cwd = _get_cwd(pid)
        project = Path(cwd).name if cwd else ""
        agent = _extract_flag(line, "--agent-name")
        team = _extract_flag(line, "--team-name")
        status = "agent" if agent else "running"
        sessions.append(ActiveSession(
            cli="claude", session_id="",
            project=project, project_path=cwd,
            status=status, last_prompt="",
            agent_name=agent, team_name=team,
            pid=pid,
        ))
    return sessions


def _is_cli_process(line: str) -> bool:
    """Filter real CLI processes from app helpers."""
    lower = line.lower()
    if "claude.app" in lower:
        return False
    if "grep" in lower:
        return False
    if "claude helper" in lower:
        return False
    return bool(re.search(
        r'(?:^|/|\s)claude\s+--', line,
    ))


def _extract_pid(line: str) -> int:
    """Extract PID from ps aux line."""
    parts = line.split()
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 0


def _extract_flag(line: str, flag: str) -> str:
    """Extract --flag value from command line."""
    idx = line.find(flag)
    if idx < 0:
        return ""
    rest = line[idx + len(flag):].strip()
    if not rest:
        return ""
    return rest.split()[0] if rest else ""


def _get_cwd(pid: int) -> str:
    """Get working directory of a process (macOS)."""
    try:
        result = subprocess.run(
            ["lsof", "-p", str(pid), "-Fn"],
            capture_output=True, text=True, timeout=3,
        )
        for line in result.stdout.splitlines():
            if line.startswith("n") and "/" in line:
                path = line[1:]
                if Path(path).is_dir():
                    return path
    except (subprocess.SubprocessError, OSError):
        pass
    return ""


# ── History scanning ──────────────────────────────


def _recent_prompts(
    claude_dir: Path | None = None,
    codex_dir: Path | None = None,
    kimi_dir: Path | None = None,
    limit: int = 15,
) -> list[RecentPrompt]:
    """Read recent prompts from all CLI histories."""
    home = Path.home()
    c_dir = claude_dir or (home / ".claude")
    x_dir = codex_dir or (home / ".codex")
    k_dir = kimi_dir or (home / ".kimi")

    prompts: list[RecentPrompt] = []
    prompts.extend(_read_claude_history(c_dir))
    prompts.extend(_read_codex_history(x_dir))
    prompts.extend(_read_kimi_history(k_dir))

    prompts.sort(key=lambda p: p.timestamp, reverse=True)
    return prompts[:limit]


def _read_claude_history(
    claude_dir: Path,
) -> list[RecentPrompt]:
    """Parse ~/.claude/history.jsonl."""
    path = claude_dir / "history.jsonl"
    if not path.exists():
        return []
    prompts: list[RecentPrompt] = []
    try:
        for line in _tail_lines(path, 50):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = entry.get("display", "")
            if not text:
                continue
            ts = entry.get("timestamp", 0)
            project = entry.get("project", "")
            prompts.append(RecentPrompt(
                cli="claude", text=text[:200],
                project=Path(project).name if project else "",
                timestamp=_ms_to_iso(ts),
                session_id=entry.get("sessionId", ""),
            ))
    except OSError:
        pass
    return prompts


def _read_codex_history(
    codex_dir: Path,
) -> list[RecentPrompt]:
    """Parse ~/.codex/history.jsonl."""
    path = codex_dir / "history.jsonl"
    if not path.exists():
        return []
    prompts: list[RecentPrompt] = []
    try:
        for line in _tail_lines(path, 50):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = entry.get("text", "")
            if not text:
                continue
            ts = entry.get("ts", 0)
            prompts.append(RecentPrompt(
                cli="codex", text=text[:200],
                project="",
                timestamp=_s_to_iso(ts),
                session_id=entry.get("session_id", ""),
            ))
    except OSError:
        pass
    return prompts


def _read_kimi_history(
    kimi_dir: Path,
) -> list[RecentPrompt]:
    """Parse ~/.kimi/user-history/*.jsonl."""
    hist_dir = kimi_dir / "user-history"
    if not hist_dir.is_dir():
        return []
    prompts: list[RecentPrompt] = []
    try:
        for f in sorted(
            hist_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:3]:
            mtime = datetime.fromtimestamp(
                f.stat().st_mtime, tz=timezone.utc,
            ).isoformat()
            for line in _tail_lines(f, 10):
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = entry.get("content", "")
                if text:
                    prompts.append(RecentPrompt(
                        cli="kimi", text=text[:200],
                        project="", timestamp=mtime,
                        session_id=f.stem,
                    ))
    except OSError:
        pass
    return prompts


# ── Helpers ───────────────────────────────────────


def _tail_lines(path: Path, n: int) -> list[str]:
    """Read last N non-empty lines from a file."""
    try:
        lines = path.read_text().splitlines()
        return [l for l in lines if l.strip()][-n:]
    except OSError:
        return []


def _ms_to_iso(ms: int | float) -> str:
    """Convert milliseconds epoch to ISO string."""
    if not ms:
        return ""
    try:
        dt = datetime.fromtimestamp(
            ms / 1000, tz=timezone.utc,
        )
        return dt.isoformat()
    except (ValueError, OSError):
        return ""


def _s_to_iso(s: int | float) -> str:
    """Convert seconds epoch to ISO string."""
    if not s:
        return ""
    try:
        dt = datetime.fromtimestamp(s, tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, OSError):
        return ""
