---
name: agent-teams
description: Claude Code Agent Teams - default team-based development with strict TDD pipeline enforcement
when-to-use: When spawning agent teams for parallel feature development with TDD pipeline
user-invocable: false
effort: high
---

# Agent Teams Skill


**Purpose:** Every project initialized with Maggy runs as a coordinated team of AI agents. This is the default workflow, not optional. Teams enforce a strict TDD pipeline where no step can be skipped.

**Setup:** Agent definitions go in `.claude/agents/` with proper frontmatter (name, description, model, tools, disallowedTools, maxTurns, effort). See agent files for the format.

---

## Core Principle

Every feature follows an immutable pipeline enforced by task dependencies:

```
┌─────────────────────────────────────────────────────────────────┐
│  STRICT FEATURE PIPELINE (IMMUTABLE)                            │
│  ──────────────────────────────────────────────────────────────  │
│                                                                  │
│  1. SPEC        Write feature specification                      │
│       ↓         (Feature Agent)                                  │
│  2. REVIEW      Quality Agent reviews spec completeness          │
│       ↓         (Quality Agent)                                  │
│  3. TESTS       Write failing tests for all acceptance criteria  │
│       ↓         (Feature Agent)                                  │
│  4. RED VERIFY  Quality Agent confirms ALL tests FAIL            │
│       ↓         (Quality Agent)                                  │
│  5. IMPLEMENT   Write minimum code to pass tests                 │
│       ↓         (Feature Agent)                                  │
│  6. GREEN VERIFY Quality Agent confirms ALL tests PASS + coverage│
│       ↓         (Quality Agent)                                  │
│  7. VALIDATE    Lint + type check + full test suite              │
│       ↓         (Feature Agent)                                  │
│  8. CODE REVIEW Multi-engine review, block on Critical/High      │
│       ↓         (Code Review Agent)                              │
│  9. SECURITY    OWASP scan, secrets detection, dependency audit  │
│       ↓         (Security Agent)                                 │
│  10. BRANCH+PR  Create feature branch, stage files, create PR    │
│                 (Merger Agent)                                    │
│                                                                  │
│  No step can be skipped. Task dependencies enforce ordering.     │
│  Quality Agent verifies RED/GREEN transitions.                   │
│  Code Review + Security Agents gate the merge path.              │
│  Merger Agent handles branching and PR creation.                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Default Agent Roster

Every project spawns 5 permanent agents + N feature agents:

```
┌─────────────────────────────────────────────────────────────────┐
│  DEFAULT TEAM ROSTER                                             │
│  ──────────────────────────────────────────────────────────────  │
│                                                                  │
│  PERMANENT AGENTS (always present)                               │
│  ─────────────────────────────────                               │
│  Team Lead        Orchestration, task breakdown, assignment      │
│                   Uses delegate mode - NEVER writes code         │
│                                                                  │
│  Quality Agent    TDD verification (RED/GREEN phases)            │
│                   Coverage gates (>= 80%)                        │
│                   Spec completeness review                       │
│                                                                  │
│  Security Agent   OWASP scanning, secrets detection              │
│                   Dependency audit, .env validation               │
│                   Blocks on Critical/High                        │
│                                                                  │
│  Code Review Agent  Multi-engine code review                     │
│                     Claude / Codex / Gemini / All                │
│                     Blocks on Critical/High                      │
│                                                                  │
│  Merger Agent     Creates feature branches                       │
│                   Stages feature-specific files only              │
│                   Creates PRs via gh CLI                          │
│                   NEVER merges - only creates PRs                │
│                                                                  │
│  DYNAMIC AGENTS (one per feature)                                │
│  ────────────────────────────────                                │
│  Feature Agent    Implements one feature end-to-end              │
│  (x N features)   Follows strict pipeline above                  │
│                   Uses Ralph loops for implementation             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| Agent | Role | Plan Mode | Can Edit Code |
|-------|------|-----------|---------------|
| team-lead | Orchestration, task breakdown, assignment | No (delegate mode) | No |
| quality-agent | TDD verification, coverage gates | Yes | No (read-only) |
| security-agent | OWASP scanning, secrets detection | Yes | No (read-only) |
| review-agent | Multi-engine code review | Yes | No (read-only) |
| merger-agent | Branch creation, PR management | No | No (git only) |
| feature-{name} | Feature implementation (one per feature) | No | Yes |

