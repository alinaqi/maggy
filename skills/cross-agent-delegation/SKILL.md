---
name: cross-agent-delegation
description: Cross-agent task routing — Codex auto-review, Kimi delegation by blast radius, iCPG + Mnemos mandatory for all agents
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

When Kimi is installed and blast radius is small, Claude delegates directly — the user does not need to run anything.

### Step 1: Check Blast Radius

```bash
icpg query blast <scope-or-file>
```

### Step 2: Decide

| Blast Radius | Action |
|-------------|--------|
| 1-3 files | Claude delegates to Kimi |
| 4-8 files | Claude asks user: "Delegate to Kimi or handle here?" |
| 9+ files | Claude handles it (needs full context) |

### Step 3: Delegate via Bash

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
[2] Claude: icpg query blast <scope>       ← How many files?
    |
    +-- 1-3 files + Kimi installed? -----> DELEGATE PATH
    |   [a] mnemos checkpoint --force      ← Save context
    |   [b] kimi --print -y -p "..."       ← Run Kimi headless
    |   [c] mnemos resume                  ← Read Kimi's work
    |   [d] git diff                       ← Review changes
    |   [e] Continue in Claude
    |
    +-- 4-8 files? -----> Ask user, then delegate or continue
    +-- 9+ files? -------> DIRECT PATH (Claude handles)
    |
    v
[3] icpg query constraints <files>         ← Invariants
[4] icpg query risk <symbols>              ��� Fragility
[5] mnemos add goal "<task>"               ← Track in memory
    |
    v
[6] IMPLEMENT (TDD: RED -> GREEN)
    |
    v
[7] Stop: tdd-loop-check.sh               ← Tests pass?
[8] Stop: codex-auto-review.sh            ← Codex reviews diff
[9] Stop: icpg-stop-record.sh             ← Record symbols
[10] Stop: mnemos-checkpoint.sh            ← Save memory
```
