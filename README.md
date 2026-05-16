# Maggy

> **From Claude Bootstrap to autonomous AI engineering.**

This project started as **Claude Bootstrap** — an opinionated set of skills, hooks, and rules for Claude Code. Over time it grew into something much bigger: a multi-model routing system, a persistent memory layer, an intent-tracking code graph, container-based orchestration, and a full engineering command center. The bootstrap scaffolding is still here, but the future of this project is **Maggy** — an autonomous engineering system that routes work across AI models, learns from outcomes, and manages the full development lifecycle.

We ship [**mWP**](docs/mwp.md) (minimum wowable product, 5-7 on the 11-star scale), not MVP. Every feature should make you think "I need this" — not just "it works."

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
| **Explore** | iCPG-powered code explorer | `trace_path`, `search_graph`, `query_graph` instead of grep |
| **Routing** | Plan-vs-execute classifier | CLAUDE tier → PLAN FIRST. DEEPSEEK/GEMINI → EXECUTE DIRECTLY |
| **Plugins** | Event-driven plugin system | Drop folder into `~/.maggy/plugins/`, auto-discovered on startup |

## Plugin System

Maggy has an [mWP](docs/mwp.md)-first plugin architecture. Drop a folder with `plugin.yaml` + `plugin.py` into `~/.maggy/plugins/` or `plugins/` — it's auto-discovered and loaded at startup. Works standalone with Claude Bootstrap (no Maggy server needed).

```yaml
# plugin.yaml
id: my-plugin
version: 1
entrypoint: plugin.py
hooks:
  - event: on_pr_merged
    handler: handle_pr_merged
  - event: on_feature_shipped
    handler: handle_feature_shipped
```

**First plugin: Build-in-Public** — autonomous storyteller that notices your work, synthesizes a narrative, and publishes across channels without you asking.

```
PR merged → AI extracts narrative arc → anonymizes sensitive names
→ formats per channel (LinkedIn teaches, X punches)
→ schedules via Buffer API
```

- **Multi-channel**: LinkedIn (professional deep dives) + X (sharp one-liners) — different voice per platform
- **Auto-redaction**: `anonymize.yaml` replaces company names, strips revenue/user data
- **AI-powered**: DeepSeek synthesizes the story — not templates
- **Zero-click**: Triggers from hooks, never asks for manual approval

See `skills/build-in-public/SKILL.md` for channel best practices.

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

Every AI coding tool loses context on compaction. The difference is whether it prevents failure or just reacts to it.

**Codex** compaction is an opaque encrypted blob triggered by a single token counter. When it misfires, the agent enters documented "death spirals" — up to 26 compactions per session, re-reading the same files 10-20×, burning 160M+ tokens on work that used to cost 89M. No telemetry surfaces *why* compaction fired. No memory survives the session.

**Claude Code** uses 9-section XML summarization at a hardcoded ~95% token threshold. The summary is opaque to the user, discard decisions are invisible, and critical context (active errors, file contents) is silently dropped. No cross-session recall, no team context, no signal that the agent is struggling *before* the summary happens.

**Maggy Mnemos** treats memory as a typed graph where goals and constraints are never evicted, while ephemeral context decays by relevance. A 4-dimension fatigue model (token pressure, scope scatter, reread ratio, error density) triggers consolidation *early* — in the COMPRESS state at 40-60% load, long before a death spiral. Mnemos measures **re-read ratio** explicitly — the leading indicator of a compaction death spiral. When the agent starts re-reading files it already read, fatigue rises and consolidation triggers *before* the context window is full. Every eviction decision is auditable in SQLite. Cross-session memory via Engram.

| | Codex | Claude Code | Maggy (Mnemos) |
|---|---|---|---|
| **Compaction trigger** | Configurable token threshold, blind to workload | Hardcoded ~95% token threshold, blind | **4-dimension fatigue score** — token-aware but not token-blind |
| **What survives** | Opaque AES-encrypted blob (both paths) | 9-section XML summary | **Typed memory nodes** with per-type eviction (goals/constraints never evicted) |
| **Transparency** | Zero — cannot audit the summary | Readable but discard decisions invisible | **Fully auditable** — SQLite + JSONL, every node and eviction on disk |
| **Death spiral prevention** | None — known to compact for hours | None — no pre-failure signal | **Re-read ratio + fatigue scoring** triggers consolidation at 40-60%, before the window is full |
| **Cross-session memory** | None | None | **Engram store** — typed, queryable, persists across sessions |
| **Pre-compaction safety** | None — compacts reactively | None | **Checkpoint written before compaction** — critical nodes survive even if compaction fails |

## Routing: Maggy vs. the Landscape

Every AI tool claims to pick the right model. Here's how they actually compare:

| | OpenRouter | Martian | Portkey | Semantic Router | **Maggy** |
|---|---|---|---|---|---|
| **Approach** | Performance-based, user-defined fallbacks | LLM-as-Classifier, trained router model | Gateway: retries, load balancing, rule-based | Embedding similarity, pre-defined routes | **LLM-as-Classifier with cascading fallback** |
| **Classification cost** | None (user picks) | API call (~$0.001) | None (rule-based) | None (embeddings) | **$0 (local qwen3)** |
| **Classifier resilience** | N/A | Single point of failure | N/A | N/A | **Cascade: qwen3 → kimi → deepseek → cache** |
| **Fatigue-aware** | No | No | No | No | **Yes — 4-dimension fatigue, PRE_SLEEP/REM escalation** |
| **Mid-task switching** | No | No | No | No | **Checkpoint-based state transfer (in progress)** |
| **Memory-aware** | Token count only | No | Token count only | No | **Semantic: typed nodes, per-type eviction, re-read ratio** |
| **Self-learning** | No | No | No | No | **Per-project routing profiles with success/failure tracking** |

**Three things only Maggy has:**

1. **Fatigue-aware routing** — nobody routes based on agent state. When Mnemos detects PRE_SLEEP (0.60), Maggy skips cheap tiers. At REM (0.75), it forces premium models. OpenRouter can't do this. Martian can't. No paper proposes it.

2. **Cascading classifier resilience** — every other router has a single point of failure. If Martian's classifier is down, routing stops. Maggy cascades through qwen3 → kimi → deepseek-flash → cached tier. The classifier itself is multi-model.

3. **Semantic memory, not token counting** — Portkey checks `token_count > 8000` to switch context windows. Maggy tracks what KIND of memory matters: goals survive compaction, error traces decay, code-refs persist. Routes based on semantic importance, not a counter.

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
