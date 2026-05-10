# Maggy

> **From opinionated Claude Code setup to autonomous AI engineering platform.**

Maggy started as an opinionated project initialization system for Claude Code — skills, TDD hooks, quality gates. It has evolved into a full autonomous engineering command center: interactive chat with session takeover, multi-agent orchestration in containers, P2P mesh networking across machines, AI-prioritized task triage, competitor intelligence, and process analytics. The guardrails that keep AI-generated code simple, secure, and verifiable are still the foundation — but now they power an end-to-end autonomous engineering workflow.

**v5.0.0** — Interactive Chat (`--resume` session takeover), Polyphony (container-isolated multi-agent orchestration), P2P Mesh (cross-machine session sync), auto-bootstrap, grouped dashboard navigation.

## Core Philosophy

```
┌────────────────────────────────────────────────────────────────┐
│  TDD LOOPS VIA STOP HOOKS                                      │
│  ─────────────────────────────────────────────────────────────│
│  Stop hooks run tests after each Claude response.              │
│  Failures feed back automatically. Claude iterates until green.│
│  Real Claude Code infrastructure — no plugins needed.          │
├────────────────────────────────────────────────────────────────┤
│  TESTS FIRST, ALWAYS                                           │
│  ─────────────────────────────────────────────────────────────│
│  Features: Write tests → Watch them fail → Implement → Pass    │
│  Bugs: Find test gap → Write failing test → Fix → Pass         │
│  No code ships without a test that failed first.               │
├────────────────────────────────────────────────────────────────┤
│  SIMPLICITY IS THE GOAL                                        │
│  ─────────────────────────────────────────────────────────────│
│  20 lines per function │ 200 lines per file │ 3 params max     │
│  Enforced via .claude/rules/ with paths: frontmatter.          │
├────────────────────────────────────────────────────────────────┤
│  SECURITY BY DEFAULT                                           │
│  ─────────────────────────────────────────────────────────────│
│  No secrets in code │ Permission deny rules for .env files     │
│  Dependency scanning │ Pre-commit hooks │ CI enforcement       │
├────────────────────────────────────────────────────────────────┤
│  AGENT TEAMS BY DEFAULT                                        │
│  ─────────────────────────────────────────────────────────────│
│  Every project runs as a coordinated team of AI agents.        │
│  Agent definitions use proper frontmatter: tools, model,       │
│  maxTurns, effort, disallowedTools.                            │
├────────────────────────────────────────────────────────────────┤
│  CONDITIONAL RULES                                             │
│  ─────────────────────────────────────────────────────────────│
│  Rules in .claude/rules/ activate based on file paths.         │
│  React rules only load when editing .tsx files.                │
│  Python rules only load when editing .py files.                │
│  Saves tokens. Reduces noise. More targeted guidance.          │
└────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone and install (clone anywhere you like)
git clone https://github.com/alinaqi/claude-bootstrap.git
cd claude-bootstrap && ./install.sh

# In any project directory
claude
> /initialize-project
```

Claude will:
1. **Validate tools** - Check gh, vercel, supabase CLIs
2. **Ask questions** - Language, framework, AI-first?, database, graph analysis level
3. **Set up repository** - Create or connect GitHub repo
4. **Create structure** - Skills, rules, settings, security, CI/CD, specs, todos
5. **Copy settings.json** - Pre-configured permissions and Stop hooks
6. **Generate CLAUDE.md** - With `@include` directives for modular skills
7. **Generate CLAUDE.local.md** - Template for private developer overrides
8. **Spawn agent team** - Deploy Team Lead + Quality + Security + Review + Merger + Feature agents

## Cross-Tool Compatibility (Claude + Kimi + Codex)

Maggy works with **Claude Code**, **Kimi CLI**, and **OpenAI Codex CLI**. All three use the same `SKILL.md` format.

| Feature | Claude Code | Kimi CLI | Codex CLI |
|---------|-------------|----------|-----------|
| Skills | `.claude/skills/` | `.kimi/skills/` (also reads `.claude/`) | `.codex/skills/` |
| Project instructions | `CLAUDE.md` | (uses skills) | `AGENTS.md` |
| Hooks config | `settings.json` | `config.toml` | `config.toml` |

**`install.sh`** auto-detects installed tools and installs skills to all of them.

**`/sync-agents`** syncs project config across tools on demand.

```bash
# Install tools
curl -L code.kimi.com/install.sh | bash     # Kimi
npm i -g @openai/codex                       # Codex

# Reinstall to pick up new tools
cd maggy && ./install.sh

# In any project, sync cross-tool config
claude
> /sync-agents
```

