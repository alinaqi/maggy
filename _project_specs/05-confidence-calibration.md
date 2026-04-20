# Spec 05: Confidence Calibration (Reinforcement Loop)

**Status:** pending
**Priority:** Tier 3 (frontier)
**Effort:** Medium

## Context

iCPG's `get_risk_profile` query today classifies symbols as fragile/stable based on ownership history and drift count. It doesn't learn from what actually failed when agents touched it. An agent that tried refactoring this file three times and failed gets the same risk score as one that hasn't been tried yet.

For autonomous engineering, we want a reinforcement loop: past agent failures against a symbol or pattern should raise its risk score for future agents.

## Goal

Track agent actions and their outcomes against symbols/patterns, and use that history to calibrate confidence for future pre-task queries.

## Approach

### Step 1 — Action-outcome tracking

Add two new node types to iCPG:

```
AgentAction   { id, agent, intent, scope[], timestamp }
Outcome       { action_id, result, evidence }
```

Result types:
- `success` — tests passed, intent fulfilled, no drift
- `partial` — intent fulfilled but introduced drift elsewhere
- `failure_test` — tests failed, rolled back
- `failure_runtime` — shipped, runtime drift detected (Spec 01)
- `abandoned` — agent gave up

Evidence is a pointer — commit SHA, test output, drift report.

### Step 2 — Hook into existing flows

Automatic capture:

- Pre-task query writes an open `AgentAction` node
- Post-commit: matches to the most recent pending action and records outcome based on test results
- Drift check: if a `VALIDATED_BY` test fails on an intent, the agent action tied to that intent's commit is marked `failure_test`
- Spec 01 runtime drift: marks `failure_runtime`
- Spec 02 auto-revert: marks `abandoned`

### Step 3 — Risk score now includes success rate

`icpg query risk <symbol>` returns a calibrated score:

```
Historical success rate for this symbol: 40% (2 of 5 attempts successful)
Pattern complexity: high (10+ dependents, 3 owners, drifted twice)
Recommendation: treat as fragile — consider smaller changes or pair
```

Calibration uses a simple Bayesian update: prior = structural risk (current method), likelihood = recent action outcomes.

### Step 4 — Pattern-level learning (stretch)

For autonomous agents, single-symbol history is too narrow — we want "refactors of dataclasses with >5 fields fail 60% of the time." This requires clustering actions by pattern, not just symbol. Defer this to a v2 of this spec; first ship the single-symbol version.

### Step 5 — Privacy & data hygiene

Action history is sensitive (could leak intent details). Make it:

- Opt-out per project (`.icpg/config.yaml: track_outcomes: false`)
- Redact content, keep structure only (symbol ids, outcome types, timestamps)
- Never exported outside the `.icpg/` directory

## Integration points

- `scripts/icpg/models.py` — `AgentAction`, `Outcome` node types
- `scripts/icpg/store.py` — outcome-tracking tables
- `scripts/icpg/drift.py` — risk scoring gains history term
- `hooks/pre-tool-use` — record `AgentAction` before Edit/Write calls
- `hooks/post-commit-graph` — finalize the outcome
- `skills/icpg/SKILL.md` — document calibrated risk semantics

## Success criteria

1. Every agent Edit/Write action is automatically logged (no manual reporting)
2. `icpg query risk <symbol>` returns a score incorporating historical outcomes
3. Risk score converges toward structural risk when action history is empty (no regression)
4. Privacy opt-out works — no history written when disabled
5. A test harness replays an action sequence and verifies calibrated scores update correctly

## Depends on

- Spec 01 (runtime observability) — feeds `failure_runtime` signal
- Spec 02 (rollback) — feeds `abandoned` signal
- Spec 03 (verifiable contracts) — feeds high-signal `failure_test` from postcondition failures
