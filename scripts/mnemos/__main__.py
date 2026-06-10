"""CLI entry point for Mnemos -- Task-Scoped Memory Lifecycle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .checkpoint import load_checkpoint, write_checkpoint
from .claude_log import ingest_all, ingest_session
from .consolidation import micro_consolidate
from .fatigue import compute_fatigue, read_fatigue_file
from .haziness import WEIGHTS, band, compute_haze, dominant_dim
from .models import FatigueState, MnemoNode, _now, _uuid
from .signals import get_session_stats
from .store import MnemosStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='mnemos',
        description='Mnemos -- Task-Scoped Memory Lifecycle'
    )
    parser.add_argument(
        '--version', action='version', version=f'mnemos {__version__}'
    )
    parser.add_argument(
        '--project', default='.', help='Project directory (default: .)'
    )
    sub = parser.add_subparsers(dest='command')

    # --- init ---
    sub.add_parser('init', help='Initialize .mnemos/ directory and database')

    # --- status ---
    sub.add_parser('status', help='Show Mnemos statistics and fatigue')

    # --- fatigue ---
    sub.add_parser('fatigue', help='Show detailed fatigue breakdown')

    # --- checkpoint ---
    p_cp = sub.add_parser('checkpoint', help='Write a checkpoint')
    p_cp.add_argument(
        '--force', action='store_true', help='Write even if fatigue is low'
    )
    p_cp.add_argument('--task-id', help='Task ID for checkpoint')

    # --- resume ---
    p_resume = sub.add_parser(
        'resume', help='Output latest checkpoint for context injection'
    )
    p_resume.add_argument('--path', help='Specific checkpoint file path')

    # --- consolidate ---
    p_cons = sub.add_parser(
        'consolidate', help='Run micro-consolidation pass'
    )
    p_cons.add_argument('--scope', default='', help='Current scope tag')

    # --- nodes ---
    p_nodes = sub.add_parser('nodes', help='List active MnemoNodes')
    p_nodes.add_argument('--type', dest='node_type', help='Filter by type')
    p_nodes.add_argument(
        '--all', action='store_true', help='Include non-active nodes'
    )

    # --- add ---
    p_add = sub.add_parser('add', help='Add a MnemoNode')
    p_add.add_argument('type', choices=[
        'goal', 'constraint', 'context', 'working', 'result'
    ])
    p_add.add_argument('content', help='Node content')
    p_add.add_argument('--task-id', default='manual', help='Task ID')
    p_add.add_argument('--scope', nargs='+', default=[], help='Scope tags')

    # --- bridge-icpg ---
    sub.add_parser(
        'bridge-icpg', help='Import iCPG ReasonNodes as MnemoNodes'
    )

    # --- ingest-claude ---
    p_ic = sub.add_parser(
        'ingest-claude',
        help='Ingest Claude Code transcripts into mnemos',
    )
    p_ic.add_argument('--session', help='Specific sessionId to ingest')
    p_ic.add_argument(
        '--transcript', help='Path to a specific JSONL transcript file'
    )
    p_ic.add_argument('--slug', help='Ingest only files under this slug dir')
    p_ic.add_argument(
        '--all', action='store_true',
        help='Ingest every transcript under --projects-root',
    )
    p_ic.add_argument(
        '--projects-root',
        help='Override Claude Code projects dir (default ~/.claude/projects)',
    )
    p_ic.add_argument(
        '--no-redact', action='store_true',
        help='Disable secret redaction (not recommended)',
    )

    # --- haze ---
    p_hz = sub.add_parser(
        'haze', help='Show per-session Claude haziness scores'
    )
    p_hz.add_argument('--session', help='Score one session by id')
    p_hz.add_argument('--slug', help='Score all sessions under a slug')
    p_hz.add_argument(
        '--recent', type=int, default=10,
        help='Show N most-recently-ingested sessions (default 10)',
    )
    p_hz.add_argument(
        '--explain', action='store_true',
        help='Dump contributing turns for each dim (requires --session)',
    )
    p_hz.add_argument(
        '--quiet', action='store_true',
        help='Suppress output (for hook use)',
    )

    args = parser.parse_args(argv)
    store = MnemosStore(args.project)

    if args.command == 'init':
        return cmd_init(store)
    elif args.command == 'status':
        return cmd_status(store, args)
    elif args.command == 'fatigue':
        return cmd_fatigue(store, args)
    elif args.command == 'checkpoint':
        return cmd_checkpoint(store, args)
    elif args.command == 'resume':
        return cmd_resume(args)
    elif args.command == 'consolidate':
        return cmd_consolidate(store, args)
    elif args.command == 'nodes':
        return cmd_nodes(store, args)
    elif args.command == 'add':
        return cmd_add(store, args)
    elif args.command == 'bridge-icpg':
        return cmd_bridge_icpg(store, args)
    elif args.command == 'ingest-claude':
        return cmd_ingest_claude(store, args)
    elif args.command == 'haze':
        return cmd_haze(store, args)
    else:
        parser.print_help()
        return 1


def cmd_init(store: MnemosStore) -> int:
    store.init_db()
    print(f'Initialized Mnemos at {store.mnemos_dir}')
    print(f'  Database: {store.db_path}')
    print(f'  .gitignore: created')
    return 0


def cmd_status(store: MnemosStore, args) -> int:
    if not store.exists():
        print('No Mnemos database. Run `mnemos init` first.')
        return 0

    stats = store.get_stats()
    fatigue_data = read_fatigue_file(args.project)

    print('MNEMOS STATUS')
    print(f'  Active nodes:     {stats["active"]}')
    print(f'  Compressed:       {stats["compressed"]}')
    print(f'  Evicted:          {stats["evicted"]}')
    print(f'  Total nodes:      {stats["total_nodes"]}')
    print(f'  Checkpoints:      {stats["checkpoints"]}')

    if stats['by_type']:
        parts = [f'{t}:{c}' for t, c in stats['by_type'].items()]
        print(f'  By type:          {", ".join(parts)}')

    # Show live fatigue if available
    if fatigue_data:
        used = fatigue_data.get('used_percentage', 0)
        remaining = fatigue_data.get('remaining_percentage', 100)
        print(f'\n  Context usage:    {used:.1f}% used, {remaining:.1f}% remaining')

        # Compute full fatigue from observable signals
        fatigue = compute_fatigue(fatigue_data, args.project)
        state_icons = {
            'flow': '+', 'compress': '~',
            'pre_sleep': '!', 'rem': '!!', 'emergency': 'XXX'
        }
        icon = state_icons.get(fatigue.state, '?')
        print(f'  Fatigue:          [{icon}] {fatigue.composite_score:.2f} ({fatigue.state})')

    # Latest checkpoint
    cp = store.get_latest_checkpoint()
    if cp:
        print(f'\n  Last checkpoint:  {cp.id[:8]} ({cp.created_at})')
        print(f'    Goal: {cp.goal[:60]}')
        print(f'    Fatigue then: {cp.fatigue_at_checkpoint:.2f}')

    return 0


def cmd_fatigue(store: MnemosStore, args) -> int:
    fatigue_data = read_fatigue_file(args.project)
    if not fatigue_data:
        print('No fatigue data. Statusline not configured or no API calls yet.')
        print('Configure mnemos-statusline.sh to start tracking.')
        return 0

    fatigue = compute_fatigue(fatigue_data, args.project)
    state_bar = _fatigue_bar(fatigue.composite_score)

    print('MNEMOS FATIGUE ANALYSIS')
    print(f'  {state_bar}')
    print(f'  Composite: {fatigue.composite_score:.4f} -> {fatigue.state.upper()}')
    print()
    print('  Dimensions (all passively observed from hooks):')
    print(f'    Token utilization: {fatigue.token_utilization:.4f}  (weight: 0.40)  [statusline]')
    print(f'    Scope scatter:     {fatigue.scope_scatter:.4f}  (weight: 0.25)  [PreToolUse file paths]')
    print(f'    Re-read ratio:     {fatigue.reread_ratio:.4f}  (weight: 0.20)  [PreToolUse Read calls]')
    print(f'    Error density:     {fatigue.error_density:.4f}  (weight: 0.15)  [PostToolUse outcomes]')
    print()

    # Signal stats
    sig_stats = get_session_stats(args.project)
    if sig_stats.get('total_signals', 0) > 0:
        print(f'  Signal log: {sig_stats["total_signals"]} events')
        if sig_stats.get('tool_calls'):
            tools = ', '.join(f'{k}:{v}' for k, v in sig_stats['tool_calls'].items())
            print(f'    Tools: {tools}')
        print(f'    Unique files read: {sig_stats.get("unique_files_read", 0)}')
        print(f'    Re-reads: {sig_stats.get("rereads", 0)}')
        print(f'    Errors: {sig_stats.get("errors", 0)}/{sig_stats.get("total_outcomes", 0)}')
        print()

    # Recommendations
    if fatigue.state == 'flow':
        print('  Status: Operating normally. No action needed.')
    elif fatigue.state == 'compress':
        print('  Status: Consider micro-consolidation.')
        print('  Run: mnemos consolidate')
    elif fatigue.state == 'pre_sleep':
        print('  Status: Write checkpoint and consolidate.')
        print('  Run: mnemos checkpoint && mnemos consolidate')
    elif fatigue.state == 'rem':
        print('  WARNING: High fatigue. Checkpoint immediately.')
        print('  Run: mnemos checkpoint --force')
    elif fatigue.state == 'emergency':
        print('  EMERGENCY: Context nearly full. Checkpoint NOW.')
        print('  Run: mnemos checkpoint --force')

    # Log it
    if store.exists():
        store.log_fatigue(fatigue)

    return 0


def cmd_checkpoint(store: MnemosStore, args) -> int:
    if not store.exists():
        store.init_db()

    # Check fatigue to decide if needed
    fatigue_data = read_fatigue_file(args.project)
    fatigue = compute_fatigue(fatigue_data, args.project) if fatigue_data else None

    if fatigue and not args.force:
        if fatigue.composite_score < 0.40:
            print(f'Fatigue low ({fatigue.composite_score:.2f}). '
                  f'Use --force to checkpoint anyway.')
            return 0

    # Try to load iCPG store if available
    icpg_store = _try_load_icpg(args.project)

    cp = write_checkpoint(
        store,
        fatigue_score=fatigue.composite_score if fatigue else 0.0,
        icpg_store=icpg_store,
        task_id=getattr(args, 'task_id', None)
    )

    print(f'Checkpoint written: {cp.id[:8]}')
    print(f'  Goal: {cp.goal[:60]}')
    print(f'  Constraints: {len(cp.active_constraints)}')
    print(f'  Results: {len(cp.active_results)}')
    print(f'  Fatigue: {cp.fatigue_at_checkpoint:.2f}')
    print(f'  File: .mnemos/checkpoint-latest.json')
    return 0


def cmd_resume(args) -> int:
    output = load_checkpoint(
        project_dir=args.project,
        path=getattr(args, 'path', None)
    )
    if not output:
        print('No checkpoint found to resume from.')
        return 0

    # Output formatted checkpoint (this goes into agent context)
    print(output)
    return 0


def cmd_consolidate(store: MnemosStore, args) -> int:
    if not store.exists():
        print('No Mnemos database. Run `mnemos init` first.')
        return 1

    scope = getattr(args, 'scope', '')
    stats = micro_consolidate(store, current_scope=scope)

    print(f'Micro-consolidation complete:')
    print(f'  Compressed: {stats["compressed"]} ResultNodes')
    print(f'  Evicted: {stats["evicted"]} ContextNodes')
    print(f'  Decayed: {stats["decayed"]} node weights')
    return 0


def cmd_nodes(store: MnemosStore, args) -> int:
    if not store.exists():
        print('No Mnemos database.')
        return 0

    node_type = getattr(args, 'node_type', None)
    show_all = getattr(args, 'all', False)

    if node_type:
        if show_all:
            # Get all statuses
            nodes = []
            for status in ('active', 'compressed', 'evicted'):
                nodes.extend(store.get_by_type(node_type, status=status))
        else:
            nodes = store.get_by_type(node_type)
    else:
        if show_all:
            nodes = []
            with store._conn() as conn:
                rows = conn.execute(
                    'SELECT * FROM mnemo_nodes ORDER BY type, activation_weight DESC'
                ).fetchall()
            nodes = [store._row_to_node(r) for r in rows]
        else:
            nodes = store.get_active_nodes()

    if not nodes:
        print('No matching nodes.')
        return 0

    status_icons = {
        'active': '+', 'compressed': '~', 'evicted': '-',
        'promoted': '^', 'handed_off': '>'
    }

    print(f'MNEMO NODES ({len(nodes)}):')
    for n in nodes:
        icon = status_icons.get(n.status, '?')
        weight = f'{n.activation_weight:.2f}'
        content = n.summary or n.content
        content_preview = content[:60] if content else '(empty)'
        print(f'  [{icon}] {n.type:12s} w={weight} {content_preview}')
        if n.scope_tags:
            print(f'       scope: {", ".join(n.scope_tags[:3])}')

    return 0


def cmd_add(store: MnemosStore, args) -> int:
    if not store.exists():
        store.init_db()

    node = MnemoNode(
        type=args.type,
        task_id=args.task_id,
        content=args.content,
        scope_tags=args.scope,
        origin='agent_generated'
    )
    store.create_node(node)

    print(f'Created {args.type} node: {node.id[:8]}')
    print(f'  Content: {args.content[:60]}')
    if args.scope:
        print(f'  Scope: {", ".join(args.scope)}')
    return 0


def cmd_bridge_icpg(store: MnemosStore, args) -> int:
    if not store.exists():
        store.init_db()

    icpg_store = _try_load_icpg(args.project)
    if not icpg_store:
        print('No iCPG database found. Run `icpg init` first.')
        return 1

    stats = store.load_from_icpg(icpg_store)
    print(f'iCPG Bridge complete:')
    print(f'  GoalNodes imported: {stats["goals_imported"]}')
    print(f'  ConstraintNodes imported: {stats["constraints_imported"]}')
    return 0


def cmd_ingest_claude(store: MnemosStore, args) -> int:
    if not store.exists():
        store.init_db()
    else:
        store.ensure_schema()  # migrate pre-feature dbs to add claude_* tables

    redact_text = not getattr(args, 'no_redact', False)
    projects_root = getattr(args, 'projects_root', None)
    if projects_root:
        projects_root = Path(projects_root).expanduser()

    transcript = getattr(args, 'transcript', None)
    slug = getattr(args, 'slug', None)
    session = getattr(args, 'session', None)
    do_all = getattr(args, 'all', False)

    if transcript:
        result = ingest_session(
            store, Path(transcript), redact_text=redact_text
        )
        if result.get('skipped'):
            print(f'Skipped: {result.get("reason", "unknown")}')
            return 0
        print(f'Session {result["session_id"][:8]}: '
              f'+{result["turns"]} turns '
              f'({"new" if result["new_session"] else "resume"})')
        if result.get('session_id'):
            haze = compute_haze(store, result['session_id'])
            _print_haze_line(haze)
        return 0

    root = projects_root or Path.home() / '.claude' / 'projects'
    if slug:
        session_dir = root / slug
        if not session_dir.exists():
            print(f'No slug dir: {session_dir}')
            return 1
        files = list(session_dir.glob('*.jsonl'))
    elif session:
        # Search all slug dirs for a <session>.jsonl file.
        files = list(root.glob(f'*/{session}.jsonl'))
        if not files:
            print(f'No transcript for session {session}')
            return 1
    elif do_all:
        stats = ingest_all(store, projects_root=root)
        # Score every ingested session. Bulk-scoring is cheap (~ms per session)
        # and means `mnemos haze --recent N` works immediately after ingest.
        scored = 0
        with store._conn() as conn:
            session_ids = [r['id'] for r in conn.execute(
                'SELECT id FROM claude_sessions'
            ).fetchall()]
        for sid in session_ids:
            compute_haze(store, sid)
            scored += 1
        print(f'Ingested {stats["files"]} files '
              f'({stats["sessions"]} new sessions, '
              f'{stats["turns"]} turns, {stats["skipped"]} skipped, '
              f'{scored} scored)')
        return 0
    else:
        print('Provide --transcript, --session, --slug, or --all')
        return 1

    total_turns = 0
    new_sessions = 0
    for path in files:
        r = ingest_session(store, path, redact_text=redact_text)
        if r.get('skipped'):
            continue
        total_turns += r.get('turns', 0)
        if r.get('new_session'):
            new_sessions += 1
        if r.get('session_id'):
            compute_haze(store, r['session_id'])
    print(f'Ingested {len(files)} files '
          f'({new_sessions} new, {total_turns} turns)')
    return 0


def cmd_haze(store: MnemosStore, args) -> int:
    if not store.exists():
        print('No Mnemos database. Run `mnemos init` first.')
        return 1
    store.ensure_schema()  # migrate pre-feature dbs to add claude_* tables

    quiet = getattr(args, 'quiet', False)
    session = getattr(args, 'session', None)
    slug = getattr(args, 'slug', None)
    explain = getattr(args, 'explain', False)
    recent = getattr(args, 'recent', 10)

    if session:
        haze = compute_haze(store, session)
        if quiet:
            return 0
        _print_haze_detail(haze)
        if explain:
            _explain_haze(store, session)
        return 0

    with store._conn() as conn:
        if slug:
            rows = conn.execute(
                """SELECT s.id, s.project_path, s.turn_count, s.last_ingested_at,
                          h.composite, h.correction_density, h.redo_ratio,
                          h.first_try_error_rate, h.orphan_tool_use_rate,
                          h.backtrack_norm
                   FROM claude_sessions s
                   LEFT JOIN claude_haze h ON h.session_id = s.id
                   WHERE s.project_slug = ?
                   ORDER BY s.last_ingested_at DESC LIMIT ?""",
                (slug, recent),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT s.id, s.project_path, s.turn_count, s.last_ingested_at,
                          h.composite, h.correction_density, h.redo_ratio,
                          h.first_try_error_rate, h.orphan_tool_use_rate,
                          h.backtrack_norm
                   FROM claude_sessions s
                   LEFT JOIN claude_haze h ON h.session_id = s.id
                   ORDER BY s.last_ingested_at DESC LIMIT ?""",
                (recent,),
            ).fetchall()

    if not rows:
        if not quiet:
            print('No ingested sessions. Run `mnemos ingest-claude --all`.')
        return 0

    if quiet:
        return 0

    print(f'{"SESSION":10s} {"PROJECT":40s} {"TURNS":>6s} '
          f'{"HAZE":>6s} {"BAND":>7s} {"DOMINANT":>20s} WHEN')
    for r in rows:
        comp = r['composite']
        if comp is None:
            comp_str, band_str, dom_str = '-', '-', '-'
        else:
            dom = dominant_dim({
                'correction_density': r['correction_density'],
                'redo_ratio': r['redo_ratio'],
                'first_try_error_rate': r['first_try_error_rate'],
                'orphan_tool_use_rate': r['orphan_tool_use_rate'],
                'backtrack_norm': r['backtrack_norm'],
            })
            comp_str = f'{comp:.2f}'
            band_str = band(comp)
            dom_str = dom
        proj = (r['project_path'] or '')[-40:]
        print(f'{r["id"][:8]:10s} {proj:40s} {r["turn_count"]:>6d} '
              f'{comp_str:>6s} {band_str:>7s} {dom_str:>20s} '
              f'{r["last_ingested_at"]}')
    return 0