## Cross-Agent Intelligence

When multiple AI CLI tools are installed, Maggy enables intelligent collaboration between them.

### Codex Auto-Review (Stop Hook)

After tests pass, Codex automatically reviews your diff for critical bugs and security issues. Runs as a Stop hook between TDD and iCPG recording.

```
Stop hook order:
1. tdd-loop-check.sh     → tests pass?
2. codex-auto-review.sh  → Codex reviews diff (NEW)
3. icpg-stop-record.sh   → record symbols
4. mnemos-checkpoint.sh   → save memory
```

- Exit 0 = no critical issues found
- Exit 2 = critical/high issues feed back to Claude for fixing
- Gracefully skips if Codex not installed

### Kimi Delegation (Token Optimization)

Claude checks iCPG blast radius and delegates small tasks to Kimi automatically — the user doesn't run anything:

| Blast Radius | Claude's Action |
|-------------|----------------|
| 1-3 files | Saves context via `mnemos checkpoint`, runs `kimi --print -y -p "..."` with context + task |
| 4-8 files | Asks user, then delegates or handles directly |
| 9+ files | Handles directly (needs full context window) |

Context transfer uses structured state (mnemos checkpoints + iCPG constraints), not raw conversation.

### iCPG + Mnemos (Always-On for All Agents)

All three tools run the same iCPG pre-task queries and Mnemos memory lifecycle:

```bash
# Before any code change (Claude, Kimi, or Codex):
icpg query prior "<goal>"        # check for duplicate work
icpg query constraints <file>    # check invariants
icpg query risk <symbol>         # check fragility

# Memory management:
mnemos add goal "<task>"         # at task start
mnemos checkpoint                # at sub-goal boundaries
```

## How TDD Loops Work (Stop Hooks)

**No plugins. No fake commands.** Claude Code's Stop hook runs a script when Claude finishes a response. Exit code 2 feeds stderr back to Claude and continues the conversation.

```
┌─────────────────────────────────────────────────────────────┐
│  1. You say: "Add email validation to signup"               │
│  2. Claude writes tests + implementation                    │
│  3. Claude finishes response                                │
│  4. Stop hook runs: npm test && npm run lint                │
│  5a. All pass (exit 0) → Done!                              │
│  5b. Failures (exit 2) → stderr fed back to Claude          │
│  6. Claude sees failures, fixes, finishes again             │
│  7. Stop hook runs again → repeat until green               │
└─────────────────────────────────────────────────────────────┘
```

**Configuration** in `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "scripts/tdd-loop-check.sh",
        "timeout": 60,
        "statusMessage": "Running tests..."
      }]
    }]
  }
}
```

The `tdd-loop-check.sh` script runs tests, lint, and typecheck. It tracks iteration count (max 25) and distinguishes code errors (loop) from environment errors (stop).

## @include Directives

CLAUDE.md uses `@include` to modularly load skills:

```markdown
# CLAUDE.md
@.claude/skills/base/SKILL.md
@.claude/skills/iterative-development/SKILL.md
@.claude/skills/security/SKILL.md
```

These are **resolved at load time** by Claude Code — the content is recursively inlined (max depth 5, cycle detection built in). This means skills actually become part of the prompt instead of just being listed as text.

## Conditional Rules

Rules in `.claude/rules/` use YAML frontmatter with `paths:` to activate only when relevant files are being edited:

```yaml
# .claude/rules/react.md
---
paths: ["src/components/**", "**/*.tsx"]
---
Prefer functional components with hooks...
```

```yaml
# .claude/rules/python.md
---
paths: ["**/*.py"]
---
Use type hints, pytest, ruff...
```

**Included rules:**

| Rule | Activates When |
|------|----------------|
| `quality-gates.md` | Always (no paths: filter) |
| `tdd-workflow.md` | Always |
| `security.md` | Always |
| `react.md` | Editing .tsx/.jsx files |
| `typescript.md` | Editing .ts/.tsx files |
| `python.md` | Editing .py files |
| `nodejs-backend.md` | Editing api/routes/server files |

## Smarter Compaction (PreCompact Hook)

Claude Code's built-in compaction fires at ~83% context and summarizes everything into 20K tokens using a generic 9-section template. It doesn't know what YOUR project cares about.

The PreCompact hook fixes this by injecting **project-specific preservation priorities** into the summarizer:

