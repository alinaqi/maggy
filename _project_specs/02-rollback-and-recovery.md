# Spec 02: Rollback & Recovery

**Status:** pending
**Priority:** Tier 2
**Effort:** Medium

## Context

When `iCPG` detects drift or a runtime signal (Spec 01) indicates a shipped change broke something, the agent has no automated path to recover. It knows the problem exists but still has to manually coordinate a revert — find the right commit, check for downstream work, revert, re-verify.

For autonomous engineering this needs to be a first-class operation. The agent should be able to say "revert intent R-abc because its postcondition failed in production" and get a safe, auditable rollback.

## Goal

Add a `icpg revert` command that safely undoes all commits attributed to a given ReasonNode, handling downstream dependencies and leaving a verifiable audit trail.

## Approach

### Step 1 — Track commit SHAs on intents

iCPG already has `CREATES` / `MODIFIES` edges between ReasonNodes and Symbols. Extend the `record` command to also store the commit SHA that made the change:

```
CREATES      Reason → Symbol    [commit_sha, timestamp]
MODIFIES     Reason → Symbol    [commit_sha, timestamp]
```

### Step 2 — `icpg revert <intent-id>`

The command:

1. Collects all commit SHAs attributed to this intent (from its edges)
2. Checks for downstream `REQUIRES` intents whose postconditions depend on this one
3. If downstream intents exist and aren't in `drifted`/`abandoned` status → refuse revert, explain the chain
4. Otherwise: `git revert --no-commit <sha1> <sha2> ...` in reverse chronological order
5. Runs the intent's `VALIDATED_BY` tests to confirm pre-intent state is reached
6. Updates the intent status to `reverted` (new status)
7. Emits a `REVERTED` edge type linking the revert commit to the original

### Step 3 — Auto-revert on severe drift (opt-in)

Wire into drift detection: when `Runtime drift` severity > 0.9 AND drift age < 1h AND `auto_revert: true` is set on the intent → trigger `icpg revert` automatically and page a human (Spec 07).

Config per-project in `.icpg/config.yaml`:

```yaml
auto_revert:
  enabled: false        # opt-in per project
  severity_threshold: 0.9
  max_age_minutes: 60
  require_test_pass: true
```

### Step 4 — Recovery for partial failures

If `git revert` fails mid-way (conflicts, missing commits), leave the tree in a clean state (`git revert --abort`) and report exactly which commit failed + why.

## Integration points

- `scripts/icpg/__main__.py` — add `revert` subcommand
- `scripts/icpg/models.py` — add `commit_sha` field on edges, `reverted` status, `REVERTED` edge type
- `scripts/icpg/drift.py` — optional auto-revert trigger for severe runtime drift
- `hooks/post-commit-graph` — capture SHA when recording
- `skills/icpg/SKILL.md` — add revert section

## Success criteria

1. `icpg revert <id>` reverts all commits attributed to that intent cleanly or explains why it can't
2. Downstream `REQUIRES` intents block the revert with a clear message
3. Auto-revert is opt-in per-intent and only fires on high-severity runtime drift
4. Every revert is logged in the graph with `REVERTED` edges pointing to the original commits
5. A test harness verifies revert correctness against a scripted intent lifecycle

## Depends on

- Spec 01 (runtime observability) — the auto-revert signal comes from runtime drift