def _print_haze_line(haze: dict) -> None:
    comp = haze['composite']
    print(f'Haze: {comp:.2f} ({band(comp)}) '
          f'[{dominant_dim(haze)} dominant, {haze["turns_analyzed"]} turns]')


def _print_haze_detail(haze: dict) -> None:
    comp = haze['composite']
    print(f'HAZE {haze["session_id"][:8]}  '
          f'{comp:.2f} {band(comp).upper()}  '
          f'({haze["turns_analyzed"]} turns)')
    print()
    for name, weight in WEIGHTS.items():
        val = haze.get(name, 0.0)
        bar = '#' * int(val * 20) + '.' * (20 - int(val * 20))
        print(f'  {name:22s}  {val:.3f}  [{bar}]  w={weight}')


def _explain_haze(store: MnemosStore, session_id: str) -> None:
    with store._conn() as conn:
        src_row = conn.execute(
            'SELECT source_path FROM claude_sessions WHERE id = ?',
            (session_id,),
        ).fetchone()
        if not src_row:
            return
        source_path = src_row['source_path']
        turns = conn.execute(
            """SELECT idx, role, tool_name, file_path, is_error,
                      text_preview, correction_match
               FROM claude_turns WHERE session_id = ? ORDER BY idx""",
            (session_id,),
        ).fetchall()

    print()
    print('CONTRIBUTING TURNS')
    shown = 0
    for t in turns:
        interesting = (
            t['correction_match']
            or t['is_error']
            or (t['tool_name'] == 'Bash' and t['text_preview']
                and 'git' in t['text_preview'])
        )
        if not interesting:
            continue
        shown += 1
        if shown > 20:
            print(f'  ... (trimmed; see {source_path} for full log)')
            break
        marker = []
        if t['correction_match']:
            marker.append('CORRECT')
        if t['is_error']:
            marker.append('ERROR')
        if t['tool_name']:
            marker.append(t['tool_name'])
        tag = ','.join(marker) or t['role']
        preview = (t['text_preview'] or t['file_path'] or '')[:80]
        print(f'  idx={t["idx"]:<6d} [{tag:16s}] {preview}')


def _try_load_icpg(project_dir: str):
    """Try to import and load iCPG store. Returns None if unavailable."""
    try:
        icpg_path = Path(project_dir).resolve() / '.icpg' / 'reason.db'
        if not icpg_path.exists():
            return None

        # Try importing from sibling package
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from icpg.store import ICPGStore
        store = ICPGStore(project_dir)
        if store.exists():
            return store
    except ImportError:
        pass
    return None


def _fatigue_bar(score: float) -> str:
    """Render a visual fatigue bar."""
    filled = int(score * 20)
    empty = 20 - filled
    bar = '#' * filled + '.' * empty

    if score >= 0.90:
        label = 'EMERGENCY'
    elif score >= 0.75:
        label = 'REM'
    elif score >= 0.60:
        label = 'PRE-SLEEP'
    elif score >= 0.40:
        label = 'COMPRESS'
    else:
        label = 'FLOW'

    return f'[{bar}] {score:.2f} {label}'


if __name__ == '__main__':
    sys.exit(main())
