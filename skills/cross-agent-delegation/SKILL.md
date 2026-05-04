---
name: cross-agent-delegation
description: Cross-agent task routing — Codex auto-review, Kimi delegation by complexity score (iCPG + Claude reasoning), iCPG + Mnemos mandatory for all agents
when-to-use: Always loaded when multiple AI CLI tools are available (Claude, Kimi, Codex)
user-invocable: false
effort: medium
---

# Cross-Agent Delegation

Claude Code orchestrates task routing to Kimi and Codex. The user interacts with Claude only — delegation happens behind the scenes.

---

## Tool Detection

At session start, detect available tools:

```bash
command -v kimi &>/dev/null && HAS_KIMI=true || HAS_KIMI=false
command -v codex &>/dev/null && HAS_CODEX=true || HAS_CODEX=false
```

---

## Codex Auto-Review (Stop Hook — Automatic)

When Codex is installed, a Stop hook reviews code after tests pass:

1. TDD loop check runs tests
2. `codex-auto-review.sh` runs Codex on the diff
3. Critical/High findings feed back to Claude (exit 2)
4. Clean reviews pass through (exit 0)

**Fully automatic.** No user or Claude action needed.

---

## Kimi Delegation (Claude Orchestrates)

When Kimi is installed and the task complexity is bounded, Claude delegates directly — the user does not need to run anything.

### Step 1: Score complexity, not file count

File count is a poor proxy for delegation risk. A 1-file change to an authz path is harder than a 12-file rename. Score the task on five dimensions, each 0-2, sourced from iCPG signals plus Claude's semantic reasoning:

| Dimension | 0 (low) | 1 (medium) | 2 (high) | Source |
|---|---|---|---|---|
| **Cyclomatic / surface depth** | <10 LOC, no branches | 10-50 LOC, ≤3 branches | 50+ LOC or nested control flow | iCPG `query_graph` over function bodies |
| **Fan-out (consumer blast radius)** | 0-2 callers | 3-10 callers | 11+ callers | iCPG `trace_path(<symbol>, mode=callers)` |
| **Crosses a security boundary** (SEC-006, auth, PII, RLS, org-scope, billing, payments) | None | Tangential | Direct read or write | iCPG SEC-* / R-063 tags + grep for `org_id`, `user_id`, `auth`, `pii` |
| **Concurrency / transactional** | Pure / sync | Async only | Locks, transactions, atomic claims, `FOR UPDATE`, `asyncio.Lock`, `session.begin` | iCPG concurrency flags + grep |
| **Domain invariants required** | None / well-documented inline | Some implicit (need to read 1-2 files) | Heavy (cross-doc, ADR-bound, RFC-bound) | Claude reasoning + iCPG ADR linkage |

```bash
# Auto-collect signals
icpg query blast <scope> --format json    # fan-out, async flags, sec tags
grep -rE "org_id|user_id|auth|pii"  <file>  # cheap sec heuristic if iCPG flags absent
grep -rE "asyncio.Lock|FOR UPDATE|session.begin" <file>  # concurrency heuristic
```

### Step 2: Sum → routing

| Total score | Route | Rationale |
|---|---|---|
| **0-3** | Kimi solo | Bounded surface, no security/concurrency/cross-doc concerns |
| **4-6** | Kimi → Codex auto-review (no user prompt) | Real risk, but not so high that we need full Claude context — Codex catches what Kimi might miss |
| **7-10** | Claude handles directly | Cross-cutting / security-critical / concurrency-heavy — needs full context |

### Step 3: Floor — trivial-case shortcut

To skip iCPG-query cost on truly trivial work:

```bash
# If <2 files changed AND no SEC/auth/PII/concurrency keyword in diff,
# → auto-Kimi without scoring.
FILES=$(git diff --name-only | wc -l)
HAS_RISK_KEYWORDS=$(git diff | grep -ciE "org_id|auth|pii|asyncio|FOR UPDATE|transaction|session\.begin" || true)
if [ "$FILES" -lt 2 ] && [ "$HAS_RISK_KEYWORDS" -eq 0 ]; then
  AUTO_KIMI=true
fi
```

This handles the trivial-rename / typo-fix case without paying the iCPG round-trip.

### When NOT to Delegate (overrides scoring)

