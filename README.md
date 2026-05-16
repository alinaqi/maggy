# Maggy

> **From Claude Bootstrap to autonomous AI engineering.**

This project started as **Claude Bootstrap** — an opinionated set of skills, hooks, and rules for Claude Code. Over time it grew into something much bigger: a multi-model routing system, a persistent memory layer, an intent-tracking code graph, container-based orchestration, and a full engineering command center. The bootstrap scaffolding is still here, but the future of this project is **Maggy** — an autonomous engineering system that routes work across AI models, learns from outcomes, and manages the full development lifecycle.

62 skills, TDD enforcement via Stop hooks, agent teams, persistent memory (Mnemos), intent tracking (iCPG), and multi-model AI command center. Works with **Claude Code**, **Kimi CLI**, and **OpenAI Codex CLI**.

## Quick Start

```bash
git clone https://github.com/alinaqi/maggy.git
cd maggy && ./install.sh

# In any project directory
claude
> /initialize-project
```

Claude will validate tools, ask about your stack, create the repo structure, copy skills/rules/hooks, and spawn an agent team.

## Maggy — Autonomous Engineering System

Maggy is the core of this project. It routes tasks across models, tracks performance, learns from outcomes, and manages the full development lifecycle from a local dashboard or CLI REPL.

- **Multi-model routing** — semantic blast scoring routes tasks across Claude/Codex/Kimi/Ollama based on complexity, cost, and proven performance
- **Task blueprints** — self-learning workflows; Maggy captures tool sequences from successful tasks and replays them with cheaper models
- **Chat** — interactive sessions with markdown rendering, streaming, session persistence, and file upload
- **Execute** — one-click TDD pipeline with iCPG context enrichment
- **Tasks** — AI-prioritized inbox from GitHub Issues or Asana
- **Competitors** — auto-discovered competitors + daily AI briefing
- **Insights** — CLI session analysis, health signals, reviewer evaluation
- **Reviewer knowledge map** — tracks which reviewer (CodeRabbit, Codex, local) is best at which finding category

```bash
cd maggy && pip install -e .
maggy serve   # dashboard at localhost:8080
maggy         # CLI REPL (runs from any project directory)
```

See [maggy/README.md](./maggy/README.md) for setup and routing details.

## Bootstrap Layer

The original scaffolding that sets up any project for AI-assisted development:

| Layer | What | Why |
|-------|------|-----|
| **Skills** | 62 skills loaded via `@include` in CLAUDE.md | Language, framework, security, AI patterns |
| **Rules** | Conditional rules (activate by file path) | Quality gates, TDD workflow, security — only when relevant |
| **Hooks** | Stop hooks for TDD loops | Tests run after every Claude response, failures feed back automatically |
| **Agents** | Team Lead + Quality + Security + Review + Merger + Feature | Coordinated pipeline: spec → test → implement → review → PR |
| **Memory** | Mnemos (typed graph on disk) | Survives compaction, crashes, restarts |
| **Intent** | iCPG (code property graph) | Tracks *why* code exists, detects drift |

## Skills (62)

**Core** — TDD, memory, intent tracking, code review, agent teams, security, commit hygiene, cross-agent delegation, Polyphony orchestration

**Languages** — Python, TypeScript, Node.js, React, React Native, Android (Java/Kotlin), Flutter

**Databases** — Supabase, Firebase, Cloudflare D1, DynamoDB, Aurora, Cosmos DB

**AI** — Agentic development, LLM patterns, AI models reference

**UI** — Web (Tailwind), mobile, visual testing, Playwright, PWA

**Integrations** — Stripe, Reddit, Shopify, WooCommerce, Medusa, Klaviyo, Teams, PostHog

