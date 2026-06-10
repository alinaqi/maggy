"""Per-session haziness scoring from ingested Claude transcripts.

Five dimensions, all in [0, 1]; higher = hazier:

    correction_density  (0.30) - user corrections per eligible user turn
    redo_ratio          (0.25) - Edit/Write re-edits after an error
    first_try_error_rate(0.20) - Edit/Write followed by errors in next 3 turns
    orphan_tool_use_rate(0.15) - tool_use without matching tool_result
    backtrack_norm      (0.10) - git revert/reset/restore calls, normalised

Composite = weighted sum. Written to `claude_haze`, one row per session.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

WEIGHTS = {
    'correction_density': 0.30,
    'redo_ratio': 0.25,
    'first_try_error_rate': 0.20,
    'orphan_tool_use_rate': 0.15,
    'backtrack_norm': 0.10,
}

_EDIT_TOOLS = {'Edit', 'Write', 'NotebookEdit'}

# git revert / reset --hard / restore / checkout -- <path>. Narrow to avoid
# matching `git checkout --orphan`, `git checkout --track`, etc.
_BACKTRACK_RE = re.compile(
    r'\bgit\s+(?:revert\b|reset\s+--hard\b|restore\b|checkout\s+--\s+\S)',
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def compute_haze(store, session_id: str) -> dict:
    """Compute and persist haze for one session. Returns the dim dict.

    If the session isn't in `claude_sessions` yet, returns a zero result
    without persisting (FK constraint would reject the insert).
    """
    if not _session_exists(store, session_id):
        return _zero_result(session_id, 0)

    turns = _load_turns(store, session_id)

    if not turns:
        result = _zero_result(session_id, 0)
    else:
        result = {
            'session_id': session_id,
            'correction_density': _correction_density(turns),
            'redo_ratio': _redo_ratio(turns),
            'first_try_error_rate': _first_try_error_rate(turns),
            'orphan_tool_use_rate': _orphan_tool_use_rate(turns),
            'backtrack_norm': _backtrack_norm(turns),
            'turns_analyzed': len(turns),
        }
        result['composite'] = _composite(result)

    _persist(store, result)
    return result


def band(composite: float) -> str:
    if composite < 0.25:
        return 'clear'
    if composite < 0.50:
        return 'cloudy'
    if composite < 0.75:
        return 'hazy'
    return 'lost'


def dominant_dim(result: dict) -> str:
    """Name of the weighted dim contributing most to the composite.

    Returns '-' when no dim has any contribution (all zeros), so ties at 0
    aren't reported as a meaningful signal.
    """
    contributions = [
        (name, result.get(name, 0.0) * w)
        for name, w in WEIGHTS.items()
    ]
    top = max(contributions, key=lambda item: item[1])
    if top[1] <= 0.0:
        return '-'
    return top[0]


# --- dim computations ---------------------------------------------------


def _correction_density(turns: list[dict]) -> float:
    eligible = [
        t for t in turns
        if t['role'] == 'user' and t['event_type'] == 'user'
        and t['text_preview'] is not None
        and t['tool_use_id'] is None
    ]
    if not eligible:
        return 0.0
    matches = sum(1 for t in eligible if t['correction_match'])
    return min(1.0, matches / len(eligible))


def _redo_ratio(turns: list[dict]) -> float:
    edits = [(p, t) for p, t in enumerate(turns)
             if t['tool_name'] in _EDIT_TOOLS and t['file_path']]
    if not edits:
        return 0.0

    matches = 0
    for pos, edit in edits:
        start = max(0, pos - 5)
        prior_same_file = [
            (p, u) for p, u in enumerate(turns[start:pos], start=start)
            if u['tool_name'] in _EDIT_TOOLS
            and u['file_path'] == edit['file_path']
        ]
        if not prior_same_file:
            continue
        earliest_pos = min(p for p, _ in prior_same_file)
        errored = any(
            turns[p]['is_error']
            for p in range(earliest_pos + 1, pos)
        )
        if errored:
            matches += 1
    return min(1.0, matches / len(edits))


def _first_try_error_rate(turns: list[dict]) -> float:
    edits = [(p, t) for p, t in enumerate(turns)
             if t['tool_name'] in _EDIT_TOOLS and t['file_path']]
    if not edits:
        return 0.0

    flagged = 0
    for pos, _ in edits:
        window = turns[pos + 1:pos + 4]
        if any(u['is_error'] for u in window):
            flagged += 1
    return min(1.0, flagged / len(edits))


def _orphan_tool_use_rate(turns: list[dict]) -> float:
    tool_uses = [t for t in turns
                 if t['tool_name'] and t['tool_use_id']
                 and t['role'] == 'assistant']
    if not tool_uses:
        return 0.0

    result_ids = {
        t['tool_use_id'] for t in turns
        if t['event_type'] == 'user' and t['tool_use_id']
    }
    orphaned = sum(1 for t in tool_uses if t['tool_use_id'] not in result_ids)
    return min(1.0, orphaned / len(tool_uses))


def _backtrack_norm(turns: list[dict]) -> float:
    count = 0
    for t in turns:
        if t['tool_name'] != 'Bash':
            continue
        cmd = t['text_preview'] or ''
        if _BACKTRACK_RE.search(cmd):
            count += 1
    return min(1.0, count / 5.0)


def _composite(result: dict) -> float:
    return round(sum(
        result[name] * w for name, w in WEIGHTS.items()
    ), 6)


def _zero_result(session_id: str, turn_count: int) -> dict:
    return {
        'session_id': session_id,
        'correction_density': 0.0,
        'redo_ratio': 0.0,
        'first_try_error_rate': 0.0,
        'orphan_tool_use_rate': 0.0,
        'backtrack_norm': 0.0,
        'composite': 0.0,
        'turns_analyzed': turn_count,
    }


# --- persistence --------------------------------------------------------


def _session_exists(store, session_id: str) -> bool:
    with store._conn() as conn:
        row = conn.execute(
            'SELECT 1 FROM claude_sessions WHERE id = ? LIMIT 1',
            (session_id,),
        ).fetchone()
    return row is not None


def _load_turns(store, session_id: str) -> list[dict]:
    with store._conn() as conn:
        rows = conn.execute(
            """SELECT idx, role, event_type, tool_name, tool_use_id,
                      file_path, is_error, text_preview, correction_match, ts
               FROM claude_turns
               WHERE session_id = ?
               ORDER BY idx ASC""",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _persist(store, result: dict) -> None:
    with store._conn() as conn:
        conn.execute(
            """INSERT INTO claude_haze
               (session_id, correction_density, redo_ratio,
                first_try_error_rate, orphan_tool_use_rate, backtrack_norm,
                composite, turns_analyzed, computed_at)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(session_id) DO UPDATE SET
                   correction_density=excluded.correction_density,
                   redo_ratio=excluded.redo_ratio,
                   first_try_error_rate=excluded.first_try_error_rate,
                   orphan_tool_use_rate=excluded.orphan_tool_use_rate,
                   backtrack_norm=excluded.backtrack_norm,
                   composite=excluded.composite,
                   turns_analyzed=excluded.turns_analyzed,
                   computed_at=excluded.computed_at""",
            (result['session_id'], result['correction_density'],
             result['redo_ratio'], result['first_try_error_rate'],
             result['orphan_tool_use_rate'], result['backtrack_norm'],
             result['composite'], result['turns_analyzed'],
             _utc_now_iso()),
        )
