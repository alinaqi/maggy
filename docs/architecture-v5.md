# Claude Bootstrap v5 Architecture — Multi-Project, Multi-Model Command Center

## 1. Executive Summary

v5 transforms claude-bootstrap from a single-project, single-model toolkit into a **multi-project, multi-model orchestration platform**. Pi replaces per-CLI adapters as the universal agent harness. Maggy becomes the central web dashboard. Token budgets are managed dynamically across providers. New features are validated against the competitive intelligence graph before engineering begins.

---

## 2. What Changed: Before and After

### v3.x (Single-Model, Single-Project)

```
User → Claude Code → single project → single model
         │
         ├── CLAUDE.md (project config)
         ├── skills/ (TDD, security, etc.)
         ├── iCPG (blast radius, drift)
         ├── Mnemos (memory, fatigue)
         └── hooks (PreToolUse, Stop, etc.)
```

- One project at a time
- One model (Claude) for everything
- When Claude tokens ran out, work stopped
- Agents shared a filesystem (conflict-prone)
- No market validation for new features

### v4.0 (Container Isolation, Cross-Agent)

```
User → Claude Code → /spawn-team → Polyphony containers
         │                            ├── Container 1 (claude CLI)
         ├── cross-agent-delegation   ├── Container 2 (codex CLI)
         │   (complexity scoring)     └── Container 3 (kimi CLI)
         ├── iCPG + Mnemos
         └── 3 separate CLI adapters
```

- Container isolation per agent (own git clone + branch)
- Cross-agent delegation via complexity scoring
- Still one project at a time
- Still separate CLI tools (claude, codex, kimi)
- Token exhaustion on one provider = manual switch

### v5.0 (Multi-Project, Multi-Model, Market-Validated)

```
User → Maggy Web Dashboard → multiple projects → multiple models
         │                       │
         │   ┌───────────────────┼───────────────────┐
         │   │ Project A         │ Project B          │
         │   │ zensurveys        │ chief-of-staff     │
         │   │                   │                    │
         │   │  ┌─Pi agent─┐    │  ┌─Pi agent─┐     │
         │   │  │ claude   │    │  │ gpt-4o   │     │
         │   │  │ → gpt-4o │    │  │ → gemini │     │
         │   │  │ → gemini │    │  │ → qwen   │     │
         │   │  └──────────┘    │  └──────────┘     │
         │   └───────────────────┼───────────────────┘
         │                       │
         ├── codebase-memory-mcp (structural graph — 36 projects)
         ├── CIKG (market graph) │ iCPG (intent graph, layers on code graph)
         ├── Mnemos (cross-model fatigue)
         └── Token Budget Manager (auto-rotate)
```

---

## 3. Core Components

### 3.1 Pi — Universal Agent Harness

**Replaces:** `ClaudeAdapter`, `CodexAdapter`, `KimiAdapter`

Pi is an open-source (MIT) terminal coding agent that supports 20+ model providers through a single interface. It runs in three modes:

| Mode | Use Case |
|------|----------|
| **Interactive** | Human at terminal |
| **RPC** | Headless JSONL over stdin/stdout — for container agents |
| **SDK** | Embedded in Maggy's orchestrator |

**Provider support:**

| Tier | Providers | Auth |
|------|-----------|------|
| Subscription | Claude Pro/Max, ChatGPT Plus/Pro, GitHub Copilot | OAuth |
| API Key | Anthropic, OpenAI, Google, DeepSeek, Mistral, Groq, xAI | Env var |
| Cloud | Azure OpenAI, Amazon Bedrock, Cloudflare Workers | Platform |
| Local | Ollama (Qwen, Llama, etc.) | None |

**Key capability:** Runtime model switching via RPC without restarting:
```json
{"command": "set_model", "provider": "openai", "model": "gpt-4o"}
```

### 3.2 Maggy v2 — Multi-Project Command Center

**Extends:** Maggy v1 (single-project inbox + execute)

Maggy v2 is a web dashboard (FastAPI + React) that orchestrates work across multiple GitHub repos from a single browser tab.

```
┌─────────────────────────────────────────────────────────────┐
│  MAGGY v2 — Web Dashboard                                    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  PROJECT REGISTRY (~/.maggy/projects.yaml)           │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│  │  │ Project │ │ Project │ │ Project │ │ Project │   │   │
│  │  │ A       │ │ B       │ │ C       │ │ D       │   │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │   │
│  └───────┼───────────┼───────────┼───────────┼─────────┘   │
│          │           │           │           │              │
│  ┌───────▼───────────▼───────────▼───────────▼─────────┐   │
│  │  ORCHESTRATOR                                        │   │
│  │  ┌────────────┐ ┌─────────────┐ ┌────────────────┐  │   │
│  │  │ Planning   │ │ Decision    │ │ Execution      │  │   │
│  │  │ Layer      │ │ Layer       │ │ Layer          │  │   │
│  │  │            │ │             │ │                │  │   │
│  │  │ Claude     │ │ iCPG blast  │ │ Pi agents in   │  │   │
│  │  │ plans      │ │ radius →    │ │ Polyphony      │  │   │
│  │  │ Codex      │ │ model tier  │ │ containers     │  │   │
│  │  │ counter-   │ │             │ │                │  │   │
│  │  │ checks     │ │ CIKG market │ │ Token budget   │  │   │
│  │  │            │ │ validation  │ │ auto-rotation  │  │   │
│  │  └────────────┘ └─────────────┘ └────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  CODE INTELLIGENCE (codebase-memory-mcp)             │   │
│  │  36 projects indexed │ 700K+ nodes │ 1.4M+ edges    │   │
│  │  Structural graph powering iCPG, blast radius,       │   │
│  │  cross-project deps, agent context                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  DEPLOY LAYER                                        │   │
│  │  4 isolated browser containers (Playwright)          │   │
│  │  Each with its own Vercel auth session               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**New capabilities over v1:**
- Multi-project view (registry of repos + branches)
- Cross-project ticket triage
- Token budget dashboard (usage per model per project)
- Deploy status per project (isolated Vercel sessions)

### 3.3 Token Budget Manager

**New component.** Manages model selection based on blast radius and token availability.

#### Model Tiering by Composite Risk Score

Model selection uses iCPG's **5-dimension complexity scoring**, not just file count. Each dimension is scored 0-2, total 0-10:

| Dimension | What It Measures | Examples |
|-----------|-----------------|----------|
| **Cyclomatic** | Control flow complexity of touched code | Nested conditionals, state machines |
| **Fan-out** | How many other modules depend on the change | Shared utilities, API contracts |
| **Security** | Whether auth, crypto, permissions, or PII are involved | Auth policy, token validation |
| **Concurrency** | Race conditions, locks, async coordination | Queue workers, websocket handlers |
| **Domain** | Business logic criticality | Pricing, billing, compliance |

Plus 6-dimension drift detection (spec, decision, ownership, test, usage, dependency) and constraint checking from active ReasonNodes.

This means a one-file auth policy change scores high (security=2, domain=2) while a five-file CSS refactor scores low (cyclomatic=0, fan_out=1). The routing is risk-aware, not file-count-aware.

```
iCPG composite risk score → model tier

┌─────────────┬──────────────────────┬─────────────────────────┐
│ Score        │ Model Tier           │ Rationale               │
├─────────────┼──────────────────────┼─────────────────────────┤
│ 0-3 (low)   │ Qwen local / DeepSeek│ Bounded scope, no       │
│             │ via Ollama            │ security/concurrency/   │
│             │                      │ domain risk             │
├─────────────┼──────────────────────┼─────────────────────────┤
│ 4-6 (medium)│ Kimi / Gemini Flash  │ Real risk but bounded;  │
│             │                      │ + high-tier post-review │
│             │                      │ on output (catch subtle │
│             │                      │ bugs cheap models miss) │
├─────────────┼──────────────────────┼─────────────────────────┤
│ 7-10 (high) │ Claude / GPT-4o      │ Full context needed —   │
│             │                      │ cross-cutting, security,│
│             │                      │ concurrency, or domain  │
│             │                      │ critical changes        │
└─────────────┴──────────────────────┴─────────────────────────┘
```

**Dimension overrides:** Regardless of total score, if `security >= 2` or `concurrency >= 2`, the task is always routed to the high tier. These dimensions are too dangerous for cheap models.

#### Low-Tier Output Verification

When a task is handled by a cheap/local model (score 0-6), its output goes through additional verification before landing:

| Gate | What It Catches |
|------|----------------|
| iCPG drift check | Scope drift, constraint violations, invariant breakage |
| iCPG constraint assertions | Postconditions from ReasonNodes evaluated against output |
| High-tier spot review | Claude/GPT-4o reviews the diff (cheaper than writing it) |
| Static analysis | Linter + type checker catch mechanical errors |

This prevents the failure class Codex identified: code that passes tests but has subtle logical regressions.

#### Fallback Chain

When the primary model hits quota, the budget manager rotates. Model switching is an **explicit handoff with verification**, not a silent swap:

1. Current model hits quota or rate limit
2. Mnemos writes checkpoint with full execution state
3. Pi switches to next model via RPC `set_model`
4. Checkpoint is re-injected as structured context
5. New model verifies it understands the task before continuing
6. If verification fails, escalate to next tier (don't retry on weaker model)

```
Claude (quota hit) → checkpoint + handoff
  → GPT-4o (quota hit) → checkpoint + handoff
    → Gemini 2.5 Pro (quota hit) → checkpoint + handoff
      → Kimi (quota hit) → checkpoint + handoff
        → DeepSeek (quota hit) → checkpoint + handoff
          → Qwen local (unlimited, always available)
```

#### Budget Tracking

```yaml
# ~/.maggy/token-budget.yaml
providers:
  anthropic:
    daily_limit_usd: 50.00
    used_today_usd: 32.15
    model_preference: claude-sonnet-4-20250514
  openai:
    daily_limit_usd: 30.00
    used_today_usd: 5.20
    model_preference: gpt-4o
  local:
    daily_limit_usd: 0  # free
    model_preference: qwen2.5-coder:32b
    ollama_endpoint: http://localhost:11434
```

### 3.4 Planning Layer — Dual-Model Review

Every plan goes through a two-model review before execution:

```
Feature Request / Ticket
        │
        ▼
┌─────────────────┐
│ Claude Plans     │  Primary model creates architecture plan
│ (full context)   │  with file list, approach, risks
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Codex Counter-   │  Second model independently reviews:
│ Checks           │  - Missing edge cases?
│ (independent)    │  - Over-engineering?
│                  │  - Security gaps?
│                  │  - Simpler approach?
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Diff View        │  Maggy shows both perspectives
│ in Maggy UI      │  User approves/resolves conflicts
└────────┬────────┘
         │
         ▼
    Execution begins
