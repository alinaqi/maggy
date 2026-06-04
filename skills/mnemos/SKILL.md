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
4. **SessionStart "compact"** fires immediately after compaction, re-injects full checkpoint (primary restore)
5. **SessionStart "startup|resume"** loads last checkpoint on new/resumed sessions
6. **PreToolUse fallback** (no matcher) detects compaction marker if SessionStart didn't fire
7. **Stop** hook writes final checkpoint for next session

### Post-Compaction Recovery (Three-Layer Defense):
When Claude Code compacts the context (~83% full), Mnemos uses three layers:
- **Layer 1 (PreCompact)**: Outputs strong preservation instructions with inline checkpoint content for the summarizer. Writes `.mnemos/just-compacted` marker.
- **Layer 2 (SessionStart "compact")**: **PRIMARY re-injection.** Fires immediately when Claude resumes after compaction — before any agent action. Consumes the marker and injects the full checkpoint into the fresh context. This is the recommended approach per the RFC (Wake State Reconstruction).
- **Layer 3 (PreToolUse fallback)**: If SessionStart doesn't fire (older versions, edge cases), the first tool call triggers `mnemos-post-compact-inject.sh` which detects the marker and injects. Safety net only.

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
mnemos ingest-claude --all     # Ingest Claude Code transcripts (see below)
mnemos haze --recent 10        # Show per-session haziness scores
```

## Claude Transcript Ingestion & Haziness

Mnemos can ingest Claude Code session transcripts (the per-session JSONL under
`~/.claude/projects/`) and score each session's **haziness** — a measure of how
much the agent struggled. The `Stop` hook does this automatically on session
exit; it is also available manually.

**What's stored:** only structural fields (roles, tool names, file paths, error
flags, timestamps) plus a **redacted, 200-char preview** of each turn. Full
content is never persisted, and secrets (API keys, tokens, PEM blocks, JWTs,
credentials) are redacted before anything touches disk.

**Haziness** is a weighted score over five dimensions, each in `[0,1]`:

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| correction_density | 0.30 | User corrections per eligible user turn |
| redo_ratio | 0.25 | Edits re-touched after an error |
| first_try_error_rate | 0.20 | Edits followed by errors within 3 turns |
| orphan_tool_use_rate | 0.15 | Tool calls with no matching result |
| backtrack_norm | 0.10 | `git revert`/`reset --hard`/`restore` calls |

The composite maps to a band: `clear` < 0.25 ≤ `cloudy` < 0.50 ≤ `hazy` < 0.75 ≤ `lost`.

```bash
mnemos ingest-claude --all              # ingest every transcript + score
mnemos ingest-claude --session <id>     # one session by id
mnemos ingest-claude --transcript <f>   # a specific JSONL file
mnemos haze --recent 10                 # table of recent sessions
mnemos haze --session <id>              # per-dimension breakdown
```

Ingestion is idempotent (resumes via `last_line_offset`). **Opt out per project**
with `touch .mnemos/claude-log.disabled`.

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
