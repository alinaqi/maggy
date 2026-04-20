# Autonomous Engineering Roadmap

A set of specs closing the gaps between claude-bootstrap's current code-intelligence stack (`codebase-memory-mcp` + `iCPG` + `Joern/CodeQL` + `Mnemos` + `code-deduplication`) and what an autonomous coding agent actually needs to ship changes without supervision.

## Why these?

Autonomous agents fail in 10 specific, repeatable ways (see [comparison doc in chat history — 2026-04-20](#)). Our current stack addresses 9 of them. The specs below close the remaining agent-observable gaps and add the two "frontier" capabilities (multimodal ingestion, verifiable contracts).

## Priority order

**Tier 1 — highest leverage, unlocks the rest:**

| # | Spec | Why it matters |
|---|---|---|
| 01 | [Runtime observability](01-runtime-observability.md) | Drift detection is static — an agent that ships code needs a production feedback signal to know if the change actually worked |
| 03 | [Verifiable contracts](03-verifiable-contracts.md) | iCPG postconditions are currently natural-language. Generating property-based tests from them makes them machine-checkable. |
| 07 | [Human escalation protocol](07-human-escalation-protocol.md) | When the agent is stuck, it needs a formal "page a human with this packet" channel |

**Tier 2 — valuable, not blocking:**

| # | Spec | Why it matters |
|---|---|---|
| 08 | [Auto CODE_INDEX](08-auto-code-index.md) | The capability index currently depends on humans maintaining it. Auto-derive from the graph. |
| 04 | [Multi-agent coordination](04-multi-agent-coordination.md) | When two agents touch the same area, we need locking / negotiation |
| 02 | [Rollback & recovery](02-rollback-and-recovery.md) | Drift flags a problem; we still need automated revert paths |

**Tier 3 — frontier / optional:**

| # | Spec | Why it matters |
|---|---|---|
| 05 | [Confidence calibration](05-confidence-calibration.md) | Reinforcement loop — learn from past agent actions which patterns fail |
| 06 | [Cost / budget awareness](06-cost-budget-awareness.md) | Agents stuck in loops burn real money. Hard budget stops. |
| 09 | [Multimodal ingestion](09-multimodal-ingestion.md) | Graphify-style. Only matters if your repos include docs/images/video. |

## What each spec contains

- **Context** — the failure mode being addressed
- **Goal** — one-sentence outcome
- **Approach** — concrete integration points with existing skills/scripts
- **Success criteria** — how we know it works
- **Effort** — rough size (small / medium / large)
- **Depends on** — other specs that should land first

## Implementation convention

When picking up a spec:

1. Create a feature branch `feat/spec-XX-<short-slug>`
2. Add an entry to `CHANGELOG.md` under an "Unreleased" section
3. Write the feature following TDD (as the rest of the project does)
4. Update the spec file's `Status` field when merged

Status values: `pending` · `in-progress` · `in-review` · `done` · `deferred`