---

## Team Lead Responsibilities

The Team Lead is the orchestrator. It NEVER writes code.

1. Read `_project_specs/features/*.md` to identify all features
2. Break each feature into the 10-task dependency chain (see below)
3. Spawn one feature agent per feature
4. Assign initial tasks (spec-writing) to feature agents
5. Monitor TaskList continuously for progress and blockers
6. Handle blocked tasks and reassignment
7. Coordinate cross-feature dependencies
8. Send `shutdown_request` to all agents when all PRs are created
9. Clean up the team when done

**Delegate mode is mandatory.** The team lead uses only:
- TeamCreate, TaskCreate, TaskUpdate, TaskList, TaskGet
- SendMessage (message, broadcast, shutdown_request)
- Read, Glob, Grep (for monitoring)

---

## Feature Agent Workflow (MANDATORY)

Each feature agent MUST follow this exact sequence. Task dependencies enforce ordering - a feature agent cannot start step N+1 until step N is marked complete and verified.

### Step 1: Write Spec
- Create `_project_specs/features/{feature-name}.md`
- Include: description, acceptance criteria, test cases table, dependencies
- Follow the atomic TODO format from base.md skill
- Mark task complete -> Quality Agent reviews

### Step 2: Write Tests (RED Phase)
- Write test files based on spec's test cases table
- Tests MUST cover ALL acceptance criteria
- Import modules that don't exist yet (they will fail)
- Mark task complete -> Quality Agent verifies tests EXIST and FAIL

### Step 3: Wait for RED Verification
- Quality Agent runs tests and verifies ALL new tests fail
- If any test passes without implementation -> rewrite tests
- Quality Agent marks verification complete -> unlocks implementation

### Step 4: Implement (GREEN Phase)
- Write minimum code to make all tests pass
- Follow simplicity rules from base.md (20 lines/function, 200 lines/file, 3 params)
- Use Ralph loops (`/ralph-loop`) for iterative implementation
- Run tests after implementation - ALL must pass
- Mark task complete -> Quality Agent verifies tests pass

### Step 5: Wait for GREEN Verification
- Quality Agent runs full test suite and checks coverage
- Coverage must be >= 80%
- If tests fail or coverage insufficient -> fix and re-request
- Quality Agent marks verification complete -> unlocks validation

### Step 6: Validate
- Run linter (ESLint / Ruff)
- Run type checker (TypeScript / mypy)
- Run full test suite with coverage
- Fix any issues
- Mark task complete -> unlocks code review

### Step 7: Wait for Code Review
- Code Review Agent runs `/code-review` on changed files
- If Critical or High issues -> fix and re-request review
- Code Review Agent marks complete -> unlocks security scan

### Step 8: Wait for Security Scan
- Security Agent runs security checks
- If Critical or High issues -> fix and re-request scan
- Security Agent marks complete -> unlocks merge

### Step 9: Wait for Branch + PR
- Merger Agent creates feature branch, stages files, creates PR
- Feature is complete when PR is created

---

## Task Dependency Chain Model

For each feature "X", the team lead creates these 10 tasks with strict ordering:

