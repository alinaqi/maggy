# Mnemos Implementation Addendum

Implementation details for the Mnemos RFC (Task-Scoped Memory Lifecycle for Autonomous Agents) as deployed in Maggy.

## 1. Signal Access in Claude Code

### Token Utilization (Primary Fatigue Signal)

Claude Code exposes context window metrics through **statusline scripts**. When configured, the statusline script receives JSON on stdin for every API call:

```json
{
  "context_window": {
    "used_percentage": 42.5,
    "remaining_percentage": 57.5,
    "used_tokens": 85000,
    "total_tokens": 200000,
    "remaining_tokens": 115000
  }
}
```

**Key discovery**: Hooks (PreToolUse, PreCompact, etc.) do NOT receive context data directly. The solution is a two-stage pipeline:

1. **Statusline script** receives token data on every API call, writes to `.mnemos/fatigue.json`
2. **Hooks** read `.mnemos/fatigue.json` from disk when they fire

This gives near-real-time fatigue monitoring without requiring direct hook access to context metrics.

### Hook System Integration

| Hook | Trigger | Mnemos Action |
|------|---------|--------------|
| Statusline | Every API call | Write `fatigue.json` with token metrics |
| PreToolUse (Edit/Write) | Before file edits | Read fatigue, auto-checkpoint at 0.60+, auto-consolidate at 0.40+ |
| PreCompact | Before compaction | Emergency checkpoint, typed preservation instructions |
| SessionStart | Session begins | Load checkpoint, bridge iCPG state |
| Stop | Agent stops | Write final checkpoint |

## 2. MnemoGraph Architecture

### Node Types and Eviction Policies

| Type | Eviction Policy | Purpose |
|------|----------------|---------|
| GoalNode | NEVER | Task's primary objective |
| ConstraintNode | NEVER | Invariants, contracts, must-not-violate rules |
| ContextNode | EVICTABLE | File contents, tool outputs, ephemeral context |
| WorkingNode | COMPRESS_FIRST | In-progress reasoning, current approach |
| ResultNode | COMPRESS_FIRST | Completed sub-task results |
| SkillNode | COMPRESS_FIRST | Learned patterns (Tier 1+: promotable to persistent) |
| CheckpointNode | NEVER | Serialized session state |
| HandoffNode | NEVER | Task completion summary for successor |

### Activation Weight Decay

All evictable/compressible nodes undergo exponential decay:
- Factor: 0.95 per consolidation pass
- GoalNodes, ConstraintNodes, CheckpointNodes, HandoffNodes exempt
- Touching a node (access) resets weight via `touch_node()`

### Storage

SQLite at `.mnemos/mnemo.db`:
- `mnemo_nodes` — MnemoGraph nodes with type, weight, status, scope_tags
- `checkpoints` — Serialized session state
- `fatigue_log` — Historical fatigue measurements for trending

## 3. Fatigue Model (4 Dimensions — All Passively Observable)

All 4 dimensions are derived from actual hook data. No agent cooperation needed.

### Signal Collection

Hooks log behavioral signals to `.mnemos/signals.jsonl` (append-only JSONL):
- **PreToolUse** logs: `{tool, event: "pre", file_path, ts}` — captures what files the agent touches
- **PostToolUse** logs: `{tool, event: "post", file_path, success, ts}` — captures tool outcomes
- **Statusline** writes: `.mnemos/fatigue.json` with token metrics — captures context window state

Fatigue computation reads the last 30 entries from `signals.jsonl` + `fatigue.json`.

### Dimension Weights

```
composite = 0.40 * token_utilization
          + 0.25 * scope_scatter
          + 0.20 * reread_ratio
          + 0.15 * error_density
```

### Dimension Details

**Token Utilization (0.40)**: `context_window.used_percentage / 100`. Direct from statusline. Most reliable signal — measures how full the context window is.

**Scope Scatter (0.25)**: Ratio of unique directories touched in the last 30 tool calls. Agent editing `src/auth/` exclusively = 0.0 (focused). Agent bouncing across `src/auth/`, `tests/`, `docs/`, `config/`, `lib/` = 0.7+ (scattered, unfocused). Derived from PreToolUse `tool_input.file_path`.

**Re-read Ratio (0.20)**: Proportion of Read tool calls that target files already read in the session. Agent reading `middleware.ts` once then moving on = 0.0 (remembers what it read). Agent re-reading `middleware.ts` 5 times = 0.8 (lost context, needs to re-read). Derived from PreToolUse when `tool_name=Read`. This is the strongest signal of actual context degradation.

**Error Density (0.15)**: Ratio of failed tool calls to total tool calls in the rolling window. Agent with 100% success = 0.0 (productive). Agent with 50% failures = 0.5 (struggling, confused). Derived from PostToolUse `tool_response` error detection.

### State Thresholds

| State | Score Range | Auto-Actions |
|-------|------------|-------------|
| FLOW | 0.00–0.40 | None |
| COMPRESS | 0.40–0.60 | Micro-consolidation (compress 3 ResultNodes, evict 1 cold ContextNode, decay weights) |
| PRE-SLEEP | 0.60–0.75 | Checkpoint written + consolidation |
| REM | 0.75–0.90 | Emergency checkpoint, warning to agent |
| EMERGENCY | 0.90+ | Emergency checkpoint, handoff instruction |