```
┌─────────────────────────────────────────────────────────────┐
│  Built-in compaction:                                       │
│  "Summarize this conversation" → generic summary            │
├─────────────────────────────────────────────────────────────┤
│  With PreCompact hook:                                      │
│  "Summarize, but preserve ALL schema decisions verbatim,    │
│   keep exact error messages, keep API contract details,     │
│   reference these Key Decisions by name, and here's the     │
│   current git state to include" → project-aware summary     │
└─────────────────────────────────────────────────────────────┘
```

The hook auto-detects:
- **Project type** (TypeScript/Next.js, Python/FastAPI, Flutter, etc.)
- **Schema files** (Drizzle, Prisma, SQLAlchemy) → tells summarizer to preserve schema discussion
- **API directories** → tells summarizer to preserve endpoint paths and contracts
- **Key Decisions from CLAUDE.md** → tells summarizer to reference them by name
- **Git state** → injects branch, uncommitted changes, staged files

Zero overhead during normal usage. Only runs when compaction actually fires.

## Mnemos — Task-Scoped Memory Lifecycle

Claude Code's built-in compaction is lossy and unreliable. It sometimes doesn't fire, `/compact` and `/clear` can fail (especially in multi-agent executions), and crashes/restarts lose all context. Mnemos provides **disk-persistent structured state** that survives all of these failure modes.

```
┌─────────────────────────────────────────────────────────────┐
│  DEFAULT CLAUDE CODE          vs  WITH MNEMOS               │
├─────────────────────────────────────────────────────────────┤
│  Blind until 83.5%               Continuous 4-dim monitoring│
│  Sudden hard compaction           Graduated: 40→60→75→83%   │
│  Uniform summarization            Typed: goals never evict  │
│  No cross-session memory          Auto checkpoint/resume    │
│  Crash = total context loss       Crash = resume from disk  │
│  Multi-agent: no shared state     Per-agent structured state│
│  No behavioral awareness          Detects re-reads, scatter │
└─────────────────────────────────────────────────────────────┘
```

### Post-Compaction Task Restoration (Two-Layer Defense)

When compaction fires, the built-in summarizer often drops task-specific state. Mnemos uses two independent layers to guarantee restoration:

```
BEFORE COMPACTION                    AFTER COMPACTION

PreCompact hook fires                First tool call → PreToolUse fires
├── Write emergency checkpoint       ├── Detect ".mnemos/just-compacted" marker
├── Build task narrative from        ├── Read checkpoint-latest.json
│   signals.jsonl (files, tools)     ├── Output full checkpoint into context
├── Output STRONG preservation       ├── Delete marker (one-shot)
│   instructions to summarizer       └── Claude now has: summary + checkpoint
└── Write ".mnemos/just-compacted"
    marker file                      = Task fully restored
```

**Layer 1** (best-effort): PreCompact tells the summarizer what to keep, including inline checkpoint content with typed eviction priorities.

**Layer 2** (guaranteed): Post-compaction injection via PreToolUse re-injects the full checkpoint on the first tool call after compaction. Doesn't depend on the summarizer. Fast path ~5ms when no compaction occurred.

### Why Not Just Write to a Plain File?

You could — but you'd immediately face: what format? When to update? How to distinguish "this is critical" from "this is nice to have"? The MnemoGraph's typed nodes solve this:

| Node Type | Eviction Policy | Example |
|-----------|----------------|---------|
| GoalNode | NEVER evict | "Implement auth module" |
| ConstraintNode | NEVER evict | "API backward compatibility" |
| ResultNode | Compress first | "JWT middleware tested" → summary kept |
| WorkingNode | Compress first | Current reasoning / in-progress analysis |
| ContextNode | Evictable | File contents → re-read from disk |

Without typed priorities, a checkpoint is just a blob. With them, the system knows goals > constraints > working memory > context, and makes intelligent decisions about what to restore within token budgets.

### Resilience Beyond Normal Compaction

The real value isn't the happy path — it's when things go wrong:

| Failure Mode | CC Built-in | Mnemos |
|---|---|---|
| Session crash/collapse | Context gone | Checkpoint on disk survives |
| `/compact` doesn't fire | Truncation at limit | Fatigue hooks wrote checkpoints earlier |
| Multi-agent child dies | No recovery | Child's `.mnemos/` has structured state |
| Forced restart | Generic summary | SessionStart reloads full checkpoint |
| `/clear` fails in multi-agent | Stuck in weird state | MnemoGraph is independent of CC's state |

### Fatigue Model

4 dimensions passively observed from hooks — no agent cooperation needed:

| Dimension | Weight | Signal Source | Detects |
|-----------|--------|---------------|---------|
| Token utilization | 0.40 | Statusline JSON | How full the context window is |
| Scope scatter | 0.25 | PreToolUse file paths | Agent bouncing between directories |
| Re-read ratio | 0.20 | PreToolUse Read calls | Agent re-reading files (context loss) |
| Error density | 0.15 | PostToolUse outcomes | Agent struggling (high error rate) |

