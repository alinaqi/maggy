#!/bin/bash
# Mnemos Post-Compaction Injection — FALLBACK Layer 2 of task restoration.
#
# NOTE: The PRIMARY re-injection point is now mnemos-compact-recovery.sh,
# which fires via SessionStart "compact" matcher BEFORE the agent acts.
# This script remains as a FALLBACK for edge cases where SessionStart
# doesn't fire (e.g., older Claude Code versions, interrupted compaction).
#
# This is a PreToolUse hook with NO matcher (fires on ALL tool calls).
# It detects when compaction just occurred and re-injects the full checkpoint.
#
# Fast path: ~5ms when no compaction happened (just a file existence check).
# Slow path: ~100ms when injecting checkpoint (only fires once after compaction).
#
# How it works:
#   1. PreCompact hook writes ".mnemos/just-compacted" marker
#   2. SessionStart "compact" consumes marker and injects checkpoint (primary)
#   3. If marker still exists (fallback), this hook injects on first tool call
#   4. Marker deletion is atomic (rename) to prevent parallel injection
#
# Install: add to .claude/settings.json under hooks.PreToolUse (no matcher)

# ─── Fast path: no compaction marker = exit immediately ───

[ -f ".mnemos/just-compacted" ] || exit 0

# ─── Validate marker is fresh and atomically consume it ───

CONSUMED=$(python3 -c "
import json, time, os

marker = '.mnemos/just-compacted'
consumed = '.mnemos/just-compacted.consumed'

try:
    with open(marker) as f:
        data = json.load(f)
    age = time.time() - data.get('timestamp', 0)
    if age > 300:
        # Stale marker (>5 min), just delete it
        os.unlink(marker)
        print('stale')
    else:
        # Fresh marker — atomically consume it
        os.rename(marker, consumed)
        try:
            os.unlink(consumed)
        except:
            pass
        print('consumed')
except FileNotFoundError:
    # Another hook already consumed it (parallel tool calls)
    print('already_consumed')
except Exception:
    print('error')
")

# Only inject if we successfully consumed the marker
if [ "$CONSUMED" != "consumed" ]; then
    exit 0
fi

# ─── Inject checkpoint into Claude's context ───

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

python3 -c "
import sys, json
sys.path.insert(0, '${SCRIPT_DIR%/templates}/scripts')

try:
    from mnemos.checkpoint import format_for_post_compact_injection
    output = format_for_post_compact_injection('.')
    if output:
        print(output)
    else:
        print('=== MNEMOS: Compaction detected but no checkpoint found. ===')
        print('Previous context was lost. Ask the user what they were working on.')
except Exception as e:
    # Fallback: try to read checkpoint JSON directly
    try:
        with open('.mnemos/checkpoint-latest.json') as f:
            data = json.load(f)
        print('=== MNEMOS: CONTEXT RESTORED AFTER COMPACTION ===')
        print()
        print('Compaction just occurred. Resume from this checkpoint:')
        print()
        print(f'## Goal')
        print(data.get('goal', 'No goal recorded'))
        print()
        constraints = data.get('active_constraints', [])
        if constraints:
            print('## Active Constraints (DO NOT VIOLATE)')
            for c in constraints:
                print(f'- {c}')
            print()
        narrative = data.get('task_narrative', '')
        if narrative:
            print(f'## What You Were Working On')
            print(narrative)
            print()
        print('=== Resume work from this checkpoint. ===')
    except:
        print('=== MNEMOS: Compaction detected but checkpoint unreadable. ===')
        print('Ask the user what they were working on.')
"

exit 0