```

### 3.5 Decision Layer — iCPG + CIKG

Two graphs feed the orchestrator's decisions:

#### iCPG (Code Graph) — "Should we change this?"

Per-project, SQLite-backed. Layers intent and constraints on top of the structural graph from **codebase-memory-mcp** (Section 3.8). Answers:

| Query | What It Returns |
|-------|----------------|
| `icpg query blast <id>` | Files affected, downstream dependencies |
| `icpg query risk <symbol>` | Drift history, ownership changes, fragility |
| `icpg query constraints <file>` | Invariants that must be preserved |
| `icpg drift check` | 6-dimension drift across spec, decision, ownership, test, usage, dependency |

The blast radius score (0-10) determines:
- Which model tier handles the task
- How deep the architecture review goes
- Whether dual-model planning is required

#### CIKG (Competitive Intelligence Knowledge Graph) — "Should we build this?"

Supabase-backed. Node types: `competitor`, `feature`, `market_segment`, `technology`, `trend`, `product`.

Edge types: `has_feature`, `competes_with`, `targets_market`, `uses_technology`, `protaige_has`, `protaige_lacks`, `threatens`.

Used for **new feature validation** before engineering begins:

```
New Feature Idea
       │
       ▼
┌────────────────────┐
│ CIKG: find_gaps()  │  Who has this? Who lacks it?
│ compare_entities() │  Competitive advantage or table stakes?
│ get_landscape()    │  Market trend alignment?
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Market Score        │
│                    │
│ gap_count: 3       │  3 competitors lack this → opportunity
│ threat_level: high │  2 competitors actively building → urgent
│ trend_align: yes   │  Aligns with "AI voice" trend → proceed
└────────┬───────────┘
         │
         ▼
  Requirements validated → proceed to iCPG blast radius
```

### 3.6 Execution Layer — Polyphony + Pi

Updated container architecture. Each feature agent runs Pi in RPC mode inside a Polyphony container:

```
┌──────────────────────────────────────────────────────┐
│ Polyphony Container (per feature)                     │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Pi Agent (RPC mode over stdin/stdout)           │ │
│  │                                                  │ │
│  │  Current model: claude-sonnet-4-20250514         │ │
│  │  Fallback chain: gpt-4o → gemini → kimi → qwen  │ │
│  │                                                  │ │
│  │  Tools: read, write, edit, bash                  │ │
│  │  Extensions: skills, hooks, MCP servers          │ │
│  └──────────────────────────────┬──────────────────┘ │
│                                 │                     │
│  ┌──────────┐  ┌────────────┐  │  ┌──────────────┐  │
│  │ Git clone│  │ .mnemos/   │  │  │ .icpg/       │  │
│  │ own      │  │ fatigue    │  │  │ blast radius │  │
│  │ branch   │  │ checkpoint │  │  │ constraints  │  │
│  └──────────┘  └────────────┘  │  └──────────────┘  │
│                                │                     │
│  ┌─────────────────────────────▼──────────────────┐  │
│  │  RPC Bridge (Maggy ↔ Pi)                       │  │
│  │  • Send prompts                                │  │
│  │  • Receive streaming events                    │  │
│  │  • Switch models on quota hit                  │  │
│  │  • Steer/follow-up mid-task                    │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

**Coordination model (hybrid — option 2):**

Claude Code's native Task tool spawns agents that keep full team coordination (SendMessage, TaskList, UI visibility). Each agent controls a Pi instance inside a Polyphony container via RPC. The agent has Claude's brain for coordination but Pi's body for execution.

**Why this is not a split-brain problem:**

Codex's review flagged this as a "split-brain control model" — two agents maintaining separate state. This concern is addressed by Mnemos, which serves as a **shared memory layer that both sides can read**:

- **Mnemos checkpoint** persists goal, constraints, progress, and working state to disk (`.mnemos/`)
- **iCPG state** persists intent, constraints, and drift to disk (`.icpg/`)
- **Signal log** (`.mnemos/signals.jsonl`) persists behavioral signals across model switches
- All three are inside the container volume — they survive model swaps

The coordination agent (Claude Task tool) handles team communication. The execution agent (Pi) handles code work. The shared disk state (Mnemos + iCPG) is the single source of truth. There's no split brain because there's no duplicated state — each layer owns a distinct concern with shared persistence.

```
Claude Code Task tool agent (coordination — messaging, tasks, UI)
    │
    ├── SendMessage to team lead ✓
    ├── TaskUpdate progress ✓
    ├── Visible in tmux/iTerm ✓
    │
    └── Executes code work via:
        docker exec polyphony-feature-X \
            pi --mode rpc --provider anthropic
        │
        ├── stdin: {"command": "prompt", "content": "implement auth"}
        ├── stdout: streaming events (text, tool calls, completion)
        ├── stdin: {"command": "set_model", ...} when quota hits
        │
        └── Shared persistence (inside container volume):
            ├── .mnemos/checkpoint-latest.json  ← goal, constraints, progress
            ├── .mnemos/signals.jsonl           ← behavioral signals
            ├── .mnemos/fatigue.json            ← model-normalized fatigue
            └── .icpg/reason.db                 ← intent, constraints, drift
```

### 3.7 Deploy Layer — Isolated Vercel Sessions

Four Docker containers, each running a headless browser with its own Vercel auth session:

```
┌────────────────────────────┐
│ vercel-session-A           │
│ Playwright + Chrome        │
│ Auth: vercel.com (session) │
│ Project: zensurveys-backend│
│ No local `vercel login`    │
├────────────────────────────┤
│ vercel-session-B           │
│ Own Chrome profile         │
│ Project: zensurveys-fe     │
├────────────────────────────┤
│ vercel-session-C           │
│ Own Chrome profile         │
│ Project: chief-of-staff    │
├────────────────────────────┤
│ vercel-session-D           │
│ Own Chrome profile         │
│ Project: rodcast           │
└────────────────────────────┘
```

Each container persists its Chrome profile to a Docker volume. No local directory conflicts. Deploys are triggered from Maggy's web UI or via git push (Vercel auto-deploy).

### 3.8 Code Intelligence Layer — codebase-memory-mcp

**Foundation layer.** Every component above — iCPG, blast radius scoring, Maggy's orchestrator, Pi agents — depends on a structural understanding of the code. codebase-memory-mcp is the AST-based knowledge graph that provides it.

```
┌──────────────────────────────────────────────────────────────┐
│  codebase-memory-mcp                                          │
│  ─────────────────────────────────────────────────────────── │
│                                                               │
│  36 projects indexed │ 14 MCP tools │ 64 languages             │
│  700K+ nodes │ 1.4M+ edges │ auto-updated via file watcher    │
│                                                               │
│  Node Types:                                                  │
│    Function, Method, Class, Variable, Route,                  │
│    File, Module, Folder, Section, Project                     │
│                                                               │
│  Edge Types:                                                  │
│    CALLS, IMPORTS, USAGE, DEFINES, DEFINES_METHOD,            │
│    TESTS, WRITES, HANDLES, HTTP_CALLS, CONFIGURES,            │
│    SEMANTICALLY_RELATED, SIMILAR_TO, CONTAINS_*               │
│                                                               │
│  Search Modes:                                                │
│    BM25 full-text │ regex pattern │ semantic vector             │
│                                                               │
│  Trace Modes:                                                 │
│    calls (callers/callees) │ data_flow (value propagation)     │
│    cross_service (HTTP/async through Routes)                   │
└──────────────────────────────────────────────────────────────┘
```

#### How Each Component Uses It

| Component | Graph Queries | Purpose |
|-----------|--------------|---------|
| **iCPG blast radius** | `trace_path(fn, mode=calls, risk_labels=true)` | Fan-out scoring — how many callers/callees, at what hop distance |
| **iCPG drift** | `detect_changes` + `query_graph` | Detect which functions changed, trace impact to dependents |
| **Token budget routing** | `trace_path` depth + edge count | Feed fan-out dimension of 5-dimension complexity score |
| **Pi agents (pre-task)** | `search_graph` + `get_architecture` | Understand codebase before making changes — no blind edits |
| **Pi agents (post-task)** | `detect_changes` | Verify scope of changes matches intent |
| **Maggy orchestrator** | `search_graph` across projects | Map ticket descriptions → relevant code across all repos |
| **Dual-model planning** | `get_architecture` + `trace_path` | Give both Claude and Codex the same structural context |
| **Reward registry** | `detect_changes` | Measure actual blast radius of completed work for reward signals |
| **Cross-project deps** | `query_graph` with HTTP_CALLS/IMPORTS | If zensurveys-backend changes an API route, trace consumers in frontend |

#### Multi-Project Graph Topology

Each project has its own indexed graph. Maggy queries across them:

```
┌─────────────────────────────────────────────────────────────┐
│  codebase-memory-mcp — Cross-Project Graph                    │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │ zensurveys       │  │ zensurveys-fe    │                  │
│  │ 7,644 nodes      │  │ 11,168 nodes     │                  │
│  │ 25,866 edges     │  │ 16,876 edges     │                  │
│  │                  │  │                  │                  │
│  │ Route: /api/v1/* │──│ HTTP_CALLS: fetch│                  │
│  └──────────────────┘  └──────────────────┘                  │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │ chief-of-staff   │  │ claude-bootstrap │                  │
│  │ 2,687 nodes      │  │ 4,692 nodes      │                  │
│  │ 6,958 edges      │  │ 7,459 edges      │                  │
│  └──────────────────┘  └──────────────────┘                  │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │ protaige-backend │  │ protaige-frontend│                  │
│  │ 26,832 nodes     │  │ 8,630 nodes      │                  │
│  │ 92,174 edges     │  │ 14,539 edges     │                  │
│  └──────────────────┘  └──────────────────┘                  │
│                                                               │
│  + 30 more indexed projects                                   │
└─────────────────────────────────────────────────────────────┘
```

#### Integration with iCPG

iCPG and codebase-memory-mcp are **complementary, not redundant**:

| Layer | What It Knows | Storage |
|-------|--------------|---------|
| **codebase-memory-mcp** | Structure — what calls what, who imports whom, where routes go | `.code-graph/` (AST-derived) |
| **iCPG** | Intent — WHY code exists, what constraints it must obey, what decisions shaped it | `.icpg/reason.db` (human/AI-derived) |

```
codebase-memory-mcp (structural)     iCPG (intentional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     ━━━━━━━━━━━━━━━━━━━━
Function: handleAuth()               ReasonNode: "handles OAuth"
  CALLS → validateToken()              Constraint: "must check exp"
  CALLS → refreshSession()             Decision: "chose PKCE over implicit"
  USAGE → from 14 callers               Drift: "spec says mTLS, code uses JWT"
  Route: POST /api/auth/login
                                      5-dimension score: 8/10
trace_path → 3-hop blast radius         (security=2, domain=2, fan_out=2)
```

The structural graph provides the "what and where." iCPG provides the "why and what-must-hold." Together they give the token budget manager a complete risk picture.

#### Freshness Guarantees

