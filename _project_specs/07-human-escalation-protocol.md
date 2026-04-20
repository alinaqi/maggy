# Spec 07: Human-in-the-Loop Escalation Protocol

**Status:** pending
**Priority:** Tier 1 (highest leverage)
**Effort:** Small-Medium

## Context

When an autonomous agent hits a wall it can't resolve — drift it can't fix, a contract violation with no clear cause, lock negotiation failure, budget exceeded — there's no formal protocol for raising the problem to a human. The hooks infrastructure exists, the discipline doesn't.

Today the agent might:
- Silently continue and compound the issue
- Write a confused summary and exit, leaving no actionable packet
- Page every minor issue, creating alert fatigue

None of these scale to autonomous engineering at a team level.

## Goal

A standard escalation protocol: the agent packages a context packet (what it tried, what went wrong, what it needs a human to decide) and delivers it through a configured channel.

## Approach

### Step 1 — Escalation packet schema

```yaml
escalation:
  id: "esc-abc123"
  agent: "claude-opus-4.7"
  intent: "R-auth-refactor"
  severity: "blocking"           # blocking | high | medium | low
  category: "drift_unresolvable" # or: contract_violation, lock_conflict,
                                 # budget_exceeded, taint_detected, unknown
  summary: "Two-sentence description of the situation"
  what_was_tried:
    - "Attempted X — result: failed because Y"
    - "Attempted Z — result: partial"
  proposed_options:
    - "Option A: revert to sha abc, human makes a decision"
    - "Option B: accept the drift, update postcondition"
  context_refs:
    - "commit: sha-latest"
    - "intent: R-auth-refactor"
    - "drift_report: path/to/drift.json"
    - "mnemos_checkpoint: path/to/checkpoint.json"
  awaiting: "resolution"
```

### Step 2 — `icpg escalate` CLI

```bash
icpg escalate --intent R-auth-refactor \
              --category drift_unresolvable \
              --severity blocking \
              --summary "Cannot resolve postcondition drift" \
              --context drift.json
```

Writes the packet to `.icpg/escalations/<id>.yaml` and fires the configured delivery channel.

### Step 3 — Pluggable delivery channels

One adapter per channel (`scripts/icpg/escalation/`):

- `slack_adapter.py` — post to configured channel with packet fields
- `github_issue_adapter.py` — create issue with the packet
- `email_adapter.py` — SendGrid / SMTP
- `file_adapter.py` — default; writes to `.icpg/escalations/` only (for local/dev)

Config in `.icpg/config.yaml`:

```yaml
escalation:
  channels:
    - type: slack
      webhook_url_env: SLACK_ESCALATION_WEBHOOK
      min_severity: high
    - type: github_issue
      repo: "org/repo"
      min_severity: blocking
```

### Step 4 — Auto-trigger from known conditions

Wire automatic escalations:

| Condition | Severity | Category |
|---|---|---|
| Drift severity >0.8, auto-revert failed | blocking | drift_unresolvable |
| Contract violation caught by generated test (Spec 03) | high | contract_violation |
| Lock negotiation timeout (Spec 04) | medium | lock_conflict |
| Budget exceeded without handoff checkpoint (Spec 06) | high | budget_exceeded |
| CodeQL finds new taint path | blocking | taint_detected |

Each hook module calls `icpg escalate` with the right packet when its trigger fires.

### Step 5 — Resolution tracking

When a human responds (comment on the GitHub issue, Slack thread reply with a resolution marker like `resolved: revert`), an `EscalationResolution` node is written and any pending agent waiting on the packet can resume.

Agents consult `icpg escalations list --pending` as part of their pre-task queries.

### Step 6 — Rate limiting / dedup

Don't spam. If the same intent + category has an open escalation, merge into it (append to `what_was_tried`) instead of creating a new one. Escalation adapter respects a per-channel rate limit.

## Integration points

- `scripts/icpg/models.py` — `Escalation`, `EscalationResolution`
- `scripts/icpg/escalation/` — new package, one module per channel
- `scripts/icpg/__main__.py` — `escalate`, `escalations list/resolve` subcommands
- `hooks/post-tool-use` — auto-escalate on trigger conditions
- `skills/icpg/SKILL.md` — document when agents should manually call it
- `templates/escalation-config.yaml` — example config

## Success criteria

1. Agent can manually escalate a situation with `icpg escalate` and humans receive it through at least one channel (Slack preferred)
2. Auto-escalations fire for all 5 trigger conditions above
3. Dedup works — same intent + category doesn't spam
4. Human resolution flows back as `EscalationResolution` node, pending agents can detect it
5. Local/dev config uses file-only adapter (no external calls), never breaks tests

## Depends on

None directly — builds on existing hook infrastructure. Integrates with:
- Spec 02 (rollback) — failed auto-revert triggers escalation
- Spec 03 (contracts) — test failures trigger escalation
- Spec 04 (locks) — negotiation timeout triggers escalation
- Spec 06 (budget) — overrun without handoff triggers escalation