Fatigue states: **FLOW** (0-0.4) → **COMPRESS** (0.4-0.6) → **PRE-SLEEP** (0.6-0.75) → **REM** (0.75-0.9) → **EMERGENCY** (0.9+). The fatigue model ensures checkpoints are written *before* things go wrong — so when a crash happens at 0.85, you have a recent checkpoint from 0.6.

### CLI

```bash
mnemos init                    # Initialize .mnemos/
mnemos status                  # Node counts + fatigue
mnemos fatigue                 # Detailed 4-dimension breakdown
mnemos checkpoint --force      # Write checkpoint now
mnemos resume                  # Output checkpoint for session inject
mnemos add goal "Build auth"   # Create a GoalNode
mnemos bridge-icpg             # Import iCPG ReasonNodes
```

**Overhead:** ~5ms per tool call (fast path), 84KB on disk. Token signal auto-feeds via statusline.

## iCPG — Intent-Augmented Code Property Graph

iCPG tracks *why* code exists, not just what it does. Every code change is linked to a ReasonNode that captures the intent, postconditions, and invariants.

```bash
icpg create "Implement auth" --scope src/auth/   # Create intent
icpg record src/auth/middleware.ts                # Link symbols
icpg query constraints src/auth/middleware.ts     # Get invariants
icpg drift                                        # Check for drift
icpg bootstrap                                    # Infer from git history
```

**Pre-Task Queries** (injected automatically via PreToolUse hook):
- `icpg query context <file>` — What intents touch this file?
- `icpg query constraints <file>` — What invariants must hold?
- `icpg drift file <file>` — Has this file drifted from its intent?

**6-Dimension Drift Detection:** spec drift, decision drift, ownership drift, test drift, usage drift, dependency drift.

## Maggy Dashboard — AI Engineering Command Center (Optional)

Maggy is a full-featured AI engineering command center. Install once, point it at your codebases and issue tracker, and get an interactive dashboard with chat, task triage, competitor intelligence, process analytics, and P2P session sync.

```bash
cd maggy/maggy
./install.sh

# Edit ~/.maggy/config.yaml — set your org, GitHub repos, codebase paths
export GITHUB_TOKEN=ghp_...
export ANTHROPIC_API_KEY=sk-ant-...

python3 -m maggy.main   # Open http://localhost:8080
```

Or from inside any Claude Code session:

```
/maggy-init   # Interactive setup wizard
/maggy        # Launch dashboard
```

### What it does

- **Interactive Chat** — auto-connects to all active Claude/Codex/Kimi sessions, SSE streaming, session continuity via `--resume`, path-based history matching
- **AI-prioritized Tasks** — Claude ranks your open issues by urgency, OKR alignment, and recency. 30-min SQLite cache with stale-cache fallback.
- **One-click Execute** — spawns `claude -p` locally in the right codebase, with iCPG context pre-injected. Runs a TDD pipeline, then commits locally for your review.
- **Competitor Intelligence** — AI-discovered competitors in whatever domain you configure, plus daily news briefing from RSS + Google News.
- **Process Insights** — CLI session history analysis, health signals, self-improvement recommendations, event spine queries.
- **P2P Mesh** — WebSocket-based multi-node session sync and handoff across machines, org-scoped networks, state quarantine.
- **Auto-Bootstrap** — all services seed themselves on startup (history, CIKG, events). No empty tabs.
- **Provider-agnostic** — GitHub Issues, Asana, or (stubbed) Linear. Swap trackers without touching services.

### Dashboard Navigation

Navigation is grouped by intent — 3 groups instead of 9 flat tabs:

| Group | Tabs | Purpose |
|-------|------|---------|
| **Work** | Chat, Tasks, Watching | Do things — chat with Claude, triage issues |
| **Intel** | Competitors, Insights | Learn things — competitor news, session analytics |
| **System** | Budget, Models, Forge, Settings | Configure — spend limits, model routing, MCP gaps |

Chat is the default tab — auto-connects to all running CLI sessions on load.

### Architecture

