---
name: mnemos
description: Task-scoped memory lifecycle — typed MnemoGraph prevents lossy context compaction by treating facts/decisions/code-refs/handoffs as distinct node types with per-type eviction policies
when-to-use: "When you need durable working memory across compactions — checkpoint decisions, preserve task handoffs, or audit what was remembered"
user-invocable: false
effort: high
---

# Mnemos — Task-Scoped Memory Lifecycle

## What It Does

Mnemos prevents lossy context compaction from destroying the structured knowledge you need most. It treats your working memory as a **typed graph** (MnemoGraph) where different types of knowledge have different eviction policies:

- **GoalNodes** and **ConstraintNodes** are NEVER evicted — they survive all compaction
- **ResultNodes** are compressed (summary kept) before eviction
- **ContextNodes** are evictable when their activation weight drops
- **CheckpointNodes** persist to disk for session resume

## Fatigue Model

Mnemos monitors 4 dimensions of "agent fatigue" — all passively observed from hook data, no manual input needed:

| Dimension | Weight | Signal Source | What It Measures |
|-----------|--------|--------------|-----------------|
| Token utilization | 0.40 | Statusline JSON | How full the context window is |
| Scope scatter | 0.25 | PreToolUse file paths | How many directories the agent is bouncing between |
| Re-read ratio | 0.20 | PreToolUse Read calls | How often the agent re-reads files it already read (context loss) |
| Error density | 0.15 | PostToolUse outcomes | What fraction of tool calls are failing (agent struggling) |

Fatigue states and actions:

| State | Score | Action |
|-------|-------|--------|
| FLOW | 0.0–0.4 | Normal operation |
| COMPRESS | 0.4–0.6 | Micro-consolidation runs (compress 3 ResultNodes, evict 1 cold ContextNode) |
| PRE-SLEEP | 0.6–0.75 | Checkpoint written, consolidation runs |
| REM | 0.75–0.9 | Emergency checkpoint, consider wrapping up |
| EMERGENCY | 0.9+ | Checkpoint written, hand off immediately |

## How To Use

### Automatic (hooks handle everything):
1. **Statusline** writes `fatigue.json` on every API call
2. **PreToolUse** hook reads fatigue before every edit, auto-checkpoints at 0.60+
3. **PreCompact** hook writes emergency checkpoint, compaction marker, and tells summarizer what to preserve
4. **Post-Compaction Injection** (PreToolUse, no matcher) detects the compaction marker on the first tool call after compaction and re-injects the full checkpoint into context
5. **SessionStart** hook loads last checkpoint on new session resume

### Post-Compaction Recovery (Two-Layer Defense):
When Claude Code compacts the context (~83% full), Mnemos uses two layers:
- **Layer 1**: PreCompact outputs strong preservation instructions with inline checkpoint content for the summarizer
- **Layer 2**: After compaction, the first tool call triggers `mnemos-post-compact-inject.sh` which detects the `.mnemos/just-compacted` marker and re-injects the full checkpoint. This is the guaranteed path — it doesn't depend on the summarizer.

The result: after compaction, you'll see a "CONTEXT RESTORED AFTER COMPACTION" block with your goal, constraints, what you were working on, and progress. Resume from there.

### Manual CLI:
```bash
mnemos init                    # Initialize .mnemos/
mnemos status                  # Show node counts + fatigue
mnemos fatigue                 # Detailed fatigue breakdown
mnemos checkpoint --force      # Write checkpoint now
mnemos resume                  # Output checkpoint for context
mnemos consolidate             # Run micro-consolidation
mnemos nodes --type goal       # List active GoalNodes
mnemos add goal "Build auth"   # Add a GoalNode
mnemos bridge-icpg             # Import iCPG ReasonNodes
```

## Agent Instructions

When working on a task:

1. **Create a GoalNode** at the start: `mnemos add goal "what you're trying to achieve" --task-id session-1`
2. **Add ConstraintNodes** for invariants: `mnemos add constraint "API backward compatibility" --scope src/api/`
3. **Check fatigue** before long operations: `mnemos fatigue`
4. **Checkpoint at sub-goal boundaries**: `mnemos checkpoint`
5. **On session resume**: the SessionStart hook automatically loads your checkpoint

## iCPG Integration

Mnemos bridges with iCPG (Intent-Augmented Code Property Graph):
- `mnemos bridge-icpg` imports active ReasonNodes as GoalNodes
- Postconditions/invariants become ConstraintNodes
- Checkpoint includes iCPG state (active intent, unresolved drift)

## Storage

Everything lives in `.mnemos/` (gitignored):
- `mnemo.db` — SQLite MnemoGraph
- `fatigue.json` — Live token metrics (updated per API call by statusline)
- `signals.jsonl` — Behavioral signal log (appended by PreToolUse + PostToolUse hooks)
- `checkpoint-latest.json` — Most recent checkpoint
- `checkpoints/` — Archived checkpoints
