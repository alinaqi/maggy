# Spec 08: Auto-Derived CODE_INDEX from Graph

**Status:** pending
**Priority:** Tier 2
**Effort:** Small-Medium

## Context

The `code-deduplication` skill requires a `CODE_INDEX.md` in the project root — a capability index that tells the agent "this already exists, don't reimplement it." The current design asks humans (or agents) to maintain it manually.

In practice:

- Agents don't reliably update the index when they add capabilities
- Humans forget to update it
- The index drifts from reality fast
- Agents that check the index get stale info and duplicate anyway

Since we already have `codebase-memory-mcp` (symbol graph) and `iCPG` (intent graph), we can derive the capability index from them instead of hand-maintaining it.

## Goal

Auto-generate `CODE_INDEX.md` from the graph, refreshed on every commit, organized by capability so agents can check-before-write reliably.

## Approach

### Step 1 — Capability extraction pass

A new pass over the combined graph:

1. Read all `ReasonNode`s with status `fulfilled` (iCPG)
2. For each, pull the symbols they `CREATE` or `MODIFY`
3. Group by capability domain (inferred from:
   - intent's `scope` path prefixes — `app/auth/*` → "auth"
   - intent's `decision_type` — `business_goal` and `arch_decision` are top-level, `task` and `workaround` are subcategories
   - common tag patterns in the codebase)
4. For each capability, collect the main entry points (public classes/functions that serve that capability)

### Step 2 — Emit CODE_INDEX.md

```markdown
# Code Capability Index

Auto-generated from iCPG + codebase-memory-mcp. Last updated: 2026-04-20.
Run `icpg index build` to regenerate.

## Authentication
**Capability:** user auth, session management, token handling
**Entry points:**
- `app.auth.login_user()` [app/auth/login.py:42] — primary login
- `app.auth.session.SessionManager` [app/auth/session.py] — session lifecycle
**Intents:** R-auth-base, R-jwt-refactor, R-rate-limit

## Survey responses
**Capability:** create, validate, persist, query survey responses
**Entry points:** ...
```

Output is deterministic — same graph state produces the same output.

### Step 3 — Hook into post-commit

Every commit that records new iCPG edges triggers a regeneration. Runs in under a second for typical repo sizes since it's a DB scan + markdown emit.

### Step 4 — `icpg index` subcommand

```bash
icpg index build        # regenerate CODE_INDEX.md
icpg index check        # verify CODE_INDEX.md matches graph state (for CI)
icpg index query auth   # query a specific capability section
```

The `check` subcommand lets CI reject commits that leave an out-of-sync CODE_INDEX.

### Step 5 — Agent workflow integration

The `code-deduplication` skill's pre-write discipline stays the same, but the data source changes from "human-maintained CODE_INDEX.md" to "graph-derived CODE_INDEX.md." Update the skill to:

1. Call `icpg query prior "<goal>"` (iCPG's existing prior-work query)
2. If no match, consult the index sections matching the intent's scope
3. Only create new code if both checks are dry

Also add `icpg query capability "<description>"` — a semantic search over capability descriptions in the index, not just symbol names.

### Step 6 — Keep hand-written sections (optional)

Let humans add non-derived sections (architecture notes, business domain glossary) in a separate file — `CODE_INDEX.human.md` — and `icpg index build` appends it. Auto-derived + human annotations cleanly separated.

## Integration points

- `scripts/icpg/index.py` — new module, grouping + emit logic
- `scripts/icpg/__main__.py` — `index build`, `index check`, `index query` subcommands
- `hooks/post-commit-graph` — call `icpg index build`
- `skills/code-deduplication/SKILL.md` — update to reference auto-derived index
- `templates/CODE_INDEX.md` — deprecate the hand-maintained template; add note pointing to the auto-generated path

## Success criteria

1. On any repo with iCPG populated, `icpg index build` produces a grouped, readable CODE_INDEX.md
2. `icpg index check` detects drift between graph and markdown (for CI)
3. Agents find existing capabilities via semantic search (`icpg query capability "rate limiting"`)
4. Generation is deterministic — same graph → same markdown
5. Backward compatible: projects without iCPG continue to hand-maintain; projects with iCPG get the auto version
6. Regeneration is <2s on a 10k-symbol repo

## Depends on

- iCPG (required)
- codebase-memory-mcp (preferred — used for richer capability grouping)
