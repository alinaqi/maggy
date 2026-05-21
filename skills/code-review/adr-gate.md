---
name: adr-gate
description: Pre-review gate that enforces ADR and spec linkage before code review proceeds
when-to-use: Automatically before every /code-review invocation
user-invocable: false
effort: low
---

# ADR Gate — Pre-Review Spec Enforcement

Every code review must have architectural context. This gate runs before review engines and ensures changes are linked to ADRs (Architecture Decision Records) and specs.

---

## Gate Protocol

Before any review engine runs, execute this sequence:

```
Changed files detected
      |
      v
[1. Classify change scope]
      |
      v
  Trivial? ──YES──> Skip gate, proceed to review
      |
      NO
      v
[2. Discover linked ADRs + specs]
      |
      v
  Found? ──YES──> Inject into review context
      |
      NO
      v
[3. Reverse-engineer ADR draft]
      |
      v
[4. Present draft to user OR auto-tag as "proposed"]
      |
      v
[5. Proceed to review with ADR context]
```

---

## Step 1: Classify Change Scope

Exempt trivial changes from ADR requirements:

### Trivial (Skip Gate)
- Typo fixes, comment edits, whitespace
- Dependency version bumps (patch/minor)
- Test-only changes that don't alter behavior
- Config value changes (not structural)
- Changelog/README updates

### Detection
```bash
# If ALL changed files match trivial patterns, skip gate
TRIVIAL_PATTERNS="CHANGELOG|README|\.lock$|\.md$|__snapshots__|\.test\.|\.spec\."
```

### Non-Trivial (Gate Applies)
- New files or deleted files
- Changes to API routes, models, schemas
- Security-related files (auth, crypto, permissions)
- Architecture changes (new services, new patterns)
- Database migrations

---

## Step 2: Discover ADRs + Specs

Search in order — stop when context is sufficient:

### 2a. Check `docs/adr/` directory
```bash
# List existing ADRs
ls docs/adr/*.md 2>/dev/null

# Search ADR content for references to changed files/modules
grep -rl "module_name\|feature_name" docs/adr/ 2>/dev/null
```

### 2b. Query iCPG (if indexed)
```
search_graph(name_pattern="*", label="ReasonNode")
```
Match ReasonNodes to changed file paths. If iCPG is not available, skip — this step is optional.

### 2c. Check `_project_specs/`
```bash
# Search specs for references to the changed area
grep -rl "feature_name\|module_name" _project_specs/ 2>/dev/null
```

### 2d. Check git history for decision context
```bash
# Get commit messages that explain WHY for changed files
git log --oneline -10 -- <changed_files>
git log --grep="decision\|chose\|instead of\|trade-off" -5
```

### 2e. Check issue tracker references
```bash
# Look for ticket references in recent commits
git log --oneline -20 | grep -oE "(#[0-9]+|[A-Z]+-[0-9]+)"

# Check PR description if in PR context
gh pr view --json body -q .body 2>/dev/null
```

### Discovery Output
Produce an ADR context block:

```markdown
## ADR Context for Review

### Linked ADRs
- ADR-0003: Use Zustand for state management (accepted)
- ADR-0007: Atomic file writes for editor (accepted)

### Linked Specs
- _project_specs/phase-08-editor.md
- GitHub Issue #25: In-browser file editor

### Relevant Decisions (from git history)
- "Chose atomic write via temp+rename over direct write" (commit abc123)

### Coverage
- 3/5 changed files have ADR linkage
- 2 files have no documented decision context
```

---

## Step 3: Reverse-Engineer ADR Draft

When ADRs are missing for non-trivial changes, draft one:

### Input Sources
1. `git log --follow -5 <file>` — commit messages for intent
2. `git diff` — what actually changed
3. File content — module structure, imports, patterns
4. PR description (if available)