```
maggy/
├── maggy/                           # optional dashboard — run ./install.sh to enable
│   ├── maggy/                       # Python package (importable as `maggy`)
│   │   ├── main.py                  # FastAPI entry + auto-bootstrap
│   │   ├── config.py                # ~/.maggy/config.yaml loader
│   │   ├── providers/               # GitHub, Asana, Linear (stub)
│   │   ├── services/                # chat, inbox, competitor, executor, activity
│   │   ├── api/                     # REST endpoints (chat, mesh, process, etc.)
│   │   ├── mesh/                    # P2P networking (discovery, sync, WebSocket)
│   │   ├── process/                 # Process intelligence (patterns, signals, router)
│   │   ├── history/                 # CLI session history parsers (Claude, Codex, Kimi)
│   │   ├── improve/                 # Self-improvement (signals, analyzer)
│   │   ├── cikg/                    # Code Intelligence Knowledge Graph
│   │   ├── engram/                  # Memory entries (write/query/expire)
│   │   ├── event_spine/             # Structured event emission + querying
│   │   ├── forge/                   # MCP capability gap detection
│   │   ├── heartbeat/               # Scheduled jobs (history, engram, mesh sync)
│   │   └── static/                  # Dashboard (Tailwind + vanilla JS, no build step)
│   ├── tests/                       # 468 tests
│   └── install.sh                   # one-line install
├── commands/maggy.md                # /maggy command
├── commands/maggy-init.md           # /maggy-init wizard
└── skills/maggy/SKILL.md            # skill reference
```

### Config-driven, no hardcoded anything

One `~/.maggy/config.yaml` drives everything — org name, domain, repos, codebase paths, competitor categories. No hardcoded board IDs or team lists.

```yaml
org: { name: "Acme Corp", domain: "fintech" }
issue_tracker:
  provider: "github"           # or "asana"
  github:
    org: "acmecorp"
    repos: ["acmecorp/api", "acmecorp/web"]
codebases:
  - { path: "~/dev/acmecorp/api", key: "api" }
  - { path: "~/dev/acmecorp/web", key: "web" }
competitors:
  categories: ["fintech", "embedded-finance"]
```

### Safety model

Execute and Chat both run Claude Code with `--dangerously-skip-permissions` so subprocesses aren't blocked waiting on approval prompts with no terminal attached. Mitigations in place:

- `working_dir` and `project_path` are **validated against configured codebase roots** — both Execute and Chat reject arbitrary filesystem paths
- **Per-session streaming lock** — `asyncio.Lock` prevents concurrent subprocess spawning via the Chat API
- Dashboard **refuses to boot** if `auth_mode="local"` is combined with a non-loopback host (would expose Execute on the local network)
- RSS URLs **SSRF-validated** before fetching (blocks loopback, private, link-local)
- `CLAUDECODE` env var stripped from subprocesses to allow nested Claude sessions
- **No-cache static middleware** — `Cache-Control: no-store` prevents stale JS

See `maggy/README.md` for the full hardening notes.

### P2P Mesh Network

Multi-node session sync and handoff across machines. Each Maggy instance is a mesh peer that can share memory, discover other nodes, and synchronize state.

| Component | What it does |
|-----------|-------------|
| **Peer Discovery** | Registry of known peers with address, org, last-seen tracking |
| **Git Discovery** | Auto-discovers peers from shared git remotes across configured codebases |
| **WebSocket Server/Client** | Bidirectional real-time communication between peers |
| **Mesh Protocol** | 7 message types: `hello`, `share`, `request`, `response`, `quarantine`, `promote`, `heartbeat` |
| **Quarantine** | Untrusted data from peers is quarantined until reviewed — prevents poisoned memory injection |
| **Org Scoping** | Peers are filtered by org key so only your team's nodes connect |
| **Provenance** | Tracks origin of shared data (which peer, when, confidence level) |

Configure in `~/.maggy/config.yaml`:

```yaml
mesh:
  enabled: true
  port: 8080
  orgs: ["my-team"]
  git_discovery: true
  share_interval: 600
```

### Engram Memory

Persistent memory system with typed records, namespace isolation, and multi-path retrieval. Engrams survive across sessions — they're stored in SQLite, not in-context.

| Field | Purpose |
|-------|---------|
| `memory_type` | `fact`, `decision`, `code_ref`, `handoff` |
| `origin` | `explicit` (user-created), `inferred` (AI-derived), `mesh` (from peer) |
| `validity` | `active`, `superseded`, `expired` |
| `confidence` | 0.0-1.0 trust score |
| `namespace` | Project/session scoping |
| `expires_at` | Optional TTL for auto-expiry |

Retrieval paths: by namespace, by type, by keyword, by tag, or most recent. The heartbeat scheduler runs periodic expiry to clean stale entries.

### Event Spine

Structured event emission and querying across all Maggy services. Every significant action (task executed, competitor discovered, history analyzed, self-improvement run) emits a typed event with a standard header.

