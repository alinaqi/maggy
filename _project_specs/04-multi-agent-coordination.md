# Spec 04: Multi-Agent Coordination (Symbol-Level Locks)

**Status:** pending
**Priority:** Tier 2
**Effort:** Medium

## Context

claude-bootstrap already has `agent-teams` and `team-coordination` skills, and Maggy ships with a P2P session-handoff pattern. But when two agents (or two sessions of the same agent) want to modify the same area of code, there's no coordination protocol. First-to-commit wins, which creates silent merge conflicts, duplicated work, and lost intent tracking.

For autonomous engineering at team scale (multiple agents, or one agent coordinating long-running subtasks), we need intent-level and symbol-level locks.

## Goal

Agents claim exclusive work on an intent or set of symbols before modifying, negotiate with holders of conflicting locks, and release on completion or timeout.

## Approach

### Step 1 — Lock primitive in iCPG

Add a `lock` table and edge type:

```
LOCKED_BY    Reason | Symbol → Agent    [acquired_at, expires_at, purpose]
```

Locks are scoped to an intent (broadest), a set of files, or a set of symbols (finest). A lock has:

- `holder_id` — agent or session identifier
- `scope` — intent id | files[] | symbols[]
- `purpose` — one-line description ("refactor auth service")
- `acquired_at` / `expires_at` — auto-expire to prevent orphans (default 30 min)
- `heartbeat_at` — renewed periodically by the holder

### Step 2 — `icpg lock` / `icpg unlock` commands

```bash
icpg lock intent R-abc --purpose "refactor auth" --expires 30m
icpg lock symbols auth.login,auth.logout --purpose "rate-limiting fix"
icpg locks list                              # show all active locks
icpg unlock R-abc                             # release
icpg locks prune                              # remove expired
```

Lock attempts on a held scope return the holder's info so the requesting agent can decide what to do (wait, negotiate, defer).

### Step 3 — Pre-task query integration

Extend the 3 canonical pre-task queries with a 4th:

| Query | What It Answers |
|---|---|
| `icpg query locks <scope>` | Is someone else working on this right now? |

The PreToolUse hook adds this to the injected context before any Edit/Write call.

### Step 4 — Negotiation protocol

When an agent wants a held lock, it sends a `negotiation_request` to the holder (Mnemos message):

- Requester states: intent, priority, estimated duration
- Holder responds: `accept` (release), `defer` (hold until completion), `split` (narrow the lock to specific symbols)

If no response within 5 minutes, the requester either takes the lock (if the holder's heartbeat is stale) or escalates (Spec 07).

### Step 5 — Conflict prevention at commit time

Post-commit hook verifies the committing agent holds the right lock for all symbols the commit modified. If not, the commit is logged as `unauthorized_modification` and the drift check flags it.

## Integration points

- `scripts/icpg/models.py` — `Lock`, `LockedByEdge`
- `scripts/icpg/store.py` — `acquire_lock`, `release_lock`, `prune_locks`, `list_locks`
- `scripts/icpg/__main__.py` — `lock`, `unlock`, `locks` subcommands
- `hooks/pre-tool-use` — inject active-lock context
- `hooks/post-commit-graph` — verify lock matches modified symbols
- `skills/agent-teams/SKILL.md` — add locking discipline section
- `skills/icpg/SKILL.md` — document the 4th pre-task query

## Success criteria

1. Two concurrent agents attempting to modify the same symbol can't both succeed — the second sees the held lock
2. Locks auto-expire 30 min after last heartbeat (agents don't have to remember to release)
3. Pre-task queries include active-lock info
4. Commits violating lock ownership are flagged in drift reports
5. Negotiation protocol works: requester gets a structured response from holder, or escalation fires

## Depends on

- Spec 07 (escalation) — when negotiation fails, escalation fires
- Builds on existing `agent-teams` and Maggy P2P patterns