- User explicitly asked Claude to do it
- Cross-service changes (API + frontend + database) — needs full context regardless of score
- Production hotfix on a release branch — cross-tool review latency is too high
- Score 7+ in any single dimension (one critical axis is enough to keep Claude in the loop)

### Step 4: Delegate via Bash

Claude writes a mnemos checkpoint, then runs Kimi headless:

```bash
# 1. Save current context to disk
mnemos checkpoint --force

# 2. Get context summary for Kimi
CONTEXT=$(mnemos resume 2>/dev/null)

# 3. Get constraints for target files
CONSTRAINTS=$(icpg query constraints <target-file> 2>/dev/null)

# 4. Run Kimi headless with full context
kimi --print -y -w . -p "
## Context (from mnemos checkpoint)
$CONTEXT

## Constraints (from iCPG)
$CONSTRAINTS

## Task
<specific task description>

## Rules
- Run tests after changes
- Record changes: icpg record --base main
- Write checkpoint when done: mnemos checkpoint --force
"
```

### Step 4: Read Results

After Kimi finishes, Claude:

```bash
# Read what Kimi did
mnemos resume          # Kimi's checkpoint
icpg status            # Kimi's recorded symbols
git diff               # Kimi's file changes
```

### When NOT to Delegate

- Security-sensitive code (auth, crypto, payments)
- Cross-service changes (API + frontend + database)
- Refactors that touch shared interfaces
- User explicitly asked Claude to do it

---

## iCPG — Mandatory for All Agents

Before ANY code change, Claude runs these (and includes results when delegating):

### Pre-Task Queries

```bash
# 1. Duplicate check — already done?
icpg query prior "<goal>"

# 2. Constraints — what invariants apply?
icpg query constraints <file-path>

# 3. Risk — is this symbol fragile?
icpg query risk <symbol-name>
```

### After Code Changes

```bash
icpg record --reason <id> --base main
icpg drift check
```

---

## Mnemos — Mandatory for All Agents

### At Task Start

```bash
mnemos add goal "<task description>"
```

### At Sub-Goal Boundaries

```bash
mnemos checkpoint
```

### At Task End (auto-handled by Stop hook)

```bash
mnemos checkpoint --force
```

### Context Transfer Between Tools

The checkpoint is the bridge. Claude writes it, Kimi reads it:

```bash
# Claude saves state
mnemos checkpoint --force

# Kimi (or Codex) reads state
mnemos resume
```

The checkpoint contains: goal, constraints, recent files, git state, fatigue level.

---

## Full Orchestration Flow

```
TASK ARRIVES (user tells Claude)
    |
    v
[1] Claude: icpg query prior "<goal>"     ← Already done?
[2] Claude: trivial-case shortcut         ← <2 files & no risk keywords?
    |
    +-- YES + Kimi installed -----> AUTO-KIMI (no scoring)
    |
    +-- NO ↓
    v
[3] Claude: score complexity (5 dims × 0-2, iCPG + reasoning)
    |
    +-- score 0-3   ----> KIMI SOLO PATH
    |   [a] mnemos checkpoint --force
    |   [b] kimi --print -y -p "..."
    |   [c] mnemos resume + git diff
    |   [d] Continue in Claude
    |
    +-- score 4-6   ----> KIMI + CODEX REVIEW PATH
    |   [a] mnemos checkpoint --force
    |   [b] kimi --print -y -p "..."
    |   [c] codex review --uncommitted    ← Auto-review the diff
    |   [d] If P0/P1 findings: re-prompt Kimi with findings
    |   [e] Once clean: continue in Claude
    |
    +-- score 7-10  ----> CLAUDE DIRECT PATH (full context)
    |
    v
[4] icpg query constraints <files>         ← Invariants
[5] icpg query risk <symbols>              ← Fragility
[6] mnemos add goal "<task>"               ← Track in memory
    |
    v
[7] IMPLEMENT (TDD: RED -> GREEN)
    |
    v
[8]  Stop: tdd-loop-check.sh               ← Tests pass?
[9]  Stop: codex-auto-review.sh            ← Codex reviews diff
[10] Stop: icpg-stop-record.sh             ← Record symbols
[11] Stop: mnemos-checkpoint.sh            ← Save memory
```