Events are stored in SQLite and queryable via the `/api/events` endpoint. The Insights tab visualizes event streams for debugging and auditing service behavior.

### Other Subsystems

| Subsystem | Purpose |
|-----------|---------|
| **CIKG** | Code Intelligence Knowledge Graph — codebase nodes, technology detection, landscape queries |
| **Forge** | MCP capability gap detection — scans filesystem patterns, suggests MCP tools to fill gaps |
| **History** | CLI session history parsers for Claude, Codex, and Kimi — topic extraction, session patterns |
| **Improve** | Self-improvement — signal collection, health scoring, actionable recommendations |
| **Budget** | Daily token spend limits with per-provider breakdown |
| **Model Router** | Reward-based heatmap for model selection by task type |
| **Heartbeat** | Scheduled jobs — history refresh, engram expiry, self-improvement, mesh sync |

## Pre-configured Permissions

`.claude/settings.json` includes permission rules so users don't get pestered for routine operations:

```json
{
  "permissions": {
    "allow": [
      "Bash(npm test *)",
      "Bash(npm run lint *)",
      "Bash(pytest *)",
      "Bash(git status *)",
      "Bash(gh pr *)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(git push --force *)",
      "Write(.env)",
      "Write(.env.*)"
    ]
  }
}
```

## CLAUDE.local.md (Private Overrides)

Each developer gets a `.gitignore`'d `CLAUDE.local.md` for personal preferences:

```markdown
# My Preferences
- I prefer verbose explanations
- My local DB runs on port 5433
- Use pnpm instead of npm
```

This loads at **higher priority** than project `CLAUDE.md` — personal preferences override team config without polluting the repo.

## Agent Teams

Every project runs as a coordinated team of AI agents with **proper frontmatter definitions**:

```yaml
# .claude/agents/team-lead.md
---
name: team-lead
description: Orchestrates the agent team
model: sonnet
tools: [Read, Glob, Grep, TaskCreate, TaskUpdate, TaskList, TaskGet, SendMessage]
disallowedTools: [Write, Edit, Bash]
maxTurns: 50
effort: high
---
```

**Default Team:**

| Agent | Role | Can Edit Code? |
|-------|------|----------------|
| **Team Lead** | Orchestrates, assigns tasks (never writes code) | No |
| **Quality Agent** | Verifies RED/GREEN TDD phases, coverage >= 80% | No |
| **Security Agent** | OWASP scanning, secrets detection, dependency audit | No |
| **Code Review Agent** | Multi-engine reviews | No |
| **Merger Agent** | Creates feature branches and PRs via `gh` CLI | No |
| **Feature Agent (x N)** | One per feature, follows strict TDD pipeline | Yes |

**Pipeline (enforced by task dependencies):**

```
Spec > Spec Review > Tests > RED Verify > Implement >
GREEN Verify > Validate > Code Review > Security > Branch+PR
```

```bash
# Auto-spawned by /initialize-project, or manually:
/spawn-team
```

## What Gets Created

```
your-project/
├── .claude/
│   ├── agents/               # Agent definitions with frontmatter
│   │   ├── team-lead.md      # name, model, tools, disallowedTools, maxTurns
│   │   ├── quality.md
│   │   ├── security.md
│   │   ├── code-review.md
│   │   ├── merger.md
│   │   └── feature.md
│   ├── rules/                # Conditional rules (paths: frontmatter)
│   │   ├── quality-gates.md  # Always active
│   │   ├── tdd-workflow.md   # Always active
│   │   ├── security.md       # Always active
│   │   ├── react.md          # Active on .tsx/.jsx files
│   │   ├── typescript.md     # Active on .ts/.tsx files
│   │   ├── python.md         # Active on .py files
│   │   └── nodejs-backend.md # Active on api/routes/server files
│   ├── skills/               # Skills loaded via @include
│   │   ├── base/SKILL.md
│   │   ├── iterative-development/SKILL.md
│   │   ├── security/SKILL.md
│   │   ├── mnemos/SKILL.md
│   │   ├── cross-agent-delegation/SKILL.md
│   │   └── [framework]/SKILL.md
│   └── settings.json         # Permissions + hooks + statusline
├── scripts/
│   ├── tdd-loop-check.sh     # Stop hook script for TDD loops
│   ├── icpg/                 # Intent-Augmented Code Property Graph
│   └── mnemos/               # Task-Scoped Memory Lifecycle
├── .mnemos/                  # Mnemos state (auto-created, gitignored)
│   ├── mnemo.db              # SQLite MnemoGraph
│   ├── fatigue.json          # Live fatigue signal
│   ├── signals.jsonl         # Behavioral signal log
│   └── checkpoint-latest.json # Most recent checkpoint
├── .github/workflows/
│   ├── quality.yml
│   └── security.yml
├── _project_specs/
│   ├── features/
│   └── todos/
├── CLAUDE.md                 # @include directives, project context
└── CLAUDE.local.md           # Private developer overrides (gitignored)
```

