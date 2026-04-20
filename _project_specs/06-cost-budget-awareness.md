# Spec 06: Cost / Budget Awareness

**Status:** pending
**Priority:** Tier 3 (frontier)
**Effort:** Small

## Context

Autonomous agents stuck in loops burn real money. Mnemos's fatigue detection (4-dim: tokens, scatter, re-reads, error density) is a *behavioral* proxy for "the agent is struggling" but it isn't a hard stop. An agent that's actually wasting tokens or API calls needs a budget ceiling.

This matters especially for:

- `/improve-maggy`, self-improvement flows, anything that spawns subagents
- Team runs where one misbehaving agent shouldn't bankrupt the whole run
- Maggy's TDD execute pipeline (up to 3 Claude Code invocations per ticket)

## Goal

Add per-task and per-session budget limits with hard stops and a budget-aware fatigue state.

## Approach

### Step 1 — Declare a budget in intent config

Extend ReasonNode:

```yaml
budget:
  tokens: 100000
  api_calls: 50
  wall_clock_minutes: 30
  usd: 5.00
```

All fields optional. `usd` calculated from model pricing tables (current Sonnet/Opus rates, refreshed quarterly).

### Step 2 — Track spend via hooks

PostToolUse hook accumulates:

- Tokens consumed (from `transcript_path` JSON blobs)
- Claude API calls (by counting tool uses)
- Wall clock elapsed since intent started

Stored in `.icpg/budgets/<intent-id>.json` with heartbeats.

### Step 3 — Budget-aware fatigue state

Add a 5th Mnemos fatigue dimension: `budget_burn_rate`. If the agent has consumed 70% of its token budget at 40% progress, that's a signal to compress / consolidate / consider abandoning. Threshold behavior:

| Budget consumed | Action |
|---|---|
| <60% | Normal |
| 60-85% | Mnemos COMPRESS state forced |
| 85-100% | Mnemos REM state forced, agent warned to wrap up |
| >100% | Hard stop — PreToolUse hook rejects further Edit/Write/Bash |

### Step 4 — Graceful stop behavior

When budget is exceeded:

1. PreToolUse hook returns `budget_exceeded` error with context about remaining work
2. Agent is expected to write a handoff Mnemos checkpoint before exiting
3. Intent status flips to `deferred_budget`
4. Human (or another agent with a fresh budget) can resume from the checkpoint

### Step 5 — Budget override

A human can set `allow_overage: true` on an intent or raise the limit mid-run. Override requires a commit to the intent's config (auditable).

## Integration points

- `scripts/icpg/models.py` — `Budget` field on ReasonNode
- `scripts/icpg/budget.py` — new module for tracking and enforcement
- `hooks/pre-tool-use` — budget check before Edit/Write/Bash
- `hooks/post-tool-use` — accumulate spend
- `templates/pricing.yaml` — model → $/token table, refreshed quarterly
- `skills/mnemos/SKILL.md` — document the 5th fatigue dimension
- `skills/icpg/SKILL.md` — document budget declaration

## Success criteria

1. An intent with a 10k-token budget hard-stops at 10k tokens via PreToolUse rejection
2. Mnemos fatigue state reflects budget consumption (COMPRESS / REM / EMERGENCY)
3. Budget overruns leave a Mnemos handoff checkpoint so work can resume
4. `icpg budgets list` shows current spend vs limit per active intent
5. No budget declared → no enforcement (backward compatible)

## Depends on

- Mnemos fatigue model (already exists)
- Nothing else