```
┌────────────────┬──────────────────────────────────────────┐
│ Layer           │ How It Stays Fresh                        │
├────────────────┼──────────────────────────────────────────┤
│ File watcher   │ Re-indexes changed files on save (~10ms) │
│ Auto-index     │ Ensures currency on Claude Code startup  │
│ Post-commit    │ git hook triggers incremental re-index   │
│ detect_changes │ Diff-aware — shows what changed since    │
│                │ last index, not full re-scan              │
└────────────────┴──────────────────────────────────────────┘
```

No manual re-indexing needed for normal development. Only `index_repository` after major restructures (branch switches with large diffs, directory renames).

---

## 4. Mnemos in a Multi-Model World

### The Problem

Mnemos v1 tracks fatigue for a single Claude Code session. In v5, a task might start on Claude, switch to GPT-4o mid-session, then fall back to Qwen. Each model has different:

- Context window sizes (200K Claude vs 128K GPT-4o vs 32K Qwen local)
- Compaction behavior
- Tool call patterns

### The Solution: Model-Aware Fatigue

Extend the 4-dimension fatigue model with model-relative normalization:

```
┌──────────────────────────────────────────────────────┐
│ Mnemos v2 — Cross-Model Fatigue                       │
│                                                       │
│ Current model: gpt-4o (128K context)                  │
│ Previous model: claude (200K context)                 │
│ Model switches this session: 1                        │
│                                                       │
│ Fatigue dimensions (model-normalized):                │
│                                                       │
│  Token utilization: 0.65                              │
│    → 83K / 128K (gpt-4o window, not claude's 200K)   │
│                                                       │
│  Scope scatter: 0.30                                  │
│    → Carried over from pre-switch signal log          │
│                                                       │
│  Re-read ratio: 0.45 ← ELEVATED                      │
│    → Model switch caused context loss, agent is       │
│      re-reading files it already read under Claude    │
│                                                       │
│  Error density: 0.20                                  │
│    → New model still learning the codebase            │
│                                                       │
│  Composite: 0.43 (COMPRESS state)                     │
│  → Auto-consolidation triggered                       │
└──────────────────────────────────────────────────────┘
```

### Key Extensions

