"""Ingest Claude Code transcripts into mnemos.

Claude Code writes one JSONL file per session to
    ~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl

Each line is a structured event (user, assistant, system, tool_use, tool_result,
permission-mode, ...). This module reads those files, normalises events into
`claude_turns` rows, upserts a `claude_sessions` row, and is idempotent via
`last_line_offset` resume + `INSERT OR IGNORE` on (session_id, idx).

Full content is NOT stored; only structural fields + a redacted preview.
The source JSONL remains the source of truth for `mnemos haze --explain`.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .redact import redact


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

# Event types we persist. Everything else (queue-operation, attachment delta,
# last-prompt markers, etc.) is noise for haziness scoring, so we advance
# the line cursor past them without emitting a row.
_INGESTED_TYPES = {
    'user', 'assistant', 'system', 'permission-mode', 'file-history-snapshot'
}

_CORRECTION_LEAD_RE = re.compile(
    r"^\s*(no|wait|stop|actually|undo|revert|rollback|wrong)\b",
    re.IGNORECASE,
)
_CORRECTION_PHRASE_RE = re.compile(
    r"\b(don'?t|not that|instead)\b",
    re.IGNORECASE,
)

_DISABLED_SENTINEL = 'claude-log.disabled'


def ingest_all(store, projects_root: Path | None = None) -> dict:
    """Walk ~/.claude/projects/*/*.jsonl and ingest each one.

    Respects `.mnemos/claude-log.disabled` in the per-session cwd (read from
    the first event in each file).
    """
    if projects_root is None:
        projects_root = Path.home() / '.claude' / 'projects'
    projects_root = Path(projects_root).expanduser()

    if not projects_root.exists():
        return {'files': 0, 'sessions': 0, 'turns': 0, 'skipped': 0}

    files = 0
    sessions = 0
    turns = 0
    skipped = 0
    for session_file in sorted(projects_root.glob('*/*.jsonl')):
        files += 1
        result = ingest_session(store, session_file)
        if result.get('skipped'):
            skipped += 1
            continue
        if result.get('new_session'):
            sessions += 1
        turns += result.get('turns', 0)
    return {
        'files': files, 'sessions': sessions,
        'turns': turns, 'skipped': skipped,
    }


def ingest_session(
    store, transcript_path: Path | str, *, redact_text: bool = True
) -> dict:
    """Idempotent ingest of one JSONL transcript.

    Returns {session_id, turns, new_session, skipped?}.
    """
    path = Path(transcript_path).expanduser().resolve()
    if not path.exists():
        return {'session_id': None, 'turns': 0, 'new_session': False,
                'skipped': True, 'reason': 'missing'}

    # Peek first event to learn cwd + sessionId + started_at.
    peek = _peek_session_meta(path)
    if peek is None:
        return {'session_id': None, 'turns': 0, 'new_session': False,
                'skipped': True, 'reason': 'empty'}
    session_id = peek['session_id']
    cwd = peek['cwd']
    started_at = peek['started_at']

    # Respect per-project opt-out.
    if cwd and (Path(cwd) / '.mnemos' / _DISABLED_SENTINEL).exists():
        return {'session_id': session_id, 'turns': 0, 'new_session': False,
                'skipped': True, 'reason': 'disabled'}

    project_slug = path.parent.name

    with store._conn() as conn:
        # Serialize session upsert to prevent TOCTOU on last_line_offset.
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            'SELECT last_line_offset FROM claude_sessions WHERE id = ?',
            (session_id,),
        ).fetchone()
        new_session = row is None
        start_offset = row['last_line_offset'] if row else 0

        now_iso = _utc_now_iso()
        if new_session:
            conn.execute(
                """INSERT INTO claude_sessions
                   (id, project_path, project_slug, task_id, model,
                    started_at, ended_at, turn_count, tokens_in, tokens_out,
                    source_path, last_line_offset, last_ingested_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (session_id, cwd or '', project_slug, None, None,
                 started_at, None, 0, 0, 0,
                 str(path), 0, now_iso),
            )
        # Commit the lock so the long scan below doesn't hold BEGIN IMMEDIATE.
        conn.commit()

    # Scan from start_offset; each line yields zero-or-more turn rows.
    rows, stats = _scan(path, session_id, start_offset, redact_text)

    if not rows and stats['lines_read'] == 0:
        return {'session_id': session_id, 'turns': 0,
                'new_session': new_session}

    with store._conn() as conn:
        conn.execute('BEGIN IMMEDIATE')
        inserted = 0
        for r in rows:
            cur = conn.execute(
                """INSERT OR IGNORE INTO claude_turns
                   (session_id, idx, uuid, parent_uuid, role, event_type,
                    tool_name, tool_use_id, file_path, is_error,
                    text_preview, correction_match, ts)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r['session_id'], r['idx'], r['uuid'], r['parent_uuid'],
                 r['role'], r['event_type'], r['tool_name'],
                 r['tool_use_id'], r['file_path'], r['is_error'],
                 r['text_preview'], r['correction_match'], r['ts']),
            )
            inserted += cur.rowcount

        new_offset = start_offset + stats['lines_read']
        ended_at = stats.get('last_ts') or started_at
        conn.execute(
            """UPDATE claude_sessions SET
                   last_line_offset = ?,
                   last_ingested_at = ?,
                   ended_at = COALESCE(?, ended_at),
                   turn_count = turn_count + ?,
                   tokens_in = tokens_in + ?,
                   tokens_out = tokens_out + ?,
                   model = COALESCE(?, model),
                   source_path = ?
               WHERE id = ?""",
            (new_offset,
             _utc_now_iso(),
             ended_at,
             inserted,
             stats.get('tokens_in', 0),
             stats.get('tokens_out', 0),
             stats.get('model'),
             str(path),
             session_id),
        )
        conn.commit()

        _maybe_link_task(conn, session_id, started_at,
                         stats.get('last_ts') or started_at, cwd or '')

    return {'session_id': session_id, 'turns': inserted,
            'new_session': new_session}