See [full skills catalog](./docs/claude-bootstrap-reference.md#skills-catalog-62-skills) for details.

## Cross-Tool Compatibility

| Feature | Claude Code | Kimi CLI | Codex CLI | DeepSeek V4 |
|---------|-------------|----------|-----------|-------------|
| Skills | `.claude/skills/` | `.kimi/skills/` | `.codex/skills/` | via Claude Code |
| Instructions | `CLAUDE.md` | (uses skills) | `AGENTS.md` | via Claude Code |
| Memory | 9-section XML summary | None | Encrypted blob / text summary | **Mnemos typed graph** |
| Routing | Manual | Manual | Manual | **6-tier auto-routing** |

`install.sh` auto-detects installed tools. `/sync-agents` syncs config across tools on demand.

## Memory: Mnemos vs. Codex vs. Claude Code

Every AI coding tool loses context on compaction — how it loses it and what survives defines the ceiling on session quality. Here's how Maggy's Mnemos differs:

| | Codex | Claude Code | Maggy (Mnemos) |
|---|---|---|---|
| **Compaction trigger** | Token threshold (~167K of 200K), blind | Token threshold, blind | **4-dimension fatigue** (token utilization, scope scatter, reread ratio, error density) |
| **What's preserved** | Encrypted blob (OpenAI models) or 4-point text summary | 9-section XML summary | **Typed memory nodes** with per-type eviction policies (code-refs survive longer than error traces) |
| **Transparency** | Zero (fast path is opaque AES-encrypted) | Readable but lossy | **Fully auditable** — every node type, eviction, and checkpoint is on disk |
| **Recursive degradation** | Known death spirals (compacts for hours before producing) | Same — no telemetry | **Fatigue score surfaces degradation before death spirals** — compacts semantically, not blindly |
| **Cross-session memory** | Per-user, non-editable | None | **Typed, queryable, cross-project** — Engram store persists across sessions |
| **Team memory** | None — no pooling across teammates | None | **Shared via Engram** — accumulated context available to new team members |
| **Pre-compaction safety** | None — compacts reactively | None | **Checkpoint written before compaction** — critical nodes survive even if compaction fails |

**Codex** compacts like a senior engineer tearing up drafts and writing a status report — effective but irreversible, and you can't audit the summary. **Claude Code** gives you readable summaries but nothing persists across sessions. **Maggy** tracks *why* each memory node exists, applies per-type eviction, and surfaces fatigue before degradation begins.

## Core Concepts

**TDD via Stop Hooks** — tests run after every Claude response. Failures feed back automatically. No plugins needed. [Details →](./docs/claude-bootstrap-reference.md#tdd-loops-via-stop-hooks)

**Mnemos Memory** — typed graph on disk (goals, constraints, results, context). Survives compaction, crashes, multi-agent failures. 4-dimension fatigue model writes checkpoints *before* things go wrong. [Details →](./docs/claude-bootstrap-reference.md#mnemos--task-scoped-memory)

**iCPG Intent Tracking** — links every code change to a ReasonNode with intent, postconditions, and invariants. 6-dimension drift detection. [Details →](./docs/claude-bootstrap-reference.md#icpg--intent-augmented-code-property-graph)

**Agent Teams** — 6 agents with enforced pipeline (spec → test → implement → review → security → PR). Only Feature agents can edit code. [Details →](./docs/claude-bootstrap-reference.md#agent-teams)

## Usage

```bash
# New project
mkdir my-app && cd my-app
claude
> /initialize-project

# Existing project
cd my-existing-app
claude
> /initialize-project    # auto-detects existing code

# Update skills globally
cd "$(cat ~/.claude/.bootstrap-dir)"
git pull && ./install.sh
```

## Docs

- [Full reference](./docs/claude-bootstrap-reference.md) — TDD hooks, Mnemos, iCPG, agent teams, skills catalog, evolution
- [Maggy reference](./maggy/docs/maggy-reference.md) — CLI commands, REPL, routing, dashboard, architecture
- [Architecture v5](./maggy/docs/architecture-v5.md) — Full system architecture
- [Polyphony spec](./maggy/docs/polyphony-spec.md) — Container orchestration
- [Changelog](./CHANGELOG.md) — Version history

## License

MIT — See [LICENSE](LICENSE)

---

**Need help scaling AI in your org?** [Claude Code & MCP experts](https://leanai.ventures/aiops/claude)