| Extension | Description |
|-----------|-------------|
| **Model-relative token %** | Normalize against current model's context window, not a fixed 200K |
| **Switch penalty** | When model switches, add +0.15 to re-read ratio (context was lost) |
| **Cross-model checkpoint** | Checkpoint includes model history so the new model knows what was done |
| **Shared signal log** | `.mnemos/signals.jsonl` persists across model switches (it's on disk) |
| **Budget-aware thresholds** | If running on free tier (Qwen local), relax fatigue thresholds (no cost pressure) |

### Checkpoint Format — Extended for Multi-Model

```json
{
  "goal": "Implement voice surveys",
  "model_history": [
    {"provider": "anthropic", "model": "claude-sonnet", "tokens_used": 145000, "duration_s": 420},
    {"provider": "openai", "model": "gpt-4o", "tokens_used": 83000, "duration_s": 180}
  ],
  "switch_reason": "anthropic quota exceeded",
  "active_constraints": ["..."],
  "active_results": ["..."],
  "current_subgoal": "...",
  "fatigue_at_checkpoint": 0.43,
  "icpg_state": {"..."},
  "cikg_context": {
    "market_validation": "3 competitors have voice — table stakes",
    "gap_id": "uuid-of-cikg-gap-node"
  }
}
```

---

## 5. Data Flow — End to End

```
1. USER opens Maggy dashboard
   → Sees all projects, token budgets, active agents

2. USER selects ticket from inbox (or creates feature idea)
   │
   ▼
3. CIKG VALIDATION (new features only)
   → find_gaps(): who has this? competitive pressure?
   → get_landscape(): market trend alignment?
   → Output: market score + competitive context
   │
   ▼
4. STRUCTURAL ANALYSIS (codebase-memory-mcp)
   → search_graph: locate relevant symbols across projects
   → trace_path: map call chains and fan-out (with risk labels)
   → get_architecture: understand module boundaries
   → Output: structural dependency map
   │
   ▼
5. iCPG ANALYSIS (layers on structural graph)
   → query blast: which files are affected?
   → query risk: are they fragile?
   → query constraints: what invariants exist?
   → Output: blast radius score (0-10)
   │
   ▼
6. MODEL SELECTION (from blast score + budget)
   → Score 0-3: Qwen local / DeepSeek (free tier)
   → Score 4-6: Kimi / Gemini Flash (cheap tier)
   → Score 7-10: Claude / GPT-4o (full tier)
   → Check token budget: rotate if primary is exhausted
   │
   ▼
7. PLANNING (score 7+ only)
   → Claude creates architecture plan
   → Codex independently counter-checks
   → Both get structural context from codebase-memory-mcp
   → Maggy shows diff in UI
   → User approves
   │
   ▼
8. EXECUTION
   → Polyphony provisions Docker container
   → Pi starts in RPC mode with selected model
   → Pi queries codebase-memory-mcp for context before editing
   → Claude Code Task agent controls Pi via RPC
   → Mnemos tracks fatigue (model-normalized)
   → If quota hits: Pi switches model, Mnemos logs switch
   │
   ▼
9. VERIFICATION
   → Tests pass in container
   → detect_changes: verify actual scope matches intended scope
   → iCPG drift check: no unintended scope drift
   → Code review (can use second model for independence)
   │
   ▼
10. DEPLOY
    → Changes on feature branch → PR created
    → Vercel preview deploy via isolated browser container
    → User reviews in Maggy dashboard
    │
    ▼
11. PROCESS LEARNING (async, post-merge)
    → Collect PR review comments + CodeRabbit findings
    → Collect CI pass/fail results for Maggy-written code
    → Track review rounds, time-to-merge, post-merge incidents
    → Update process_patterns.db, ci_patterns.db, pr_patterns.db
    → Feed reward registry: +0.5 first-round approval, -0.4 critical finding
    → Adjust policy: add pre-checks, evolve skills, tune PR sizing
```

---

## 6. Project Registry

```yaml
# ~/.maggy/projects.yaml
projects:
  - name: zensurveys-backend
    repo: zenloopGmbH/surveys-backend
    path: ~/Documents/protaige/projects/zensurveys
    default_branch: staging-v2
    vercel_session: vercel-session-A
    icpg: true
    cikg: false  # not a product repo

  - name: zensurveys-frontend
    repo: zenloopGmbH/main-frontend-clean
    path: ~/Documents/protaige/projects/main-frontend-clean
    default_branch: main
    vercel_session: vercel-session-B
    icpg: true
    cikg: false

  - name: chief-of-staff
    repo: alinaqi/chief-of-staff
    path: ~/Documents/protaige/projects/chief-of-staff
    default_branch: main
    vercel_session: vercel-session-C
    icpg: true
    cikg: true  # has competitive intelligence graph

  - name: rodcast
    repo: alinaqi/rodcast
    path: ~/Documents/AI-Playground/rodcast
    default_branch: main
    vercel_session: vercel-session-D
    icpg: true
    cikg: false
```

---

## 7. Component Map

```
claude-bootstrap/
├── maggy/                        # Maggy v2 — web dashboard
│   ├── src/
│   │   ├── api/                  # FastAPI routes
│   │   ├── providers/            # GitHub, Asana, Linear
│   │   ├── services/
│   │   │   ├── inbox.py          # AI-prioritized ticket inbox
│   │   │   ├── executor.py       # Execute pipeline (now via Pi)
│   │   │   ├── competitor.py     # Daily briefing
│   │   │   ├── planner.py        # NEW: dual-model planning
│   │   │   ├── budget.py         # NEW: token budget manager
│   │   │   ├── deploy.py         # NEW: isolated Vercel deploys
│   │   │   ├── process.py        # NEW: process intelligence (env discovery, signal collection)
│   │   │   └── forge.py          # NEW: MCP Forge integration (capability expansion)
│   │   └── orchestrator.py       # NEW: multi-project orchestrator
│   └── frontend/                 # React dashboard
│       ├── ProjectRegistry.tsx   # NEW: multi-project view
│       ├── TokenBudget.tsx       # NEW: usage per model
│       ├── PlanReview.tsx        # NEW: dual-model plan diff
│       └── DeployStatus.tsx      # NEW: per-project deploy
│
├── scripts/
│   ├── polyphony/                # Container orchestration
│   │   ├── adapters/
│   │   │   ├── pi.py             # NEW: PiAdapter (replaces claude/codex/kimi)
│   │   │   ├── claude.py         # DEPRECATED: kept for fallback
│   │   │   ├── codex.py          # DEPRECATED: kept for fallback
│   │   │   └── kimi.py           # DEPRECATED: kept for fallback
│   │   ├── budget.py             # NEW: token budget + model routing
│   │   ├── runtime.py            # Docker container lifecycle
│   │   ├── orchestrator.py       # Supervisor loop
│   │   └── ...
│   ├── icpg/                     # Code graph (per-project)
│   ├── mnemos/                   # Memory + fatigue
│   │   ├── fatigue.py            # EXTENDED: model-normalized
│   │   ├── checkpoint.py         # EXTENDED: cross-model state
│   │   └── ...
│   └── cikg/                     # NEW: extracted from chief-of-staff
│       ├── __init__.py
│       ├── graph.py              # KnowledgeGraphService
│       ├── models.py             # Node/Edge types
│       └── __main__.py           # CLI: cikg query/traverse/gaps
│
├── skills/
│   ├── polyphony/SKILL.md        # Updated for Pi
│   ├── mnemos/SKILL.md           # Updated for multi-model
│   ├── icpg/SKILL.md             # Unchanged
│   ├── code-graph/SKILL.md       # codebase-memory-mcp integration
│   └── cikg/SKILL.md             # NEW: competitive intelligence skill
│
├── templates/
│   ├── Dockerfile.polyphony      # Updated: includes Pi
│   ├── Dockerfile.vercel-session # NEW: Playwright + Chrome
│   └── ...
│
└── docs/
    ├── architecture-v5.md        # THIS DOCUMENT
    ├── polyphony-spec.md         # Container orchestration spec
    └── mnemos-implementation.md  # Memory lifecycle spec
```

---

## 8. Migration Path

| Phase | What | Depends On |
|-------|------|-----------|
| **Phase 1** | PiAdapter + token budget manager | Pi installed |
| **Phase 2** | Model-tiered routing (blast score → model) | Phase 1 + iCPG |
| **Phase 3** | Mnemos multi-model fatigue | Phase 1 |
| **Phase 4** | Extract CIKG from chief-of-staff | Supabase access |
| **Phase 5** | Maggy v2 multi-project UI | Phases 1-4 |
| **Phase 6** | Dual-model planning (Claude + Codex) | Phase 1 |
| **Phase 7** | Isolated Vercel deploy containers | Docker |
| **Phase 8** | Process intelligence (env discovery + signal collection) | Phase 5 + GitHub API |
| **Phase 9** | MCP Forge integration (capability expansion) | Phase 5 + mcp_forge |
| **Phase 10** | Integration testing + docs | All phases |

---

## 9. Security Considerations

| Concern | Mitigation |
|---------|-----------|
| API keys across models | Pi's auth.json + env vars, never in code |
| Container escape | Polyphony containers run unprivileged, no host network |
| Vercel session theft | Each browser container has isolated Chrome profile in Docker volume |
| CIKG data sensitivity | Competitive intelligence stays in Supabase with RLS |
| Local model data leaks | Qwen/Ollama runs fully local, no data leaves machine |
| Token budget manipulation | Budget file is local YAML, not exposed via API |

---

## 10. Core Principle — mWp (Minimum Wowable Product)

Every component in this architecture must be designed to wow, not just work.

> **mWp > MVP**: We don't ship "minimum viable." We ship "minimum wowable." The bar is: would this make someone stop scrolling and say "wait, how did it do that?"

### What mWp means for each component

| Component | MVP (don't ship this) | mWp (ship this) |
|-----------|----------------------|-----------------|
| Token budget | Show remaining tokens | Auto-rotate models mid-task, user never notices the switch |
| Blast radius | Show a score number | Score drives model selection, review depth, and plan complexity automatically |
| CIKG validation | "3 competitors have this" | "Here's the competitive gap map, market trend alignment, and suggested positioning — before you write a line of code" |
| Mnemos fatigue | "Context 80% full" | Silently checkpoints, switches models, re-injects context — user's train of thought is never interrupted |
| Vercel deploy | "Run vercel deploy" | 4 projects deploy in parallel with zero auth conflicts, preview links appear in Maggy dashboard |
| Code graph | "We indexed your repo" | "Maggy already knows every function, every caller, every route across all 36 projects — before you ask. It traced the blast radius in 10ms, not 10 minutes of grepping." |
| Process intelligence | "Here are your CI results" | "Maggy learned that your reviewer always flags missing error handling — it added it before the PR was created. CI pass rate went from 72% to 97%. Review rounds dropped from 2.8 to 1.1. It didn't just fix the code, it fixed the process." |
| Capability expansion | "We don't support that integration" | "Maggy built a Linear MCP server from the API docs, registered the tools, and pulled your sprint data — all within the same conversation." |
| Dual-model planning | Two plans side by side | Conflicts highlighted, trade-offs explained, one-click approval with merged approach |

### The 5-second test for Maggy v2

A developer opens Maggy in the morning. Within 5 seconds they see:
- Inbox ranked by urgency across all 4 projects
- Token budget status (green/yellow/red per provider)
- Active agents and their progress
- Yesterday's competitive intelligence briefing
- Process health: CI pass rate, review rounds trend, CodeRabbit findings trend
- One-click "Execute" on any ticket with the right model auto-selected

That's the wow.

---

## 11. Maggy as a Self-Improving System

Maggy is not a tool that waits for instructions. It's an autonomous agent with a single objective function: **maximize user development efficiency**. It observes, measures, optimizes, and evaluates itself — continuously, without asking for permission.

### The Objective Function

```
efficiency = (value_delivered / time_spent) × quality_multiplier

where:
  value_delivered  = tickets landed + features shipped + bugs fixed
  time_spent       = wall clock from ticket selection to merge
  quality_multiplier = 1.0 - (bug_escape_rate + revert_rate + incident_rate)
```

Maggy optimizes this function across all projects, all models, all workflows. Everything it does — model routing, inbox ordering, workflow tuning, fatigue management — feeds back into this single metric.

### Reward Registry

Every action Maggy takes generates a reward signal. Positive rewards reinforce. Negative rewards suppress. The registry is the memory of what works.

```
┌─────────────────────────────────────────────────────────────┐
│  REWARD REGISTRY                                             │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  POSITIVE REWARDS (reinforce)                       │    │
│  │                                                      │    │
│  │  +1.0  Ticket lands without human intervention       │    │
│  │  +0.8  Tests pass on first attempt                   │    │
│  │  +0.5  Time-to-merge below rolling average           │    │
│  │  +0.3  No bug escapes at 2-week mark                 │    │
│  │  +0.2  User doesn't re-do the work manually          │    │
│  │  +0.1  Model switch was seamless (no re-reads spike) │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  NEGATIVE REWARDS (suppress)                        │    │
│  │                                                      │    │
│  │  -1.0  User reverts the change                       │    │
│  │  -0.8  Bug escape discovered post-merge              │    │
│  │  -0.5  User manually re-does the task                │    │
│  │  -0.3  Tests fail after model switch                 │    │
│  │  -0.2  User overrides Maggy's model/routing choice   │    │
│  │  -0.1  Time-to-merge above rolling average           │    │
│  │  -0.1  iCPG drift detected after task completion     │    │
│  │  -0.1  detect_changes shows scope exceeded intent   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Rewards decay: 0.95^(days_since_event)                     │
│  Window: 60-day rolling                                      │
│  Cold start: hardcoded defaults until 30+ events per signal  │
└─────────────────────────────────────────────────────────────┘
```

### Multi-Level Closed-Loop Control

The previous version of this section described a flat observe → measure → adjust → evaluate loop. That's not a closed-loop system — that's batch processing with hope. A bad model routing decision on Monday would serve degraded output to every task until the weekly evaluation catches it.

**Control theory insight: inner loops provide stability, outer loops provide optimization.** Level 0 keeps individual tasks from going off the rails. Level 2 keeps tools and models healthy day-to-day. Level 3 makes Maggy smarter week-over-week. Each level's output becomes an input signal for the level above it.

```
┌──────────────────────────────────────────────────────────────┐
│  MULTI-LEVEL CLOSED-LOOP CONTROL                              │
│                                                               │
│  Level 4 ─── Monthly (evolutionary) ──────────────────────── │
│  │  Sensor:  cross-project trends, platform trajectory        │
│  │  Actuator: new reward signals, new process patterns,       │
│  │           blast→tier recalibration, exploration rate        │
│  │  Bandwidth: weeks                                          │
│  │                                                            │
│  │  Level 3 ─── Weekly (strategic) ────────────────────────  │
│  │  │  Sensor:  worst/best task patterns, score deltas,       │
│  │  │          process pattern analysis, capability gaps      │
│  │  │  Actuator: skill evolution, workflow step changes,      │
│  │  │           model routing thresholds, MCP Forge,          │
│  │  │           PR strategy, prompt patches                   │
│  │  │  Bandwidth: days                                        │
│  │  │                                                         │
│  │  │  Level 2 ─── Daily (operational) ──────────────────   │
│  │  │  │  Sensor:  CI pass rates, review round trends,        │
│  │  │  │          CodeRabbit findings, model failure rates,   │
│  │  │  │          token budget burn rate                       │
│  │  │  │  Actuator: pre-commit check toggles, lint rules,     │
│  │  │  │           model enable/disable, routing weights      │
│  │  │  │  Bandwidth: hours                                    │
│  │  │  │                                                      │
│  │  │  │  Level 1 ─── Task (post-completion) ─────────────  │
│  │  │  │  │  Sensor:  task reward score, CI results,          │
│  │  │  │  │          iCPG drift, detect_changes scope,        │
│  │  │  │  │          review comments on PR                    │
│  │  │  │  │  Actuator: update model scores, log process       │
│  │  │  │  │           signals, update fatigue profile          │
│  │  │  │  │  Bandwidth: minutes                               │
│  │  │  │  │                                                   │
│  │  │  │  │  Level 0 ─── Real-time (within task) ──────────│
│  │  │  │  │  │  Sensor:  tool success/fail, test pass/fail,  ││
│  │  │  │  │  │          lint errors, Pi RPC events,          ││
│  │  │  │  │  │          model response quality, fatigue      ││
│  │  │  │  │  │  Actuator: switch model, retry with context,  ││
│  │  │  │  │  │           adjust verification depth,          ││
│  │  │  │  │  │           abort + re-plan, checkpoint          ││
│  │  │  │  │  │  Bandwidth: seconds                           ││
│  │  │  │  │  └───────────────────────────────────────────────┘│
│  │  │  │  └──────────────────────────────────────────────────┘│
│  │  │  └─────────────────────────────────────────────────────┘│
│  │  └────────────────────────────────────────────────────────┘│
│  └───────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘

Signal cascade (inner → outer):
  L0 events aggregate into → L1 task reward
  L1 task rewards aggregate into → L2 daily trends
  L2 daily trends feed → L3 weekly pattern analysis
  L3 weekly patterns feed → L4 monthly trajectory
```

#### Level 0 — Real-Time (Within Task Execution)

This is the **stability loop** — the most critical and currently missing level. It keeps individual tasks from going off the rails *as they happen*, not after the damage is done.

```
┌──────────────────────────────────────────────────────────────┐
│  LEVEL 0 — REAL-TIME CONTROL (seconds)                        │
│                                                               │
│  Pi agent executing task inside Polyphony container           │
│       │                                                       │
│       ├── Tool call fails (file not found, API error)         │
│       │   → Retry with adjusted path/params (not new model)  │
│       │   → If 3 consecutive fails: escalate model tier       │
│       │                                                       │
│       ├── Test fails during TDD green phase                   │
│       │   → Analyze error: syntax? logic? missing import?     │
│       │   → If model is struggling (3+ failed attempts):      │
│       │     checkpoint + switch to higher-tier model           │
│       │                                                       │
│       ├── Lint error on written code                          │
│       │   → Auto-fix (ruff --fix / eslint --fix)              │
│       │   → If pattern repeats: flag for L2 (add pre-check)  │
│       │                                                       │
│       ├── Fatigue signal crosses threshold                    │
│       │   → Mnemos auto-checkpoint                            │
│       │   → If mid-task: consolidate context, continue        │
│       │   → If near completion: push through, checkpoint after│
│       │                                                       │
│       ├── Model response quality degrades                     │
│       │   → Detected by: repeated re-reads, circular edits,  │
│       │     tool calls that undo previous tool calls          │
│       │   → Action: checkpoint + model switch immediately     │
│       │                                                       │
│       └── Scope drift detected (iCPG)                         │
│           → Agent touching files outside blast radius          │
│           → Action: warn → constrain → abort if persistent    │
│                                                               │
│  All L0 events are logged to signals.jsonl with timestamps.   │
│  They aggregate into the L1 task reward score.                │
└──────────────────────────────────────────────────────────────┘
```

**Why L0 matters more than any weekly patch:** If Maggy can detect mid-task that the current model is struggling and switch to a stronger one *within seconds*, that's worth more than a hundred policy adjustments. A user whose task fails experiences -1.0 reward. A user whose task recovers mid-flight via model switch experiences +0.1. The delta between "fail and retry tomorrow" and "hiccup and recover" is the entire product experience.

**L0 signal types:**

| Signal | Detection Method | Response Time | Action |
|--------|-----------------|---------------|--------|
| Tool failure | Pi RPC error event | < 1s | Retry with adjusted params |
| Test failure | Exit code from test runner | < 5s | Analyze, fix, or escalate model |
| Lint error | ruff/eslint output on written code | < 2s | Auto-fix or flag for L2 |
| Fatigue spike | Mnemos threshold breach | < 1s | Checkpoint, consolidate, or switch |
| Quality degradation | Circular edits, re-reads, undo patterns | ~30s | Checkpoint + model switch |
| Scope drift | iCPG blast radius check on file access | < 1s | Warn → constrain → abort |
| Model quota hit | Pi RPC quota/rate error | < 1s | Fallback chain activation |

#### Level 1 — Task (Post-Completion, Minutes)

After each task completes, compute the task reward score and update the per-model, per-task-type scores. This is the **learning loop** — every completed task teaches Maggy something.

```
Task completes (PR created or code landed)
    │
    ├── Compute task reward from L0 signals:
    │   reward = Σ(signal_weight × signal_value)
    │   adjusted for: model used, blast tier, task type
    │
    ├── Update model_scores.db:
    │   (claude, auth, high) → new running average
    │
    ├── Update fatigue_profile:
    │   session duration, checkpoint timing, recovery reads
    │
    ├── Log L0 events summary → L2 aggregation:
    │   "3 tool retries, 1 model switch, 0 scope drifts"
    │
    └── Emit task_completed event → Maggy dashboard
```

#### Level 2 — Daily (Operational, Hours)

Runs on a daily schedule (or triggered when a threshold is breached). Catches degradation before it compounds. This is the **operational health loop**.

```
Daily aggregation job:
    │
    ├── CI pass rate today vs 7-day average
    │   → If dropped >10%: disable the model causing failures
    │
    ├── Review rounds today vs 7-day average
    │   → If increased: check which code patterns are new
    │
    ├── CodeRabbit critical findings today
    │   → If >0 on Maggy-written code: add pattern to pre-check
    │
    ├── Model failure rate by tier
    │   → If a model's L0 failure signals spike: demote it
    │
    ├── Token budget burn rate
    │   → If burning faster than expected: adjust routing to cheaper tier
    │
    └── Emergency trigger: if any metric drops >15% in one day
        → Halt exploration, revert last policy change, alert
```

**Why L2 exists separately from L3:** A weekly batch can't catch a model that started failing on Tuesday. By Friday, that's 3 days of degraded tasks, 3 days of negative rewards accumulating. L2's daily check catches it within hours and disables the failing model before the damage compounds.

#### Level 3 — Weekly (Strategic, Days)

The deliberate optimization loop. Analyzes patterns across the week, proposes and applies policy changes with rollback windows. This is where skill evolution, workflow step changes, and MCP Forge generation happen.

```
Weekly strategic analysis:
    │
    ├── Worst 10 tasks this week: what went wrong?
    │   → Common patterns → skill file patches
    │   → Recurring reviewer comments → add to review prevention
    │
    ├── Best 10 tasks this week: what went right?
    │   → Reinforce: model, workflow, blast tier settings
    │
    ├── Score deltas from last week's modifications
    │   → delta < -0.2: auto-revert
    │   → delta > +0.2: reinforce + expand to similar task types
    │
    ├── Process pattern analysis
    │   → New (code_pattern, review_feedback) entries
    │   → PR sizing effectiveness
    │   → CI failure patterns
    │
    ├── Capability gap analysis
    │   → Top unresolvable requests → trigger MCP Forge
    │
    └── Exploration candidates
        → Select 10% of low-blast task types for next week's exploration
```

#### Level 4 — Monthly (Evolutionary, Weeks)

The meta-optimization loop. Evaluates whether the control system itself is improving. Changes the reward signals, recalibrates tier boundaries, adjusts exploration rates. This is the loop that improves the improvement process.

```
Monthly evolution review:
    │
    ├── Cross-project patterns
    │   → Are skills learned in project A useful in project B?
    │   → Promote project-specific skills to global skills
    │
    ├── Reward signal effectiveness
    │   → Is any signal consistently noisy? Reduce its weight
    │   → Is a new signal needed? (e.g., deploy success rate)
    │   → Add, remove, or reweight signals
    │
    ├── Tier boundary recalibration
    │   → If blast 4-6 tasks are consistently handled well by
    │     the cheap tier, lower the threshold: 0-4 = cheap
    │   → If blast 3 tasks keep failing on cheap models,
    │     raise it: 0-2 = cheap, 3+ = medium
    │
    ├── Exploration rate adjustment
    │   → If exploration success rate > 40%: increase to 15%
    │   → If exploration success rate < 10%: decrease to 5%
    │
    ├── Control loop tuning
    │   → Is L2 catching issues that should be caught at L0?
    │   → Are L0 model switches too aggressive or too cautious?
    │   → Adjust L0 thresholds based on L1 outcome data
    │
    └── Platform trajectory
        → Efficiency trend: improving, flat, or declining?
        → If flat for 2+ months: the system has saturated
          current strategy — try structural change
```

#### Signal Cascade — How Levels Feed Each Other

```
┌──────────────────────────────────────────────────────────────┐
│  SIGNAL CASCADE                                               │
│                                                               │
│  L0: tool_fail, test_fail, lint_error, model_switch           │
│   │  (raw events, seconds)                                    │
│   ▼                                                           │
│  L1: task_reward = f(L0_signals)                              │
│   │  model_score[claude, auth, 8] += task_reward              │
│   │  (per-task aggregation, minutes)                          │
│   ▼                                                           │
│  L2: daily_ci_rate = mean(L1.ci_pass for today)               │
│   │  daily_model_health[claude] = mean(L1.rewards for claude) │
│   │  (daily aggregation, hours)                               │
│   │  ACTION: disable model if health < threshold              │
│   ▼                                                           │
│  L3: weekly_pattern = cluster(L2.failures + L1.review_comments│
│   │  score_delta = this_week.reward - last_week.reward        │
│   │  (weekly analysis, days)                                  │
│   │  ACTION: evolve skills, adjust routing, trigger Forge     │
│   ▼                                                           │
│  L4: monthly_trajectory = trend(L3.score_deltas)              │
│      reward_signal_weights = recalibrate(L3.signal_noise)     │
│      (monthly meta-analysis, weeks)                           │
│      ACTION: change reward function itself, adjust L0-L3      │
│                                                               │
│  Key: outer loops NEVER override inner loop stability.        │
│  L3 can change routing policy, but L0 still catches in-task   │
│  failures regardless of what L3 decided.                      │
└──────────────────────────────────────────────────────────────┘
```

### What Gets Optimized (and How)

#### 1. Model Routing

Maggy tracks reward per `(model × task_type × blast_tier)` triple:

```
reward_table:
  (claude, auth, high):      +0.92  ← claude is great at auth
  (claude, docs, low):       +0.40  ← claude works but wasteful
  (qwen, docs, low):         +0.85  ← qwen is faster + free
  (qwen, auth, medium):      -0.30  ← qwen failed auth tasks
  (gpt-4o, frontend, medium):+0.78  ← gpt-4o is strong on frontend
  (kimi, tests, low):        +0.70  ← kimi writes good tests cheaply
```

Maggy routes new tasks to the model with the highest reward for that `(task_type, blast_tier)`. No human in the loop — the reward table decides.

If a model has no data for a task type, Maggy uses the tier default (hardcoded) until it collects 30+ data points.

#### 2. Inbox Ordering

Inbox priority is a weighted score that Maggy continuously adjusts:

```python
priority = (
    w_urgency * urgency_score
    + w_okr * okr_alignment
    + w_recency * recency
    + w_type * type_weight[ticket.type]
    + w_project * project_weight[ticket.project]
)
```

The weights (`w_urgency`, `w_okr`, etc.) are updated based on which tickets the user actually executes first. If the user consistently picks security tickets despite Maggy ranking them 5th, the type weight for security increases automatically. Not because Maggy asked — because the reward signal said "user overrode my ranking" (-0.2) and Maggy's adjustment brought the ranking closer to what the user actually does.

#### 3. Workflow Steps

Some workflow steps add value, some don't. Maggy measures reward per step:

```
workflow_rewards:
  codex_counter_check:
    blast_0_3: -0.1    # adds latency, never catches issues
    blast_4_6: +0.2    # catches real issues sometimes
    blast_7_10: +0.6   # catches critical issues often

  icpg_drift_check:
    all_tiers: +0.4    # consistently prevents regressions

  high_tier_post_review:
    after_qwen: +0.7   # catches qwen mistakes frequently
    after_kimi: +0.3   # kimi output is cleaner, fewer catches
    after_claude: +0.0  # reviewing claude with claude is redundant
```

Maggy skips steps with consistently negative reward. No permission needed — if Codex counter-check never catches issues on blast < 3, it gets dropped from that tier. If it starts catching issues again (maybe the codebase grew more complex), the reward changes and it gets re-enabled.

#### 4. Fatigue Thresholds

Different users fatigue differently. Maggy learns the user's fatigue curve:

```
fatigue_profile:
  avg_productive_session_minutes: 47
  pre_checkpoint_optimal_minutes: 42
  model_switch_recovery_reads: 3.2    # avg re-reads after switch
  best_model_for_recovery: gpt-4o    # fastest context rebuild
```

Maggy pre-checkpoints at 42 minutes (not at the generic 0.60 threshold) because it learned this user's fatigue pattern. No question asked — the reward signal showed that checkpoints at 42 minutes led to better post-checkpoint output (+0.3 reward) than checkpoints at 50 minutes (-0.2 reward from quality drop).

#### 5. Process Intelligence — Learning from the Full SDLC

Maggy doesn't just optimize code output. It optimizes the **entire development process** by observing what happens to code after it's written: PR reviews, CI results, CodeRabbit findings, reviewer feedback, merge patterns, and post-deploy incidents.

##### 5a. Environment Discovery

On first run per project, Maggy auto-discovers the developer's workflow. No configuration — it reads what's already there.

```
┌──────────────────────────────────────────────────────────────┐
│  ENVIRONMENT DISCOVERY (auto, per project)                     │
│                                                               │
│  Ticketing:                                                   │
│    gh api repos/{owner}/{repo}/issues → GitHub Issues?        │
│    .asana.yml / .linear/* / jira.config → which tracker?      │
│    Maggy Inbox providers config → already connected?          │
│                                                               │
│  GitHub Integrations:                                         │
│    gh api repos/{owner}/{repo}/hooks → webhooks               │
│    gh api repos/{owner}/{repo}/installation → GitHub Apps     │
│    PR comment authors → detect bots: coderabbitai[bot],       │
│      dependabot[bot], renovate[bot], github-actions[bot]      │
│                                                               │
│  CI/CD:                                                       │
│    .github/workflows/*.yml → GitHub Actions                   │
│    Jenkinsfile / .circleci/ / .gitlab-ci.yml → other CI       │
│    gh api repos/{owner}/{repo}/actions/runs → run history     │
│                                                               │
│  Code Quality:                                                │
│    .eslintrc* / ruff.toml / .prettierrc → lint config         │
│    mypy.ini / tsconfig.json → type checking                   │
│    .pre-commit-config.yaml → pre-commit hooks                 │
│    codecov.yml / .nycrc → coverage config                     │
│                                                               │
│  Review Process:                                              │
│    gh api repos/{owner}/{repo}/branches/{b}/protection        │
│      → required reviewers, status checks, merge rules         │
│    CODEOWNERS → who reviews what                              │
│    Average PR review rounds from git history                   │
│                                                               │
│  Output: ~/.maggy/environments/{project}.yaml                 │
└──────────────────────────────────────────────────────────────┘
```

```yaml
# ~/.maggy/environments/zensurveys-backend.yaml (auto-generated)
ticketing: github_issues
github_integrations:
  - coderabbitai        # CodeRabbit AI reviews
  - dependabot          # dependency updates
  - vercel              # preview deploys
ci:
  provider: github_actions
  workflows:
    - test.yml          # pytest + coverage
    - lint.yml          # ruff + mypy
    - deploy.yml        # staging deploy
lint:
  python: [ruff, mypy]
  config_files: [ruff.toml, mypy.ini]
review:
  required_approvals: 1
  codeowners: true
  branch_protection: staging-v2
```

##### 5b. Process Signal Collection

Maggy subscribes to signals from every stage of the SDLC pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│  PROCESS SIGNALS (collected per PR / per task)                │
│                                                              │
│  ┌─── REVIEW SIGNALS ────────────────────────────────────┐  │
│  │                                                        │  │
│  │  PR reviewer comments (human)                         │  │
│  │    → "missing error handling in /api/surveys"          │  │
│  │    → "this should be a transaction"                    │  │
│  │    → "add tests for edge case"                         │  │
│  │                                                        │  │
│  │  CodeRabbit findings (automated)                      │  │
│  │    → severity: critical/warning/suggestion             │  │
│  │    → category: security/performance/style/bug          │  │
│  │    → file + line + specific suggestion                 │  │
│  │                                                        │  │
│  │  Review rounds                                        │  │
│  │    → PR needed 3 rounds before approval                │  │
│  │    → First round had 8 comments, second had 2          │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─── CI SIGNALS ────────────────────────────────────────┐  │
│  │                                                        │  │
│  │  GitHub Actions results                               │  │
│  │    → test.yml: PASS (42s)                              │  │
│  │    → lint.yml: FAIL — ruff: 3 errors, mypy: 1 error   │  │
│  │    → deploy.yml: PASS (preview URL generated)          │  │
│  │                                                        │  │
│  │  Failure patterns                                     │  │
│  │    → lint failures in files Maggy touched              │  │
│  │    → test failures from code Maggy wrote               │  │
│  │    → flaky tests (pass/fail on same code)              │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─── POST-MERGE SIGNALS ────────────────────────────────┐  │
│  │                                                        │  │
│  │  Revert within 48h → code was bad                     │  │
│  │  Hotfix within 7d  → code had latent bug              │  │
│  │  Incident linked to PR → production impact            │  │
│  │  Dependency alert (Dependabot/Renovate) → stale deps  │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

New reward signals for the registry:

```
PROCESS REWARD SIGNALS

+0.5  PR approved on first review round
+0.3  CI passes on first push (no re-push needed)
+0.2  CodeRabbit: zero critical/warning findings
+0.1  PR merged within 24h of creation

-0.8  PR reverted within 48h
-0.5  CI fails on Maggy-written code (lint or test)
-0.4  CodeRabbit critical finding on Maggy-written code
-0.3  PR requires 3+ review rounds
-0.2  Reviewer flags same issue type Maggy was warned about before
-0.1  CodeRabbit warning finding on Maggy-written code
```

##### 5c. Process Learning

Maggy tracks patterns across three dimensions:

**Code Pattern → Review Feedback:**
```
process_patterns.db:

(api_route, missing_error_handling):
  occurrences: 7
  reviewers: ["alice", "coderabbitai"]
  fix_pattern: "add try/except with proper HTTP error codes"
  → LEARNED: always add error handling to API routes

(database_query, missing_transaction):
  occurrences: 4
  reviewers: ["bob"]
  fix_pattern: "wrap multi-table writes in transaction"
  → LEARNED: multi-table writes need transactions

(test_file, missing_edge_case):
  occurrences: 12
  reviewers: ["alice", "bob", "coderabbitai"]
  fix_pattern: "test empty input, null, boundary values"
  → LEARNED: always test edge cases (empty, null, boundary)
```

**File → CI Failure:**
```
ci_patterns.db:

src/api/surveys.py:
  lint_failures: 5 (ruff E501, E741)
  type_errors: 2 (mypy: missing return type)
  → LEARNED: this file needs strict lint pre-check

tests/test_integration.py:
  flaky_rate: 0.15 (fails 15% of runs on same code)
  → LEARNED: mark as flaky, don't block on single failure

src/services/auth.py:
  ci_failures: 0 in 30 days
  → LEARNED: auth code is well-tested, low CI risk
```

**PR Characteristics → Merge Velocity:**
```
pr_patterns.db:

(size < 200 lines, single_concern):
  avg_review_rounds: 1.2
  avg_time_to_merge: 4h
  → LEARNED: small focused PRs merge fast

(size > 500 lines, multi_concern):
  avg_review_rounds: 3.1
  avg_time_to_merge: 48h
  → LEARNED: split large PRs into stacked PRs

(has_tests, covers_new_code):
  approval_rate_first_round: 0.78
  → LEARNED: tests increase first-round approval

(no_tests, new_feature):
  reviewer_comment_rate: 0.95
  most_common: "please add tests"
  → LEARNED: never submit new features without tests
```

##### 5d. Process Optimization — What Maggy Changes

Based on learned patterns, Maggy autonomously adjusts its own behavior:

| What Changes | Based On | Example |
|-------------|---------|---------|
| **Pre-task lint** | CI failure patterns | Maggy runs `ruff check` + `mypy` on its output before committing — prevents CI failures it has seen before |
| **Skill evolution** | Recurring review comments | If reviewers flag "missing error handling" 7 times, Maggy adds the pattern to its skill files — future code includes error handling by default |
| **PR sizing** | Merge velocity data | If PRs > 500 lines take 3x longer to merge, Maggy splits tasks into stacked PRs automatically |
| **Test generation** | Reviewer feedback | If "add tests" is the most common review comment, Maggy ensures every PR includes tests for new code |
| **CodeRabbit pre-check** | CodeRabbit finding patterns | If CodeRabbit consistently flags the same security issue, Maggy pre-validates against that pattern before pushing |
| **Commit hygiene** | CI config + branch rules | Maggy matches commit message format, branch naming, and PR template to whatever the project enforces |

```yaml
# Added to ~/.maggy/policy.yaml
process:
  pre_commit_checks:
    ruff: true                     # learned: lint failures cost -0.5
    mypy: true                     # learned: type errors caught by CI
    test_coverage_min: 80          # learned: PRs without coverage get rejected
  pr_strategy:
    max_lines: 400                 # learned: optimal size for this team
    stacked_prs: true              # learned: large changes split = faster merge
    require_tests: true            # learned: "add tests" is #1 review comment
  review_prevention:
    error_handling_api_routes: true # learned from 7 review comments
    transaction_multi_writes: true # learned from 4 review comments
    edge_case_tests: true          # learned from 12 review comments
  coderabbit_precheck:
    security_scan: true            # learned: CodeRabbit catches these
    unused_imports: true           # learned: CodeRabbit flags these
```

##### 5e. The Process Intelligence Flywheel

```
┌──────────────────────────────────────────────────────────────┐
│  PROCESS INTELLIGENCE FLYWHEEL                                │
│                                                               │
│  Week 1: Maggy discovers environment, starts collecting       │
│    → Sees 5 lint failures, 3 "add tests" comments             │
│    → Learns: run lint before push, always include tests       │
│                                                               │
│  Week 2: Maggy applies learned patterns                       │
│    → Lint failures drop to 0 (pre-checked)                    │
│    → "Add tests" comments drop to 1 (edge case missed)        │
│    → Review rounds drop from 2.8 to 1.6 avg                  │
│                                                               │
│  Week 4: Maggy has enough data for deeper patterns            │
│    → Learns that PRs touching auth need 2 reviewers           │
│    → Learns that Friday PRs take 2x longer to merge           │
│    → Starts scheduling auth PRs for Monday-Wednesday          │
│                                                               │
│  Week 8: Maggy evolves its own skills                         │
│    → Writes new lint rules based on recurring review comments │
│    → Generates pre-commit hooks for patterns that always fail │
│    → Review round avg: 1.1 (down from 2.8)                   │
│    → CI first-pass rate: 97% (up from 72%)                    │
│    → Time-to-merge: 6h avg (down from 36h)                    │
│                                                               │
│  The wow: Maggy didn't just write better code.                │
│  It made the entire development process faster.               │
└──────────────────────────────────────────────────────────────┘
```

#### 6. Capability Expansion — MCP Forge Integration

When Maggy encounters a capability gap — a workflow integration that doesn't exist — it doesn't stop. It builds one.

**Source:** MCP Forge (`~/Documents/protaige/mcp_forge`) generates TypeScript MCP servers from API documentation.

```
Maggy task requires Mailchimp subscriber data
    │
    ├── search existing MCP tools → no Mailchimp tool found
    │
    ├── Forge: search registry (500+ APIs) → Mailchimp API found
    │
    ├── Forge: generate MCP server
    │   → TypeScript MCP server with validated tool schemas
    │   → Tools: list_segments, get_subscribers, campaign_stats
    │
    ├── Register new tools with Pi agent's MCP config
    │
    ├── Execute original task using new tools
    │
    └── Reward signal: did it work?
        → +1.0: task completed with new tool
        → -0.5: tool generated but failed at runtime
```

**Weekly gap analysis:**
```
capability_gaps.db:

This week's unresolvable requests:
  "check Linear sprint progress"    → 8 occurrences
  "pull Slack channel activity"     → 5 occurrences
  "get Figma design specs"          → 3 occurrences

Top 3 gaps → trigger Forge generation:
  1. Linear MCP server (sprint, issues, labels)
  2. Slack MCP server (channels, messages, threads)
  3. Figma MCP server (files, components, comments)

After generation: capability surface grows autonomously.
Hibernation policy: tools with < 3 uses in 14 days → disabled.
```

### Self-Evaluation

Maggy evaluates its own optimization quality on a weekly cycle:

```
┌──────────────────────────────────────────────────────────┐
│ MAGGY SELF-EVALUATION (weekly)                            │
│                                                           │
│ Efficiency trend:                                         │
│   Week 1: 2.3 tickets/day, 0.92 quality multiplier       │
│   Week 2: 2.7 tickets/day, 0.94 quality multiplier  ↑    │
│   Week 3: 3.1 tickets/day, 0.91 quality multiplier  ↑↓   │
│   Week 4: 3.0 tickets/day, 0.95 quality multiplier  →↑   │
│                                                           │
│ Adjustments this week: 6                                  │
│   ✓ Promoted kimi for test-writing (reward +0.7)          │
│   ✓ Dropped codex review for blast < 3 (reward +0.1)     │
│   ✗ Tried qwen for API routes — auto-rolled back         │
│     (reward -0.4, 2 bug escapes detected at day 12)      │
│   ✓ Pre-checkpoint moved to 40min (reward +0.3)          │
│   ✓ Added error handling to API routes (review feedback)  │
│   ✓ Enabled ruff pre-check (CI failure prevention)        │
│                                                           │
│ Process intelligence:                                     │
│   CI first-pass rate: 94% (up from 72% at week 1)        │
│   Review rounds avg: 1.3 (down from 2.8 at week 1)       │
│   CodeRabbit critical findings: 0 (down from 4 at week 1)│
│   Capability gaps filled: 2 (Linear, Slack via Forge)     │
│                                                           │
│ Auto-rollbacks this week: 1                               │
│   qwen for API routes: reverted to kimi after 3 failures  │
│                                                           │
│ Overall efficiency delta: +18% vs 4 weeks ago             │
└──────────────────────────────────────────────────────────┘
```

When an adjustment makes things worse, Maggy doesn't wait for the user to notice. It detects the reward drop and **auto-rolls back**. When an adjustment works, it reinforces and looks for similar task types to expand to.

### Exploration vs Exploitation

Maggy needs to try new things (exploration) while mostly doing what works (exploitation):

```
exploration_rate: 0.10  # 10% of tasks try a new model/workflow
                        # 90% use the current best policy

exploration_rules:
  - Never explore on blast >= 7 (too risky)
  - Never explore on security/concurrency tasks
  - Explore on docs, tests, low-blast refactors (low cost of failure)
  - If exploration succeeds 3x in a row, promote to exploitation
  - If exploration fails 2x in a row, abandon and try different hypothesis
```

### Storage

```
~/.maggy/
  reward_registry.db      # SQLite: (action, context, reward, timestamp)
  model_scores.db         # SQLite: (model, task_type, blast_tier, reward_avg, n_samples)
  workflow_scores.db      # SQLite: (workflow_step, tier, reward_avg, n_samples)
  process_patterns.db     # SQLite: (code_pattern, review_feedback, occurrences, fix_pattern)
  ci_patterns.db          # SQLite: (file, failure_type, count, flaky_rate)
  pr_patterns.db          # SQLite: (size_bucket, concern_count, avg_rounds, avg_merge_time)
  capability_gaps.db      # SQLite: (request_type, occurrences, forge_status, tool_name)
  improvement_ledger.db   # SQLite: all self-modifications with config snapshots + backtesting
  task_history.db         # SQLite: every task with L0 events, reward, CI/review outcomes
  fatigue_profile.yaml    # Learned fatigue curve for this user
  policy.yaml             # Current active policy (model routing, inbox weights, process rules)
  policy_history/         # Timestamped snapshots for rollback (also in ledger.db)
  self_eval.jsonl         # Weekly self-evaluation log
  environments/           # Auto-discovered per-project workflow configs
```

```yaml
# ~/.maggy/policy.yaml (Maggy-managed, not user-edited)
version: 47  # auto-incremented on every policy update
updated_at: "2026-05-10T03:00:00Z"

model_routing:
  blast_0_3:
    primary: qwen-local
    except:
      api_routes: kimi          # learned: qwen bad at API routes
      auth: claude              # override: security dimension >= 2
  blast_4_6:
    primary: kimi
    post_review: true           # high-tier spot check on output
  blast_7_10:
    primary: claude
    fallback: gpt-4o
    counter_check: codex        # dual-model planning

inbox_weights:
  urgency: 0.30
  okr_alignment: 0.20
  recency: 0.15
  type:
    security: 1.8
    bug: 1.2
    feature: 1.0
    docs: 0.6
  project:
    zensurveys-backend: 1.3     # learned: user prioritizes this project
    chief-of-staff: 1.0
    rodcast: 0.8

workflow:
  codex_counter_check:
    enabled_above_blast: 5      # learned: no value below 5
  pre_checkpoint_minutes: 40    # learned: user's fatigue curve
  exploration_rate: 0.10

process:
  pre_commit_checks:
    ruff: true                     # learned: CI catches these
    mypy: true                     # learned: type errors in CI
    test_coverage_min: 80          # learned: PRs without coverage rejected
  pr_strategy:
    max_lines: 400                 # learned: optimal for this team
    stacked_prs: true              # learned: faster merge for large changes
    require_tests: true            # learned: #1 review comment is "add tests"
  review_prevention:               # patterns learned from reviewer feedback
    error_handling_api_routes: true
    transaction_multi_writes: true
    edge_case_tests: true
  coderabbit_precheck:             # patterns learned from CodeRabbit
    security_scan: true
    unused_imports: true
  scheduling:
    avoid_friday_auth_prs: true    # learned: Friday auth PRs take 2x to merge
  forge:
    auto_expand: true              # generate new MCP tools for capability gaps
    hibernation_days: 14           # disable unused forge tools after 14 days
    min_gap_requests: 5            # require 5+ requests before triggering forge
```

### Optimization Targets Mapped to Control Levels

Each optimization target from Sections 1-6 now maps to a specific control level:

| Target | L0 (seconds) | L1 (minutes) | L2 (hours) | L3 (days) | L4 (weeks) |
|--------|:---:|:---:|:---:|:---:|:---:|
| **1. Model routing** | Switch on failure/fatigue | Update (model,task,tier) score | Disable failing model | Adjust tier boundaries | Recalibrate blast→tier map |
| **2. Inbox ordering** | — | — | — | Adjust type/project weights | Reweight signals |
| **3. Workflow steps** | — | Log step value for task | — | Enable/disable steps by tier | Add/remove signal types |
| **4. Fatigue** | Checkpoint on threshold | Update fatigue profile | — | Adjust checkpoint timing | Tune L0 thresholds |
| **5. Process intelligence** | Lint before commit | Log CI/review signals | Toggle pre-checks | Evolve skills from patterns | Recalibrate process signals |
| **6. Capability expansion** | — | Log capability gap | — | Forge top 3 gaps | Prune/archive unused tools |

**L0 handles stability** (don't let a task fail). **L1-L2 handle health** (don't let bad patterns accumulate). **L3-L4 handle strategy** (make the system smarter over time).

### Improvement Ledger — Full Auditability + Backtesting

Every self-modification Maggy makes is recorded in the improvement ledger with full state snapshots. This serves three purposes: auditability (what changed and why), rollback (revert any change), and **backtesting** (would a policy have worked better on historical data?).

#### Ledger Schema

```sql
-- ~/.maggy/improvement_ledger.db
CREATE TABLE modifications (
    id              INTEGER PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    control_level   INTEGER NOT NULL,  -- 0-4
    category        TEXT NOT NULL,     -- model_routing, process, workflow, etc.
    description     TEXT NOT NULL,     -- human-readable what changed
    reasoning       TEXT NOT NULL,     -- why the change was made (signal data)
    config_before   TEXT NOT NULL,     -- full policy.yaml snapshot (JSON)
    config_after    TEXT NOT NULL,     -- full policy.yaml snapshot (JSON)
    score_before    REAL,             -- avg reward in measurement window before
    score_after     REAL,             -- avg reward in measurement window after
    delta           REAL,             -- score_after - score_before
    status          TEXT DEFAULT 'active',  -- active, rolled_back, superseded
    rolled_back_at  TEXT,             -- timestamp if reverted
    rollback_reason TEXT              -- why it was reverted
);

CREATE TABLE task_history (
    id              INTEGER PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    project         TEXT NOT NULL,
    task_type       TEXT NOT NULL,     -- auth, api_route, test, docs, etc.
    blast_tier      INTEGER NOT NULL,  -- 0-10
    model_used      TEXT NOT NULL,
    policy_version  INTEGER NOT NULL,  -- which policy was active
    l0_events       TEXT NOT NULL,     -- JSON array of L0 signals
    l1_reward       REAL NOT NULL,     -- computed task reward
    ci_passed       BOOLEAN,
    review_rounds   INTEGER,
    coderabbit_findings INTEGER,
    time_to_merge_h REAL,
    reverted        BOOLEAN DEFAULT FALSE,
    bug_escape      BOOLEAN DEFAULT FALSE
);
```

#### Backtesting: "Would This Policy Have Worked?"

Before deploying a L3/L4 policy change, Maggy can **replay historical tasks** against the proposed policy to predict the outcome:

```
┌──────────────────────────────────────────────────────────────┐
│  BACKTEST: proposed policy v48 vs current policy v47          │
│                                                               │
│  Replaying 200 tasks from last 30 days...                     │
│                                                               │
│  Proposed change: route blast 3 tasks to qwen instead of kimi │
│                                                               │
│  Historical tasks at blast 3 (n=47):                          │
│    Under kimi (actual):                                       │
│      avg reward: +0.62                                        │
│      CI pass rate: 91%                                        │
│      review rounds: 1.4                                       │
│                                                               │
│    Under qwen (backtest simulation):                          │
│      predicted reward: +0.38  ← LOWER                         │
│      predicted CI pass rate: 78%  ← based on qwen's L0 data  │
│      predicted review rounds: 2.1 ← based on qwen's L1 data  │
│                                                               │
│  VERDICT: DO NOT APPLY — backtest predicts -0.24 reward drop  │
│                                                               │
│  Alternative explored: route blast 1-2 to qwen, keep 3 on    │
│  kimi. Backtest on blast 1-2 tasks (n=31):                    │
│    kimi actual: +0.58                                         │
│    qwen predicted: +0.71  ← HIGHER (simpler tasks = qwen OK) │
│                                                               │
│  VERDICT: APPLY partial — blast 1-2 to qwen, blast 3 stays   │
└──────────────────────────────────────────────────────────────┘
```

**How backtesting works:**

1. **Query `task_history`** for all tasks matching the target criteria (e.g., blast tier, task type)
2. **For each historical task**, look up the proposed model's performance on similar `(task_type, blast_tier)` combinations from `model_scores.db`
3. **Predict reward** using the proposed model's historical L0 signals (failure rate, lint errors, test pass rate) on similar tasks
4. **Compare** predicted vs actual reward across the full set
5. **Decision**: apply if predicted delta > +0.1, reject if < -0.1, flag for exploration if between

**Backtesting is required for L3 and L4 changes.** L0-L2 changes are reactive (stability and health) and don't need backtesting — they respond to immediate signals. L3-L4 changes are strategic and can be validated against historical data first.

#### Auto-Seeding: Maggy Bootstraps Herself

Maggy has Pi agents. She has access to Claude, Codex, Kimi, Qwen — whatever models are configured. There is no reason for a manual `maggy seed` command. The moment a project is registered in `~/.maggy/projects.yaml`, Maggy spawns a Pi agent to analyze the project's history and seed her own databases. No user action required.

```
┌──────────────────────────────────────────────────────────────┐
│  AUTO-SEED (triggered on project registration)                │
│                                                               │
│  1. Maggy detects new project in registry                     │
│     │                                                         │
│  2. Spawns Pi agent (cheapest available model — qwen/kimi)    │
│     Task: "Analyze project history and extract patterns"      │
│     │                                                         │
│  3. Agent executes via gh CLI + git log:                      │
│     │                                                         │
│     ├── gh pr list --state merged --limit 200 --json          │
│     │   → PR sizes, review rounds, time-to-merge              │
│     │   → Reviewers, approval patterns                        │
│     │                                                         │
│     ├── gh pr view {n} --comments --json                      │
│     │   → Review comments categorized by pattern              │
│     │   → CodeRabbit findings by severity + category          │
│     │   → Bot authors detected (coderabbitai, dependabot)     │
│     │                                                         │
│     ├── gh api repos/{owner}/{repo}/actions/runs              │
│     │   → CI pass/fail rates per workflow                     │
│     │   → Failure patterns per file                           │
│     │   → Flaky test detection                                │
│     │                                                         │
│     ├── git log --format='%H %s' --since='6 months ago'       │
│     │   → Revert detection (commit messages with "revert")    │
│     │   → Commit patterns, branch naming conventions          │
│     │                                                         │
│     ├── codebase-memory-mcp: get_architecture + search_graph  │
│     │   → Module structure, hot files, dependency depth       │
│     │   → Fan-out scores for initial blast radius calibration │
│     │                                                         │
│     └── Environment discovery (Section 5a)                    │
│         → Ticketing, CI, lint, review process auto-detected   │
│                                                               │
│  4. Agent writes structured analysis to Maggy's databases:    │
│     process_patterns.db: seeded with review comment patterns  │
│     ci_patterns.db: seeded with CI failure history            │
│     pr_patterns.db: seeded with merge velocity data           │
│     task_history.db: synthetic entries from git log           │
│     environments/{project}.yaml: workflow config              │
│                                                               │
│  5. Agent computes initial policy.yaml from patterns:         │
│     → "PRs > 400 lines take 3x review rounds → set max 400"  │
│     → "ruff failures in 40% of PRs → enable pre-check"       │
│     → "auth files have 0% CI failures → low risk"            │
│     → "CodeRabbit flags unused imports 60% of PRs → pre-fix" │
│                                                               │
│  6. Maggy logs seed as modification #1 in improvement_ledger  │
│     config_before: empty (default policy)                     │
│     config_after: data-derived initial policy                 │
│     score_before: null (no baseline)                          │
│     → All future modifications measured against this seed     │
│                                                               │
│  Total cost: ~$0.10-0.50 on a cheap model (one-time)          │
│  Total time: background task, user doesn't wait               │
│  User action required: zero                                   │
└──────────────────────────────────────────────────────────────┘
```

**Why this works:** The seed analysis is exactly the kind of task cheap models are good at — structured data extraction, pattern counting, statistical aggregation. No creative reasoning needed. Qwen local can do it for free. And the Pi agent already has all the tools: `gh` CLI for GitHub data, `git` for history, codebase-memory-mcp for structural analysis.

**Why manual seed is wrong:** Maggy's entire philosophy is autonomous optimization. A `maggy seed --project foo` command implies the user knows they need to seed, knows the right flags, and remembers to run it. That's three failure points. Maggy should behave like a new hire who reads the project's git history on their first day — automatically, without being told.

**Multi-project seed:** When Maggy is first installed with 4 projects in the registry, she spawns 4 seed agents in parallel (one per project, each in its own Polyphony container). All 4 seed concurrently. By the time the user opens the dashboard, Maggy already knows:
- zensurveys-backend: "PRs to auth/ need 2 reviewers, ruff fails on 40% of pushes"
- zensurveys-frontend: "CodeRabbit catches unused imports, avg PR is 180 lines"
- chief-of-staff: "No CI, manual deploys, review optional"
- rodcast: "New project, minimal history — start with defaults"

**Validation before real work:** The seed data lets Maggy prove her value immediately. On the dashboard, day 1:

```
┌──────────────────────────────────────────────────────────────┐
│  MAGGY — Day 1 Analysis (auto-generated from project history)│
│                                                               │
│  zensurveys-backend (200 PRs analyzed):                       │
│    Current process health:                                    │
│      CI first-pass rate: 72%                                  │
│      Avg review rounds: 2.8                                   │
│      Top review comment: "add error handling" (23 times)      │
│      Avg time-to-merge: 36h                                   │
│                                                               │
│    Predicted improvements if Maggy had been active:           │
│      CI first-pass rate: 72% → ~94% (pre-lint + pre-type)    │
│      Review rounds: 2.8 → ~1.4 (auto error handling + tests) │
│      Time-to-merge: 36h → ~12h (smaller PRs + fewer rounds)  │
│                                                               │
│    Based on: patterns from your last 200 PRs                  │
│    Confidence: high (200+ data points per pattern)            │
└──────────────────────────────────────────────────────────────┘
```

That's the mWp for onboarding. Maggy doesn't say "configure me." She says "I already analyzed your project. Here's what I found. Here's what I'll fix. Watch."

#### Ledger Queries — "How Did Maggy Improve Itself?"

```sql
-- Show all modifications, most recent first
SELECT timestamp, control_level, category, description, delta, status
FROM modifications ORDER BY timestamp DESC LIMIT 20;

-- Show rolled-back changes (what went wrong?)
SELECT timestamp, description, delta, rollback_reason
FROM modifications WHERE status = 'rolled_back';

-- Show cumulative improvement over time
SELECT date(timestamp) as day,
       sum(CASE WHEN delta > 0 THEN delta ELSE 0 END) as positive_delta,
       sum(CASE WHEN delta < 0 THEN delta ELSE 0 END) as negative_delta,
       sum(delta) as net_delta
FROM modifications
GROUP BY day ORDER BY day;

-- Show which control level produces the most value
SELECT control_level,
       count(*) as modifications,
       avg(delta) as avg_delta,
       sum(CASE WHEN status = 'rolled_back' THEN 1 ELSE 0 END) as rollbacks
FROM modifications
GROUP BY control_level;

-- Backtest: what would policy v48 have scored on last month's tasks?
SELECT task_type, blast_tier,
       avg(l1_reward) as actual_reward,
       count(*) as n_tasks
FROM task_history
WHERE policy_version = 47
  AND timestamp > date('now', '-30 days')
GROUP BY task_type, blast_tier;
```

### The Wow Factor

Maggy after 4 weeks:

> "I didn't configure anything. I didn't set weights. I didn't tell it which model to use for what. It figured out that Claude is best for my auth code, Kimi writes my tests, and Qwen handles docs — by itself. It tried routing API routes to Qwen once, caught that it was producing bugs, and rolled it back before I even noticed. It knows I fatigue at 42 minutes and checkpoints at 40. My throughput is up 30% and my bug escape rate is down. I don't manage Maggy. Maggy manages my development."

> "But the thing that blows me away is the process improvement. Maggy figured out that my team's reviewers always flag missing error handling on API routes — so now it adds error handling by default. It learned that our CI lint step fails on long lines — so it runs ruff before pushing. Our CodeRabbit findings dropped to zero. PRs that used to take 3 review rounds now merge on the first. And when I needed to pull data from Linear, Maggy generated a whole MCP integration on the fly — I didn't even know that was possible. It's not just writing better code. It's making the entire pipeline faster."

That's the mWp. Not a tool. Not an assistant that asks questions. An autonomous system that optimizes itself with one goal: make its human as efficient as possible.

---

## 12. Codex Review Response

Codex (GPT-5.4) reviewed this architecture. Full review: `docs/codex-review-v5.md`. Summary of decisions:

### Accepted

| Finding | Our Response |
|---------|-------------|
| Blast radius is overloaded as routing signal | Correct. Updated to use full 5-dimension iCPG scoring (cyclomatic, fan_out, security, concurrency, domain) with dimension overrides for security/concurrency. |
| Low-tier output needs stronger verification | Added high-tier post-review gate, iCPG constraint assertions, and static analysis for all cheap-model output. |
| Self-improving loop needs guardrails | Added cold-start thresholds (50+ data points), 30-day decay windows, delayed outcome tracking, audit log, and user-approval for adaptations. |
| CIKG + iCPG need shared decision schema | Accepted. Will define cross-graph artifact types (Requirement, Decision, Hypothesis, Evidence, Risk, Outcome) in Phase 4. |
| Observability is missing | Accepted. Adding to Phase 8: structured event log for agent decisions, bridge translations, model switches, and tool actions. |
| Model switching should be explicit handoff | Updated fallback chain to include checkpoint + verification step before continuing on new model. |

### Rejected (Codex was wrong on these)

| Codex's Claim | Why We Disagree |
|---------|-----|
| Split-brain control model | Not a split-brain. Mnemos + iCPG provide shared persistent state on disk inside the container. Coordination agent and execution agent own distinct concerns with shared persistence. No duplicated state. |
| Pi is a dangerous universal dependency | Partially rejected. Pi is the right choice for adapter unification, but we accept the recommendation to keep an internal execution contract and preserve direct adapters as fallback for critical paths. |
| Browser-container deploy is over-engineered | Rejected for our use case. The user has a specific pain point: 4 projects on Vercel with auth conflicts when using `vercel login` locally. Browser containers solve this directly. API/CLI deploy is the primary path; browser containers solve the auth isolation problem specifically. |
| Self-improving Maggy is unrealistic | Rejected. Maggy is an autonomous optimization agent, not a suggestion engine. It uses a reward registry with positive/negative signals, auto-rollback on reward drops, exploration/exploitation balance (10% exploration on low-risk tasks only), and weekly self-evaluation. Cold start uses hardcoded defaults until 30+ samples. No user approval needed — the reward function is the judge. |

---

## 13. Open Questions

1. **CIKG extraction scope** — Extract just the graph service, or the full strategy pipeline (daily briefing, trend monitoring)?
2. **Pi extension authoring** — Do we write custom Pi extensions for iCPG/Mnemos hooks, or keep them as shell scripts?
3. **Vercel deploy frequency** — On every PR, or manual trigger from Maggy?
4. **Local model quality floor** — Minimum benchmark Qwen must pass before routing low-blast tasks to it?
5. **Cross-project dependencies** — codebase-memory-mcp can trace HTTP_CALLS across project graphs. When zensurveys-backend changes a Route, should Maggy auto-create a task in zensurveys-frontend? The graph data is there (36 projects indexed); the question is the automation policy.