# --- internal helpers ---------------------------------------------------


def _peek_session_meta(path: Path) -> dict | None:
    """Learn sessionId + cwd + started_at from the transcript.

    Queue-operation events carry sessionId but no cwd. Real user/assistant
    events carry both. Walk until we find one with cwd; fall back to the
    earliest sessionId if no event has cwd.
    """
    first_sid: str | None = None
    first_ts: str = ''
    try:
        with path.open('r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = ev.get('sessionId')
                if not sid:
                    continue
                if first_sid is None:
                    first_sid = sid
                    first_ts = ev.get('timestamp') or ''
                cwd = ev.get('cwd')
                if cwd:
                    return {
                        'session_id': sid,
                        'cwd': cwd,
                        'started_at': ev.get('timestamp') or first_ts,
                    }
    except OSError:
        return None
    if first_sid:
        return {'session_id': first_sid, 'cwd': '', 'started_at': first_ts}
    return None


def _scan(
    path: Path, session_id: str, start_offset: int, redact_text: bool,
) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    lines_read = 0
    tokens_in = 0
    tokens_out = 0
    model: str | None = None
    last_ts: str | None = None

    with path.open('r', encoding='utf-8', errors='replace') as f:
        for line_no, raw in enumerate(f):
            if line_no < start_offset:
                continue
            lines_read += 1
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                continue

            ev_type = ev.get('type') or ''
            if ev_type not in _INGESTED_TYPES:
                continue

            ts = ev.get('timestamp') or ''
            if ts:
                last_ts = ts

            # Accumulate token + model on assistant turns.
            msg = ev.get('message') or {}
            if ev_type == 'assistant':
                usage = msg.get('usage') or {}
                tokens_in += int(usage.get('input_tokens') or 0)
                tokens_out += int(usage.get('output_tokens') or 0)
                model = msg.get('model') or model

            for block_row in _emit_rows(
                ev, line_no, session_id, ts, redact_text,
            ):
                rows.append(block_row)

    stats = {'lines_read': lines_read, 'tokens_in': tokens_in,
             'tokens_out': tokens_out, 'model': model, 'last_ts': last_ts}
    return rows, stats


def _emit_rows(
    ev: dict, line_no: int, session_id: str, ts: str, redact_text: bool,
) -> list[dict]:
    ev_type = ev['type']
    msg = ev.get('message') or {}
    role = msg.get('role') or ev_type
    uuid = ev.get('uuid')
    parent_uuid = ev.get('parentUuid')

    content = msg.get('content')

    # System / permission-mode / file-history-snapshot: single row, no blocks.
    if ev_type in ('system', 'permission-mode', 'file-history-snapshot'):
        text = _extract_text(msg, ev)
        preview, _ = _preview(text, redact_text)
        return [_make_row(
            session_id, line_no * 100, uuid, parent_uuid,
            ev_type, ev_type, None, None, None, 0,
            preview, 0, ts,
        )]

    # User / assistant: walk content blocks. Emit one row per block.
    blocks = _as_blocks(content)
    out: list[dict] = []
    for block_idx, block in enumerate(blocks):
        idx = line_no * 100 + block_idx
        btype = block.get('type', 'text')

        if btype == 'text':
            text = block.get('text') or ''
            preview, match = _preview(text, redact_text, is_user=(role == 'user'))
            out.append(_make_row(
                session_id, idx, uuid, parent_uuid, role, ev_type,
                None, None, None, 0, preview, match, ts,
            ))
        elif btype == 'tool_use':
            tool_name = block.get('name')
            tool_use_id = block.get('id')
            tool_input = block.get('input') or {}
            file_path = _extract_file_path(tool_name, tool_input)
            # For Bash we capture the command as preview so haze scoring can
            # detect `git revert` / `git reset --hard` without reopening JSONL.
            preview = None
            if tool_name == 'Bash':
                cmd = tool_input.get('command') or ''
                preview, _ = _preview(cmd, redact_text)
            out.append(_make_row(
                session_id, idx, uuid, parent_uuid, role, ev_type,
                tool_name, tool_use_id, file_path, 0, preview, 0, ts,
            ))
        elif btype == 'tool_result':
            tool_use_id = block.get('tool_use_id')
            is_error = 1 if block.get('is_error') else 0
            raw_result = block.get('content')
            if isinstance(raw_result, list):
                raw_result = ' '.join(
                    b.get('text', '') for b in raw_result
                    if isinstance(b, dict) and b.get('type') == 'text'
                )
            elif not isinstance(raw_result, str):
                raw_result = ''
            preview, _ = _preview(raw_result, redact_text)
            # Treat string-level "Error:" as is_error too.
            if not is_error and raw_result.startswith(('Error:', 'error:')):
                is_error = 1
            out.append(_make_row(
                session_id, idx, uuid, parent_uuid, role, ev_type,
                None, tool_use_id, None, is_error, preview, 0, ts,
            ))
        # Unknown block type: skip silently.

    if not out:
        # Edge case: empty content array. Emit a placeholder row.
        out.append(_make_row(
            session_id, line_no * 100, uuid, parent_uuid, role, ev_type,
            None, None, None, 0, None, 0, ts,
        ))
    return out


def _as_blocks(content) -> list[dict]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{'type': 'text', 'text': content}]
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def _extract_text(msg: dict, ev: dict) -> str:
    c = msg.get('content')
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return ' '.join(
            b.get('text', '') for b in c
            if isinstance(b, dict) and b.get('type') == 'text'
        )
    # Some system events put the text at the event level.
    return ev.get('text') or ev.get('content') or ''


