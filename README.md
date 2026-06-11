# Claude Bootstrap + Maggy

> **Turn Claude Code into a self-reviewing, test-enforced engineering system that remembers context across sessions — then route work across 13 models from a single dashboard.**

Claude Bootstrap is an installable config pack (skills, hooks, rules, templates) for Claude Code. Maggy is the optional local server that adds multi-model routing, a web dashboard, intent-driven protocols, and plugin orchestration. Both live in this repo. Start with Bootstrap; add Maggy when you need the harness.

[![Tests](https://img.shields.io/badge/tests-1100%2B%20passing-brightgreen)](maggy/tests/)
[![Version](https://img.shields.io/badge/version-6.37.0-blue)](CHANGELOG.md)
[![Stars](https://img.shields.io/github/stars/alinaqi/maggy)](https://github.com/alinaqi/maggy/stargazers)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**1100+ tests. 67 skills. 15 MCP tools. Used daily across production codebases.**

---

## Who This Is For

- **Solo engineers** using Claude Code who want TDD enforcement, quality gates, and memory that survives context compaction — without changing their workflow
- **Teams** routing work across Claude, DeepSeek, Kimi, Gemini, and Codex from a single dashboard with cost-aware model selection
- **Platform engineers** building AI-assisted developer tooling who need a reference implementation with intent tracking, protocol execution, and plugin architecture

---

## Choose Your Path

| | Claude Bootstrap | Maggy Harness |
|---|---|---|
| **What it is** | Skills, hooks, rules installed into `~/.claude/` | Local FastAPI server + web dashboard |
| **Install time** | ~30 seconds | ~5 minutes (Python 3.11+, API keys) |
| **Requires** | Claude Code (also works with Codex, Kimi, Gemini CLI) | Everything in Bootstrap + Python + optional Docker |
| **You get** | TDD enforcement, 67 skills, quality gates, ADR reviews, iCPG, Mnemos memory | All of Bootstrap + 13-tier routing, skill protocols, Telos testing, Cortex MCP, plugins, dashboard |

### Bootstrap — 30-second install

```bash
git clone https://github.com/alinaqi/maggy.git
cd maggy && ./install.sh
```

Your next Claude Code session picks it up automatically.

### Full Harness — zero-config

```bash
pipx install maggy-harness   # or: pip install maggy-harness
maggy bootstrap              # installs skills, hooks, ~/bin model wrappers, plugins
maggy serve                  # auto-configures from your local repos,
                             # then opens the dashboard at localhost:8080
```

(or from source: `cd maggy && ./install.sh && maggy serve`)

No API keys required to start — Maggy runs in local mode and, on first launch,
discovers your local git repos and opens the dashboard pointed at them. Add
`GITHUB_TOKEN` / `ANTHROPIC_API_KEY` later only if you want GitHub sync or
API-model features. See [GETTING_STARTED.md](GETTING_STARTED.md) for details.

---

## What It Looks Like in Practice

**Routing a task:**
```
You: "review the auth middleware for timing attacks"
→ Blast score: 8/10 (security + architecture)
→ Routed to: Claude (Tier 11)
→ ADR gate: found docs/adr/0003-jwt-strategy.md → injected as context
→ Review runs with full architectural context
```

**Skill Protocol execution:**
```
You: "push to git"
→ Intent matched: git-push protocol
→ ✅ lint       (2.1s)
→ ✅ typecheck   (4.3s)
→ ✅ tests       (11.2s)
→ ✅ stage
→ ✅ commit      [AI-generated: "fix: resolve token refresh race condition"]
→ ✅ push
```

**Fatigue-aware memory:**
```
Session fatigue: 0.61 (PRE-SLEEP)
→ Mnemos: auto-checkpoint written
→ Micro-consolidation: 3 ResultNodes compressed
→ iCPG context injected: 2 ReasonNodes, 1 constraint
→ Context freed: ~18k tokens
```

---

## The Problem This Solves

You're using Claude Code. It's impressive — but:

- It picks the most expensive model for everything, including trivial tasks
- Context fills up, state is lost, you re-explain yourself every session
- There's no enforcement: code quality, test coverage, and ADR compliance only happen if you remember to ask
- Running multiple agents on the same repo causes file conflicts
- You have no visibility into what Claude is actually doing inside your codebase

---

## What Bootstrap Gives You

| Layer | What it does |
|-------|-------------|
| **67 skills** | Python, TypeScript, React, React Native, Flutter, Supabase, Firebase, Stripe, Playwright, security, ADRs, cross-agent delegation |
| **TDD enforcement** | Stop hooks — tests must pass before Claude considers a task done |
| **Quality gates** | Max 20 lines/function, 3 params, 2 nesting levels. Enforced per file |
| **iCPG** | Intent-Augmented Code Property Graph. Stores *why* code exists. 6-dimension drift detection. Prevents duplicate implementations |
| **Mnemos** | Task-scoped memory with 4-dimension fatigue model. Survives context compaction with typed checkpoints |
| **ADR enforcement** | Non-trivial changes require an Architectural Decision Record. Missing one? Reverse-engineered from git history |
| **Agent teams** | 6 agents: Lead, Quality, Security, Review, Merger, Feature |

---

## What Maggy Adds

| System | What it does |
|--------|-------------|
| **13-Tier Routing** | Semantic blast score (1–10) routes to cheapest capable model. Local Qwen3 classifier → DeepSeek (~80% of tasks) → Kimi → Gemini → Grok → Codex → Claude. Budget-capped with auto-demotion. [Routing details](#model-routing) |
| **Skill Protocols** | YAML-defined workflows in `maggy/skills/protocols/`. "Push to git" → lint → test → stage → commit → push. Drop a `.yaml` to add your own |
| **Telos** | Testing beyond TDD. Three planes: Conformance × Validation × Integrity. A zero in any plane collapses the total score. [Details](#telos-testing-beyond-tdd) |
| **Cortex MCP** | Code intelligence: 10 edge types, cyclomatic complexity, FTS5 search, bidirectional traversal. 15 tools, single SQLite DB. [Benchmarks](cortex-mcp/docs/cortex-vs-codebase-memory.md) |
| **Polyphony** | Docker-isolated parallel agent execution. Second session auto-provisions a workspace. [Spec](maggy/docs/polyphony-spec.md) |
| **Engram** | Cross-session memory. 7 amnesia types. Persists architectural knowledge across weeks |
| **Plugins** | Drop-in system. Ships with: Build-in-Public (auto-posts to LinkedIn/X), Telos, GitHub/Asana/Monday providers |

---

## Model Routing

Every message is scored 1–10 for complexity and classified by task type. The cheapest capable model wins.

| Tier | Model | Role |
|------|-------|------|
| T0 | Qwen3 (local) | Classification, triage, free bulk ops |
| T1 | Gemini Flash-Lite | Bulk extraction, CIG pipelines |
| T2 | DeepSeek Flash | Docs, tests, scaffolding |
| T3 | Gemini Flash | Multimodal, vision, audio |
| T4 | DeepSeek Pro | Complex coding, multi-file refactors |
| T5 | Gemini CLI | Multi-file agentic coding |
| T6 | AGY | End-to-end implementation (git + code + test) |
| T7 | Kimi | Long-context analysis, routing alt |
| T8 | Gemini Pro Search | Deep research, Google grounding, 2M context |
| T9 | Grok | Competitor intel, deep reasoning |
| T10 | Codex | Bulk generation, security-sensitive tasks |
| T11 | Claude Sonnet | Quality-critical code, complex debugging |
| T12 | Claude Opus | Architecture, security review, ADR decisions |

Routing is semantic (Qwen3 as local classifier), fatigue-aware, budget-capped, and cascading.

### Gateway routing with srooter — [www.srooter.ai](https://www.srooter.ai)

We've added first-class support for **[srooter](https://www.srooter.ai)**, an Anthropic/OpenAI-compatible LLM gateway that routes your requests across models (Claude, MiniMax, DeepSeek, Kimi, Gemini, Grok, local Qwen) transparently — intent-based routing, budget caps, fallbacks, and a usage dashboard, without changing your tools.

**Recommended with Maggy, Claude Code, or Codex.** Point any of them at the gateway and your traffic is routed for you — no per-tool config:

```bash
# Claude Code (or Codex) → srooter
export ANTHROPIC_BASE_URL="https://www.srooter.ai/anthropic"   # or your local gateway
export ANTHROPIC_API_KEY="<your-srooter-key>"
claude        # now routed through srooter
```

Pick the model you "follow" once with `/model-config` — Maggy, the route-task hooks, and srooter all honor the same choice. Trivial asks stay on the cheap/local tier; real coding goes to your primary model (e.g. MiniMax-M2.5).

---

## Telos: Testing Beyond TDD

Standard TDD tells you if your code passes tests. Telos tells you if your code fulfills its *intent*.

```
IFS (Intent Fidelity Scale) = F1 × F2 × F3

F1 — Conformance:  passed / total tests            (pytest / vitest)
F2 — Validation:   drift severity                  (Cortex drift_events)
F3 — Integrity:    IF-3 orphan symbols              (no reason edges)
                   IF-4 empty contracts             (no pre/post/invariants)
                   IF-6 stale reasons               (proposed >7d, never fulfilled)
                   IF-7 scope sprawl                (reason scopes >10 files)
```

A zero in any plane collapses IFS to zero. 100% test pass rate with severe architectural drift = score of 0. This is intentional. See the [Telos RFC](https://github.com/alinaqi/alinaqi/blob/main/docs/Telos_RFC_v1.1.md).

---

## Repo Structure

```
.claude/
  skills/       # 67 skills — Python, TS, React, security, mobile, databases
  hooks/        # TDD enforcement, quality gates, Mnemos lifecycle
  rules/        # Conditional rules by file glob
  templates/    # settings.json, CLAUDE.md, ADR template, PR template

maggy/
  maggy/
    pipeline/   # Unified ChatPipeline orchestrator
    skills/     # Skill injection + YAML protocol engine
    api/        # REST API (chat, routing, plugins, pipeline logs)
    static/     # Web dashboard (vanilla JS, no build step)
    services/   # Routing, memory, execution, Mnemos

cortex-mcp/     # Code intelligence MCP server
  src/cortex/
    structure/  # AST extraction, edge types, complexity
    storage/    # SQLite graph store, FTS5 index

plugins/        # Drop-in plugins (build-in-public, telos, providers)
```

---

## Tests

```bash
cd maggy && python3 -m pytest tests/ -x -q        # 900+ tests
cd cortex-mcp && python3 -m pytest tests/ -q       # 207 tests
```

---

## What's New in v6.37

- **Skill Protocols** — YAML intent-driven workflows. "Push to git" runs lint → test → commit → push automatically
- **Unified Pipeline** — single ChatPipeline orchestrator with real-time streaming, fallback, per-request logging
- **Telos** — intent-grounded testing with IFS scoring on every project open
- **Cortex MCP** — modular edge extraction (Python AST, TypeScript, Git co-change). Elixir support
- **13-Tier Routing** — AGY, Gemini CLI, and Grok added to the routing ladder

See [CHANGELOG.md](CHANGELOG.md) for full history.

---

## Docs

| | |
|---|---|
| [Getting Started](GETTING_STARTED.md) | Installation, prerequisites, first session walkthrough |
| [Architecture v5](maggy/docs/architecture-v5.md) | System design, routing, dashboard |
| [CLI Reference](maggy/docs/maggy-reference.md) | REPL commands, slash commands, routing |
| [Telos RFC](https://github.com/alinaqi/alinaqi/blob/main/docs/Telos_RFC_v1.1.md) | Intent-grounded testing spec |
| [Cortex docs](cortex-mcp/docs/) | Code intelligence, edge types, MCP tools |
| [Cortex benchmarks](cortex-mcp/docs/cortex-vs-codebase-memory.md) | Performance vs codebase-memory-mcp |
| [Changelog](CHANGELOG.md) | Version history (current: v6.37.0) |

---

## Contributing

Skill PRs welcome. All skills run through the linter before merge:

```bash
PYTHONPATH=scripts python3 -m skill_lint --fail-on error skills/your-skill/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the quality gate checklist.

---

## License

MIT — See [LICENSE](LICENSE)

---

*Need help scaling AI engineering in your org? [LeanAI Ventures — Claude Code & MCP specialists](https://leanai.ventures/aiops/claude)*