## 4. Checkpoint/Resume Protocol

### CheckpointNode Contents

```json
{
  "id": "uuid",
  "task_id": "session-1",
  "goal": "Implement authentication module",
  "active_constraints": [
    "INV: API backward compatibility",
    "POST: All endpoints require auth token"
  ],
  "active_results": [
    "JWT middleware implemented and tested",
    "User model created with email/password"
  ],
  "current_subgoal": "Add password reset flow",
  "working_memory": "Considering email vs SMS for reset codes...",
  "fatigue_at_checkpoint": 0.62,
  "git_state": {
    "branch": "feat/auth",
    "uncommitted": ["src/auth/middleware.ts", "src/auth/routes.ts"]
  },
  "icpg_state": {
    "active_reason": "abc12345 -- Implement user authentication",
    "unresolved_drift": 2,
    "stats": {"reasons": 5, "symbols": 42, "edges": 48}
  },
  "node_summary": {
    "total": 15, "active": 10, "compressed": 3,
    "by_type": {"goal": 1, "constraint": 3, "result": 4, "working": 2}
  }
}
```

### Resume Format

SessionStart hook loads `checkpoint-latest.json` and formats as structured markdown:

```markdown
## Mnemos Session Resume
Checkpoint: abc12345
Fatigue at checkpoint: 0.62

### Goal
Implement authentication module

### Active Constraints (DO NOT VIOLATE)
- INV: API backward compatibility
- POST: All endpoints require auth token

### Current Sub-Goal
Add password reset flow

### Progress So Far
- JWT middleware implemented and tested
- User model created with email/password

### Git State
Branch: feat/auth
Uncommitted files:
  - src/auth/middleware.ts
  - src/auth/routes.ts
```

## 5. iCPG Bridge

Mnemos imports iCPG state via `mnemos bridge-icpg`:

| iCPG Entity | Mnemos Node | Notes |
|-------------|-------------|-------|
| ReasonNode (active) | GoalNode | Content includes iCPG ID reference |
| ReasonNode.invariants | ConstraintNode | Linked to GoalNode |
| ReasonNode.postconditions | ConstraintNode | Linked to GoalNode |
| Unresolved drift count | CheckpointNode.icpg_state | Summary only |
| Graph stats | CheckpointNode.icpg_state | Reasons/symbols/edges counts |

Bridge runs automatically on SessionStart (background) and on-demand via CLI.

## 6. Micro-Consolidation (Tier 0)

Rule-based, no LLM, <100ms target:

1. **Compress**: Take 3 oldest active ResultNodes, set status=COMPRESSED, store first 200 chars as summary, clear content
2. **Evict**: Take 1 cold ContextNode (weight < 0.2, access_count < 3, no scope overlap), set status=EVICTED
3. **Decay**: Apply 0.95 exponential decay to all evictable node weights

Triggered automatically by PreToolUse hook when fatigue >= 0.40.

## 7. Deployment

### Files

```
scripts/mnemos/
  __init__.py          # Package init
  models.py            # MnemoNode, FatigueState, CheckpointNode
  store.py             # SQLite storage (MnemosStore)
  fatigue.py           # 4-dimension fatigue from observable signals
  signals.py           # Behavioral signal collection from hooks
  checkpoint.py        # Checkpoint write/load
  consolidation.py     # Micro-consolidation
  __main__.py          # CLI (mnemos command)

templates/
  mnemos-statusline.sh      # Statusline: writes fatigue.json (token metrics)
  mnemos-pre-edit.sh        # PreToolUse: logs file signal + fatigue check + iCPG
  mnemos-post-tool.sh       # PostToolUse: logs success/failure for error density
  mnemos-session-start.sh   # SessionStart: checkpoint resume
  mnemos-pre-compact.sh     # PreCompact: emergency checkpoint + typed preservation
  mnemos-stop-checkpoint.sh # Stop: final checkpoint

skills/mnemos/SKILL.md      # Skill documentation
commands/mnemos-status.md   # /mnemos-status slash command
commands/mnemos-checkpoint.md # /mnemos-checkpoint slash command
```

### Configuration (settings.json)

Hooks are configured in `.claude/settings.json`. The Mnemos hooks replace the standalone iCPG hooks (mnemos-pre-edit.sh includes iCPG context queries).

### Dependencies

Zero external dependencies. Uses only Python stdlib (sqlite3, json, pathlib, subprocess, dataclasses).

## 8. Future Work (Tier 1+)

Not implemented in this release:
- **Mini-REM consolidation**: LLM-based summarization of WorkingNodes during high fatigue
- **Full REM consolidation**: Cross-task pattern extraction, SkillNode promotion algebra
- **Multi-agent orchestrator protocol**: Checkpoint exchange between agent instances
- **SkillNode promotion**: Automatic promotion of repeated patterns to persistent storage
- **Fatigue prediction**: Use fatigue_log history to predict when checkpoints will be needed