def _extract_file_path(tool_name: str | None, tool_input: dict) -> str | None:
    if not tool_name:
        return None
    if tool_name in ('Read', 'Edit', 'Write', 'NotebookEdit'):
        return tool_input.get('file_path') or tool_input.get('path') or None
    if tool_name in ('Glob', 'Grep'):
        return tool_input.get('path') or None
    # Bash: parsing paths from commands is unreliable; leave null.
    return None


def _preview(
    text: str, redact_text: bool, *, is_user: bool = False,
) -> tuple[str | None, int]:
    if not text:
        return None, 0
    cleaned = text if not redact_text else redact(text)[0]
    preview = cleaned[:200]
    match = 0
    if is_user and len(cleaned) < 500:
        if _CORRECTION_LEAD_RE.match(cleaned) or (
            len(cleaned) < 200 and _CORRECTION_PHRASE_RE.search(cleaned)
        ):
            match = 1
    return preview, match


def _make_row(
    session_id, idx, uuid, parent_uuid, role, event_type,
    tool_name, tool_use_id, file_path, is_error,
    text_preview, correction_match, ts,
) -> dict:
    return {
        'session_id': session_id, 'idx': idx,
        'uuid': uuid, 'parent_uuid': parent_uuid,
        'role': role, 'event_type': event_type,
        'tool_name': tool_name, 'tool_use_id': tool_use_id,
        'file_path': file_path, 'is_error': is_error,
        'text_preview': text_preview,
        'correction_match': correction_match,
        'ts': ts or '',
    }


def _maybe_link_task(
    conn: sqlite3.Connection, session_id: str,
    started_at: str, ended_at: str, cwd: str,
) -> None:
    """Populate claude_sessions.task_id when a checkpoint falls inside the
    session's time window. mnemos_nodes.task_id is free-form; we only trust
    checkpoints, which are timestamped events.
    """
    if not started_at or not ended_at:
        return
    row = conn.execute(
        """SELECT task_id FROM checkpoints
           WHERE created_at >= ? AND created_at <= ?
           ORDER BY created_at DESC LIMIT 1""",
        (started_at, ended_at),
    ).fetchone()
    if row and row['task_id']:
        conn.execute(
            'UPDATE claude_sessions SET task_id = ? WHERE id = ?',
            (row['task_id'], session_id),
        )
