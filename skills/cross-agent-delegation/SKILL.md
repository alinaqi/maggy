---
name: cross-agent-delegation
description: Cross-agent task routing — Codex auto-review, Kimi delegation by blast radius, iCPG + Mnemos mandatory for all agents
when-to-use: Always loaded when multiple AI CLI tools are available (Claude, Kimi, Codex)
user-invocable: false
effort: medium
---

# Cross-Agent Delegation

Route tasks to the right AI CLI tool based on blast radius. Use iCPG for code intelligence and Mnemos for memory in every tool.

---

## Tool Detection

Before any delegation, check what's installed:

```bash
# Detect available tools
command -v claude &>/dev/null && HAS_CLAUDE=true
command -v kimi &>/dev/null && HAS_KIMI=true
command -v codex &>/dev/null && HAS_CODEX=true
```

---

## Codex Auto-Review (Stop Hook)

When Codex is installed, a Stop hook automatically reviews code after tests pass:

1. TDD loop check runs tests
2. If tests pass, `codex-auto-review.sh` runs
3. Codex reviews the diff for Critical/High issues
4. Critical/High findings feed back to Claude (exit 2)
5. Clean reviews pass through (exit 0)

**No action needed** — the hook handles this automatically. To disable, remove the hook from `.claude/settings.json`.

---

## Kimi Delegation (Token Optimization)

Before starting any non-trivial task, check the iCPG blast radius:

```bash
icpg query blast <scope-or-reason-id>
```

### Delegation Rules

| Blast Radius | Recommendation | Command |
|-------------|---------------|---------|
| 1-3 files | Suggest Kimi | `kimi -y "<task description>"` |
| 4-8 files | Offer Kimi as option | "Medium scope — Kimi could handle this, or continue here" |
| 9+ files | Stay in Claude | Complex task, needs full context window |

### Example Suggestion

When blast radius is small:

> This task affects 2 files (`src/utils/format.ts`, `tests/format.test.ts`).
> To save tokens, you could run this with Kimi:
> ```
> kimi -y "Add date formatting util to src/utils/format.ts with tests"
> ```
> Or I can handle it here. Your call.

### When NOT to Delegate

- Security-sensitive code (auth, crypto, payments)
- Cross-service changes (API + frontend + database)
- Refactors that touch shared interfaces
- When the user explicitly asked Claude to do it

---

## iCPG — Mandatory for All Agents

**Every agent (Claude, Kimi, Codex) MUST run these before writing code:**

### The 3 Pre-Task Queries

```bash
# 1. Duplicate detection — has this been done before?
icpg query prior "<goal description>"

# 2. Constraints — what invariants apply to files I'll touch?
icpg query constraints <file-path>

# 3. Risk — is this symbol fragile?
icpg query risk <symbol-name>
```

### After Code Changes

```bash
# Record symbols linked to intent
icpg record --reason <id> --base main

# Check for unintended drift
icpg drift check
```

### For Kimi and Codex

Both tools can run `icpg` commands directly since it's a CLI tool:

```bash
# In Kimi session
kimi -y "Run: icpg query prior 'add user validation' && icpg query constraints src/api/users.ts"

# In Codex session
codex exec "Run icpg query prior 'add user validation' before making changes"
```

---

## Mnemos — Mandatory for All Agents

**Every agent uses Mnemos for memory management:**

### At Task Start

```bash
mnemos add goal "<what you're trying to achieve>" --task-id <session-id>
```

### During Work

```bash
# Check fatigue before long operations
mnemos fatigue

# Checkpoint at sub-goal boundaries
mnemos checkpoint
```

### At Task End

```bash
# Final checkpoint (auto-handled by Stop hook)
mnemos checkpoint --force
```

### For Kimi and Codex

Mnemos hooks fire automatically for Claude. For Kimi/Codex, the same hooks are in `config.toml`. Manual commands also work:

```bash
# Resume from last checkpoint
mnemos resume

# Check memory status
mnemos status
```

---

## Cross-Agent Workflow Summary

```
TASK ARRIVES
    |
    v
[1] icpg query prior "<goal>"        ← Duplicate check
[2] icpg query blast <scope>          ← Blast radius
    |
    +-- radius <= 3 files? ---------> Suggest Kimi
    +-- radius 4-8 files? ----------> Offer Kimi option
    +-- radius 9+ files? -----------> Stay in Claude
    |
    v
[3] icpg query constraints <files>    ← Invariants
[4] icpg query risk <symbols>         ← Fragility
[5] mnemos add goal "<task>"          ← Memory tracking
    |
    v
[6] IMPLEMENT (TDD: RED -> GREEN)
    |
    v
[7] Stop hook: tdd-loop-check.sh     ← Tests pass?
[8] Stop hook: codex-auto-review.sh   ← Codex reviews (if installed)
[9] Stop hook: icpg-stop-record.sh    ← Record symbols
[10] Stop hook: mnemos-checkpoint.sh   ← Save memory
```
