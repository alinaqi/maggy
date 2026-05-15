#!/bin/bash
# Mnemos Compact Recovery — PRIMARY post-compaction context restore.
#
# SessionStart hook with "compact" matcher.
# Fires IMMEDIATELY when Claude resumes after compaction, before any
# agent action. This is the correct injection point per the Mnemos RFC
# (Section 12: Wake State Reconstruction).
#
# The PreToolUse marker-based inject (mnemos-post-compact-inject.sh)
# remains as a FALLBACK for edge cases where SessionStart doesn't fire.
#
# Flow:
#   1. PreCompact writes checkpoint + marker
#   2. Claude compacts (lossy summarization)
#   3. SessionStart "compact" fires → THIS SCRIPT
#   4. Checkpoint re-injected into fresh context immediately
#   5. PreToolUse marker check becomes no-op (marker already consumed)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─── 1. Consume compaction marker atomically ───
# This prevents the PreToolUse fallback from double-injecting.

MARKER_CONSUMED="false"
if [ -f ".mnemos/just-compacted" ]; then
    python3 -c "
import json, time, os

marker = '.mnemos/just-compacted'
consumed = '.mnemos/just-compacted.consumed'

try:
    with open(marker) as f:
        data = json.load(f)
    age = time.time() - data.get('timestamp', 0)
    if age > 300:
        os.unlink(marker)
        print('stale')
    else:
        os.rename(marker, consumed)
        try:
            os.unlink(consumed)
        except:
            pass
        print('consumed')
except FileNotFoundError:
    print('already_consumed')
except Exception:
    print('error')
" > /tmp/mnemos-marker-state 2>/dev/null

    STATE=$(cat /tmp/mnemos-marker-state 2>/dev/null)
    rm -f /tmp/mnemos-marker-state
    if [ "$STATE" = "consumed" ]; then
        MARKER_CONSUMED="true"
    fi
fi

# ─── 2. Inject checkpoint (even without marker, checkpoint may exist) ───
# After compaction the context is nearly empty. Inject everything we have.

if [ ! -f ".mnemos/checkpoint-latest.json" ]; then
    if [ "$MARKER_CONSUMED" = "true" ]; then
        echo "=== MNEMOS: Compaction detected but no checkpoint found. ==="
        echo "Previous context was lost. Ask the user what they were working on."
    fi
    exit 0
fi

# ─── 3. Rich checkpoint injection via Python module ───

INJECT_OUTPUT=$(python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR%/templates}/scripts')

try:
    from mnemos.checkpoint import format_for_post_compact_injection
    output = format_for_post_compact_injection('.')
    if output:
        print(output)
    else:
        raise ValueError('empty')
except Exception:
    # Fallback: read checkpoint JSON directly
    import json
    try:
        with open('.mnemos/checkpoint-latest.json') as f:
            data = json.load(f)
        print('=== MNEMOS: CONTEXT RESTORED AFTER COMPACTION ===')
        print()
        print('## Goal')
        print(data.get('goal', 'No goal recorded'))
        print()
        constraints = data.get('active_constraints', [])
        if constraints:
            print('## Active Constraints (DO NOT VIOLATE)')
            for c in constraints:
                print('- ' + c)
            print()
        narrative = data.get('task_narrative', '')
        if narrative:
            print('## What You Were Working On')
            print(narrative)
            print()
        subgoal = data.get('current_subgoal', '')
        if subgoal:
            print('## Current Sub-Goal')
            print(subgoal)
            print()
        working = data.get('working_memory', '')
        if working:
            print('## Working Memory')
            print(working[:500])
            print()
        results = data.get('active_results', [])
        if results:
            print('## Completed Results')
            for r in results[:5]:
                print('- ' + r)
            print()
        git = data.get('git_state', {})
        if git.get('branch'):
            print('## Git State')
            print('Branch: ' + git['branch'])
            uncommitted = git.get('uncommitted', [])
            if uncommitted:
                print('Uncommitted: ' + ', '.join(uncommitted[:5]))
            print()
        files = data.get('recent_files', [])[:8]
        if files:
            print('## Recent Files')
            for entry in files:
                p = entry.get('path', '?')
                parts = []
                e = entry.get('edits', 0)
                r = entry.get('reads', 0)
                if e:
                    parts.append('edited ' + str(e) + 'x')
                if r:
                    parts.append('read ' + str(r) + 'x')
                print('- ' + p + (' (' + ', '.join(parts) + ')' if parts else ''))
            print()
        print('=== Resume work from this checkpoint. Do NOT re-derive what is stated above. ===')
    except:
        print('=== MNEMOS: Compaction detected but checkpoint unreadable. ===')
        print('Ask the user what they were working on.')
" 2>/dev/null)

if [ -n "$INJECT_OUTPUT" ]; then
    echo "$INJECT_OUTPUT"
fi

# ─── 4. Bridge iCPG state in background ───

if [ -f ".icpg/reason.db" ] && [ -f ".mnemos/mnemo.db" ]; then
    MNEMOS_CMD=""
    if command -v mnemos &>/dev/null; then
        MNEMOS_CMD="mnemos"
    elif PYTHONPATH="${SCRIPT_DIR%/templates}/scripts" python3 -m mnemos --version &>/dev/null 2>&1; then
        MNEMOS_CMD="PYTHONPATH=${SCRIPT_DIR%/templates}/scripts python3 -m mnemos"
    fi
    if [ -n "$MNEMOS_CMD" ]; then
        eval $MNEMOS_CMD bridge-icpg &>/dev/null &
    fi
fi

exit 0