```
┌────────────────────────────────────────────────────────────────┐
│  TASK CHAIN FOR FEATURE "X"                                     │
│                                                                  │
│  Task 1:  X-spec                                                │
│           owner: feature-X                                       │
│           blockedBy: (none)                                      │
│           ↓                                                      │
│  Task 2:  X-spec-review                                         │
│           owner: quality-agent                                   │
│           blockedBy: X-spec                                      │
│           ↓                                                      │
│  Task 3:  X-tests                                               │
│           owner: feature-X                                       │
│           blockedBy: X-spec-review                               │
│           ↓                                                      │
│  Task 4:  X-tests-fail-verify                                   │
│           owner: quality-agent                                   │
│           blockedBy: X-tests                                     │
│           ↓                                                      │
│  Task 5:  X-implement                                           │
│           owner: feature-X                                       │
│           blockedBy: X-tests-fail-verify                         │
│           ↓                                                      │
│  Task 6:  X-tests-pass-verify                                   │
│           owner: quality-agent                                   │
│           blockedBy: X-implement                                 │
│           ↓                                                      │
│  Task 7:  X-validate                                            │
│           owner: feature-X                                       │
│           blockedBy: X-tests-pass-verify                         │
│           ↓                                                      │
│  Task 8:  X-code-review                                         │
│           owner: review-agent                                    │
│           blockedBy: X-validate                                  │
│           ↓                                                      │
│  Task 9:  X-security-scan                                       │
│           owner: security-agent                                  │
│           blockedBy: X-code-review                               │
│           ↓                                                      │
│  Task 10: X-branch-pr                                           │
│           owner: merger-agent                                    │
│           blockedBy: X-security-scan                             │
└────────────────────────────────────────────────────────────────┘
```

### Parallel Feature Execution

Multiple features run their chains in parallel. Shared agents process tasks as they unblock:

```
Feature: auth         Feature: dashboard      Feature: payments
  auth-spec             dash-spec               pay-spec
  auth-spec-review      dash-spec-review        pay-spec-review
  auth-tests            dash-tests              pay-tests
  auth-fail-verify      dash-fail-verify        pay-fail-verify
  auth-implement        dash-implement          pay-implement
  auth-pass-verify      dash-pass-verify        pay-pass-verify
  auth-validate         dash-validate           pay-validate
  auth-code-review      dash-code-review        pay-code-review
  auth-security         dash-security           pay-security
  auth-branch-pr        dash-branch-pr          pay-branch-pr
       |                     |                       |
       v                     v                       v
   [All chains run simultaneously]
   [Quality Agent handles all verify tasks as they unblock]
   [Review Agent handles all review tasks as they unblock]
   [Security Agent handles all scan tasks as they unblock]
   [Merger Agent handles all branch-pr tasks as they unblock]
```

---

## Inter-Agent Communication

### Direct Messages (for targeted work)
```
Feature Agent -> Quality Agent:  "Tests written for auth, ready for RED verify"
Quality Agent -> Feature Agent:  "All 7 tests fail as expected. Proceed to implement"
Feature Agent -> Review Agent:   "Implementation complete, ready for code review"
Review Agent  -> Feature Agent:  "2 High issues found: [details]. Fix before proceeding"
Security Agent -> Merger Agent:  "Security scan passed for auth feature"
Merger Agent  -> Team Lead:      "PR #42 created for auth feature"
```

### Task List (source of truth for state)
- All agents check TaskList after completing work
- Quality Agent claims verification tasks automatically
- Review Agent claims code-review tasks automatically
- Security Agent claims security-scan tasks automatically
- Merger Agent claims branch-pr tasks automatically

### Broadcast (rare - blocking issues only)
- Team Lead -> All: "Blocking dependency found between auth and dashboard"
- Security Agent -> All: "Critical vulnerability in shared dependency"

---

## Feature Agent Spawning

The team lead spawns one feature agent per feature:

1. Read `_project_specs/features/*.md`
2. For each feature spec, spawn a feature agent:
   - name: `feature-{feature-name}`
   - Uses `.claude/agents/feature.md` definition
   - Spawn prompt includes the feature name and spec location
3. Create the full 10-task dependency chain for that feature
4. Assign the spec-writing task to the feature agent

### Example
If project has 3 features: auth, dashboard, payments
- Spawn: `feature-auth`, `feature-dashboard`, `feature-payments`
- Create 30 tasks total (10 per feature)
- Each feature agent starts with their spec task
- All 3 work in parallel

---

## Branch and PR Strategy

**One branch per feature. One PR per feature.**

```
Branch naming:  feature/{feature-name}
PR title:       feat({feature-name}): {short description}
PR body:        Generated from spec + test results + review + security results
```

The Merger Agent:
1. `git checkout main && git pull origin main`
2. `git checkout -b feature/{feature-name}`
3. Stages ONLY files changed for this feature (never `git add -A`)
4. Commits with descriptive message including verification results
5. `git push -u origin feature/{feature-name}`
6. `gh pr create` with full template including:
   - Summary from feature spec
   - Test results from quality verification
   - Code review summary from review agent
   - Security scan results from security agent
   - Checklist of all pipeline steps completed