## Commit Hygiene

```
┌─────────────────────────────────────────────────────────────┐
│  COMMIT SIZE THRESHOLDS                                     │
├─────────────────────────────────────────────────────────────┤
│  OK:     ≤ 5 files,  ≤ 200 lines                           │
│  WARN:   6-10 files, 201-400 lines  → "Commit soon"        │
│  STOP:   > 10 files, > 400 lines    → "Commit NOW"         │
└─────────────────────────────────────────────────────────────┘
```

## Skills Included (62 Skills)

### Core Skills
| Skill | Purpose |
|-------|---------|
| `base.md` | Universal patterns, constraints, TDD workflow, atomic todos |
| `iterative-development.md` | TDD loops via Stop hooks (replaces Ralph Wiggum) |
| `mnemos.md` | Task-scoped memory lifecycle — fatigue monitoring, checkpoints, typed compaction |
| `icpg.md` | Intent-augmented code property graph — track why code exists, detect drift |
| `code-review.md` | Mandatory code reviews - Claude, Codex, Gemini, or multi-engine |
| `codex-review.md` | OpenAI Codex CLI code review |
| `gemini-review.md` | Google Gemini CLI code review, 1M token context |
| `workspace.md` | Multi-repo workspace awareness, contract tracking |
| `commit-hygiene.md` | Atomic commits, PR size limits |
| `code-deduplication.md` | Prevent semantic duplication with capability index |
| `agent-teams.md` | Agent team workflow with proper frontmatter definitions |
| `ticket-craft.md` | AI-native ticket writing optimized for Claude Code |
| `maggy.md` | Optional local AI command center — AI-prioritized inbox, one-click TDD execute, competitor intelligence. See the [Maggy section](#maggy--ai-engineering-command-center-optional) for the full docs |
| `team-coordination.md` | Multi-person projects, shared state, handoffs |
| `code-graph.md` | Persistent code graph via MCP |
| `cpg-analysis.md` | Deep CPG analysis - Joern + CodeQL |
| `security.md` | OWASP patterns, secrets management |
| `credentials.md` | Centralized API key management |
| `session-management.md` | Context preservation, resumability |
| `project-tooling.md` | gh, vercel, supabase CLI + deployment |
| `existing-repo.md` | Analyze existing repos, setup guardrails |
| `cross-agent-delegation.md` | Cross-agent task routing, Codex auto-review, Kimi delegation |
| `polyphony.md` | Multi-agent orchestration with container-isolated workspaces |

### Language & Framework Skills
| Skill | Purpose |
|-------|---------|
| `python.md` | Python + ruff + mypy + pytest |
| `typescript.md` | TypeScript strict + eslint + jest |
| `nodejs-backend.md` | Express/Fastify patterns, repositories |
| `react-web.md` | React + hooks + React Query + Zustand |
| `react-native.md` | Mobile patterns, platform-specific code |
| `android-java.md` | Android Java with MVVM, ViewBinding, Espresso |
| `android-kotlin.md` | Android Kotlin with Coroutines, Jetpack Compose, Hilt |
| `flutter.md` | Flutter with Riverpod, Freezed, go_router |

### UI Skills
| Skill | Purpose |
|-------|---------|
| `ui-web.md` | Web UI - Tailwind, dark mode, accessibility |
| `ui-mobile.md` | Mobile UI - React Native, iOS/Android patterns |
| `ui-testing.md` | Visual testing |
| `playwright-testing.md` | E2E testing - Playwright, Page Objects |
| `user-journeys.md` | User experience flows |
| `pwa-development.md` | Progressive Web Apps - service workers, offline |

### Database & Backend Skills
| Skill | Purpose |
|-------|---------|
| `database-schema.md` | Schema awareness |
| `supabase.md` | Core Supabase CLI, migrations, RLS |
| `supabase-nextjs.md` | Next.js + Supabase + Drizzle ORM |
| `supabase-python.md` | FastAPI + Supabase |
| `supabase-node.md` | Express/Hono + Supabase |
| `firebase.md` | Firebase Firestore, Auth, Storage |
| `cloudflare-d1.md` | Cloudflare D1 SQLite with Workers |
| `aws-dynamodb.md` | AWS DynamoDB single-table design |
| `aws-aurora.md` | AWS Aurora Serverless v2 |
| `azure-cosmosdb.md` | Azure Cosmos DB |

### AI & Agentic Skills
| Skill | Purpose |
|-------|---------|
| `agentic-development.md` | Build AI agents |
| `llm-patterns.md` | AI-first apps, LLM testing |
| `ai-models.md` | Latest models reference |

### Content, Integration & Other Skills
| Skill | Purpose |
|-------|---------|
| `aeo-optimization.md` | AI Engine Optimization |
| `web-content.md` | SEO + AI discovery |
| `site-architecture.md` | Technical SEO |
| `web-payments.md` | Stripe Checkout, subscriptions |
| `reddit-api.md` | Reddit API |
| `reddit-ads.md` | Reddit Ads API + agentic optimization |
| `ms-teams-apps.md` | Microsoft Teams bots |
| `posthog-analytics.md` | PostHog analytics |
| `shopify-apps.md` | Shopify app development |
| `woocommerce.md` | WooCommerce REST API |
| `medusa.md` | Medusa headless commerce |
| `klaviyo.md` | Klaviyo email/SMS marketing |

## Usage Patterns

### New Project
```bash
mkdir my-new-app && cd my-new-app
claude
> /initialize-project
```

### Existing Project
```bash
cd my-existing-app
claude
> /initialize-project
# Auto-detects existing code → runs analysis first
```

### Update Skills Globally
```bash
cd "$(cat ~/.claude/.bootstrap-dir)"
git pull
./install.sh
```

## Prerequisites

```bash
# GitHub CLI
brew install gh && gh auth login

# Vercel CLI (optional)
npm i -g vercel && vercel login

# Supabase CLI (optional)
brew install supabase/tap/supabase && supabase login
```

## Evolution

| Version | Date | What Changed |
|---------|------|-------------|
| **v1.0** | Jan 2026 | Initial release — 30+ skills, `/initialize-project`, TDD via Ralph Wiggum loops, Python/TypeScript/React support |
| **v2.0** | Jan 2026 | Skills restructured (`folder/SKILL.md`), YAML frontmatter, validation tests, 60+ skills across 10 categories |
| **v3.0** | Mar 2026 | **Real Claude Code infrastructure** — Ralph Wiggum replaced with Stop hooks, `@include` directives, conditional rules (`paths:` frontmatter), agent teams via `.claude/agents/`, pre-configured permissions |
| **v3.3** | Apr 2026 | Mnemos (task-scoped memory), iCPG (intent tracking + drift detection), Maggy dashboard MVP (inbox, execute, competitors) |
| **v3.5** | Apr 2026 | PreCompact hook for smarter compaction, fatigue model (4 dimensions), hook error resilience |
| **v3.6** | May 2026 | Cross-tool compatibility (Claude + Kimi + Codex), cross-agent intelligence (Codex auto-review, Kimi delegation), complexity-based routing |
| **v4.0** | May 2026 | **Polyphony** — multi-agent orchestration with container isolation, 5-dimension complexity scoring, Docker runtime, 3 agent adapters, state machine task lifecycle |
| **v5.0** | May 2026 | **Autonomous command center** — Interactive Chat with `--resume` takeover, P2P Mesh networking, process intelligence, auto-bootstrap, grouped UI (Work/Intel/System), 468 tests, security hardening (path validation, streaming lock) |

### Where we started vs where we are

| Area | v1 (Jan 2026) | v5 (May 2026) |
|------|---------------|---------------|
| **Scope** | Claude Code project setup tool | Autonomous AI engineering platform |
| **TDD** | Ralph Wiggum plugin (didn't exist) | Real Stop hooks with iteration tracking |
| **Skills** | 30 flat `.md` files | 62 skills with `@include`, conditional rules |
| **Memory** | None (lost on compaction) | Mnemos typed graph + fatigue model |
| **Intent** | None | iCPG with 6-dimension drift detection |
| **Agents** | Single Claude session | Polyphony containers + cross-agent delegation |
| **Models** | Claude only | Claude + Codex + Kimi + complexity routing |
| **Dashboard** | None | Maggy — chat, tasks, competitors, insights, mesh |
| **Networking** | None | P2P Mesh (WebSocket sync, org-scoped) |
| **Tests** | Shell validation script | 468 pytest tests + integration suite |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

MIT - See [LICENSE](LICENSE)

## Credits

Built on learnings from 100+ projects across customer experience management, agentic AI platforms, mobile apps, and full-stack web applications.

---

**Need help scaling AI in your org?** [Claude Code & MCP experts](https://leanai.ventures/aiops/claude)