### Draft Template
```markdown
# NNNN - [Auto-generated title from change description]

**Status:** proposed
**Date:** [today]
**Spec:** [discovered spec or "none — needs linking"]
**Deciders:** [git author]

## Context
[Extracted from commit messages and PR description]

## Decision
[Inferred from the code changes — what pattern/library/approach was chosen]

## Consequences
[Inferred trade-offs from the implementation]

## Alternatives Considered
[If git history shows rejected approaches, include them]
```

---

## Step 4: Present or Auto-Tag

### Interactive Mode (default when user is present)
Present the draft ADR:
```
No ADR found for changes to src/services/editor.ts.
Here's a draft based on git history and code:

  # 0008 - Atomic file writes for editor API
  Status: proposed
  Decision: Use temp file + os.rename for atomic saves
  Context: Editor needs crash-safe writes...

Accept this ADR? [Y/edit/skip]
```

### Unattended Mode (CI/CD, headless)
- Write ADR draft as `docs/adr/NNNN-draft-TITLE.md` with `Status: proposed`
- Log warning: "ADR auto-generated as proposed — needs human review"
- Do NOT mark as "accepted" — only humans accept ADRs
- Review proceeds with the proposed ADR as context

### Configuration
Set in project CLAUDE.md or `.claude/settings.json`:
```toml
[adr-gate]
mode = "interactive"   # interactive | unattended | strict
# interactive: ask user to confirm ADR drafts
# unattended: auto-write as proposed, proceed
# strict: block review until ADR exists (not auto-generated)
```

---

## Step 5: Inject into Review Context

Prepend this block to the review prompt sent to any engine:

```markdown
## Architectural Context (ADR Gate)

### Active ADRs for This Change
[List of relevant ADRs with status and summary]

### Linked Specifications
[List of specs/tickets with key requirements]

### Review Against ADRs
In addition to standard review categories, verify:
1. Does this change conform to the linked ADRs?
2. Does it introduce decisions not captured in any ADR?
3. Should any existing ADR be updated or superseded?
4. Are there spec requirements not addressed by this change?
```

---

## New Review Dimension: ADR Compliance

Added to the standard review categories:

| Category | What It Checks |
|----------|----------------|
| **ADR Compliance** | Change conforms to documented decisions, no undocumented architectural shifts |

### Severity for ADR Issues
| Finding | Severity |
|---------|----------|
| Change contradicts accepted ADR | Critical |
| Architectural decision not in any ADR | High |
| ADR exists but is outdated/stale | Medium |
| Minor drift from ADR intent | Low |

---

## Post-Review: Decision Extraction

After review completes, extract new decisions:

1. If review flagged architectural choices → prompt to create ADR
2. If review approved a new pattern → log to `_project_specs/session/decisions.md`
3. If review found ADR drift → flag ADR for update

### Auto-Log Format (decisions.md)
```markdown
- [YYYY-MM-DD] **[Review Finding]**: Brief description
  - Source: Code review of [PR/commit]
  - ADR: Created/Updated ADR-NNNN
  - Impact: [What changed]
```

---

## ADR Numbering

ADRs use sequential 4-digit numbers: `0001`, `0002`, etc.

### Auto-Number Logic
```bash
# Find next ADR number
LAST=$(ls docs/adr/*.md 2>/dev/null | sort -t- -k1 -n | tail -1 | grep -oE '[0-9]{4}' | head -1)
NEXT=$(printf "%04d" $((${LAST:-0} + 1)))
```

---

## Project Init Integration

When a project is initialized via claude-bootstrap:
1. Create `docs/adr/` directory
2. Write `docs/adr/0001-project-init.md` with tech stack decisions
3. Add `docs/adr/` to the file structure documentation
4. Register ADR pattern in session decisions.md

---

## Quick Reference

```
/code-review          → ADR gate runs automatically before review
docs/adr/NNNN-*.md   → ADR storage location
_project_specs/       → Spec storage (phases, roadmap)
decisions.md          → Session decision log (auto-appended)

ADR statuses: proposed → accepted → deprecated/superseded
Gate modes:   interactive | unattended | strict
```