---

## Quality Gates

### Workflow Enforcement (via task dependencies)
- Task dependencies make it **structurally impossible** to skip steps
- A feature agent cannot see "implement" until quality agent completes "tests-fail-verify"
- This is the primary enforcement mechanism

### Cross-Agent Verification (trust but verify)
- Quality agent independently runs tests (doesn't trust feature agent's report)
- Security agent independently scans (doesn't trust review agent)
- Merger agent verifies all predecessor tasks are complete before branching

### Blocking Rules
- Quality Agent: blocks if tests don't fail (RED) or don't pass (GREEN) or coverage < 80%
- Code Review Agent: blocks on Critical or High severity issues
- Security Agent: blocks on Critical or High severity findings
- Merger Agent: refuses to branch if any predecessor task is incomplete

---

## Integration with Existing Skills

| Existing Skill | How Agent Teams Uses It |
|----------------|------------------------|
| base.md | TDD workflow, atomic todos, simplicity rules - all agents follow |
| code-review.md | Review Agent executes `/code-review` per this skill |
| security.md | Security Agent follows OWASP patterns from this skill |
| session-management.md | Each agent maintains its own session state |
| iterative-development.md | Feature agents use Stop hook TDD loops for implementation |
| project-tooling.md | Merger Agent uses `gh` CLI for branches and PRs |
| team-coordination.md | Superseded by agent-teams for automated coordination |
| **icpg.md** | **Team lead creates ReasonNodes. Feature agents query constraints/risk. Quality agent checks drift. PreToolUse hook injects context. Stop hook auto-records symbols.** |
| code-graph.md | Feature agents use graph for symbol lookup alongside iCPG for intent context |

---

## Environment Setup

### Required Setting
```json
// settings.json or environment
{
  "env": {
    "agent teams (via .claude/agents/ definitions)": "1"
  }
}
```

### Project Structure (created by /initialize-project)
```
.claude/
  agents/            # Agent definitions (from agent-teams skill)
    team-lead.md
    quality.md
    security.md
    code-review.md
    merger.md
    feature.md
  skills/
    agent-teams/     # This skill
      SKILL.md
      agents/        # Agent definition templates
    base/
    code-review/
    security/
    ...
```

---

## Spawning the Team

### Automatic (via /initialize-project)
After project setup completes, Phase 6 asks for features and spawns the team automatically.

### Manual (via /spawn-team)
For existing projects: run `/spawn-team` to spawn the team from existing feature specs.

---

## Container Isolation (Polyphony)

When Docker/OrbStack is available, feature agents run in Polyphony containers by default. The team lead and shared agents (quality, security, review, merger) still run natively — they only read and coordinate.

### What changes with Polyphony

| Aspect | Without Polyphony | With Polyphony |
|--------|-------------------|----------------|
| Feature agents | Shared filesystem | Own container + git branch |
| File conflicts | Team lead must serialize | Impossible (isolated clones) |
| Test execution | Shared, can interfere | Independent per container |
| Branch strategy | Merger agent creates branches | Each container has its own branch |

### How it works

1. `/spawn-team` detects Docker + polyphony CLI
2. For each feature, runs `polyphony spawn "$FEATURE" --type feature`
3. Polyphony creates a container with its own git clone + branch
4. Agent CLI starts inside the container
5. On completion, changes are on a dedicated branch ready for PR

### Fallback

If Docker is not available, `/spawn-team` falls back to the native Agent tool (shared filesystem). A note is printed:
> "Running without container isolation (Docker not found). Agents share the workspace."

---

## Limitations

- **Experimental feature** - Agent teams require the experimental env var
- **No nested teams** - Teammates cannot spawn sub-teams
- **One team per session** - Clean up before starting a new team
- **No session resumption** - If session dies, re-run `/spawn-team` (tasks persist)
- **File conflicts** - Features sharing files must be serialized by team lead (unless using Polyphony containers)
- **Token cost** - Each agent is a separate Claude instance (5 + N instances)
