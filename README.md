# Maggy

Autonomous AI engineering command center. Route work across 13 model tiers, execute intent-driven protocols, and test beyond TDD — from a single local dashboard.

## What This Is

Maggy is two things in one repo:

1. **Claude Bootstrap** — 67 skills, TDD hooks, quality gates, and security rules that install into Claude Code (and Codex/Kimi/Gemini CLI) in 30 seconds
2. **Maggy Harness** — a local FastAPI server that adds multi-model routing, chat sessions, skill protocols, pipeline logging, and a web dashboard on top

They work independently or together. Bootstrap is zero-config. Maggy adds the harness layer for engineers who want to steer multiple AI agents from one place.

## Core Systems

| System | What it does |
|--------|-------------|
| **Routing** | Semantic blast-score rates task complexity (1-10), routes to cheapest capable model. DeepSeek handles ~80% of work. Claude reserved for architecture/security |
| **Skill Protocols** | YAML workflows that match user intent and execute steps. "Push to git" → lint → test → stage → commit → push. Extensible by dropping a `.yaml` file |
| **Unified Pipeline** | Single `ChatPipeline` orchestrator for Claude, DeepSeek, Kimi, Gemini, Codex. Real-time streaming, fallback, per-request logging |
| **Telos** | Intent-grounded testing. Three planes: Conformance, Validation, Integrity. IFS = F1 x F2 x F3 — a zero in any plane collapses the score |
| **Cortex MCP** | Code intelligence server. Structure (AST), Intent (iCPG), Memory (Mnemos). 15 tools, single SQLite DB, 66x faster incremental reindex |
| **Plugins** | Drop-in `plugin.yaml` + `plugin.py`. Ships with build-in-public, Telos, GitHub/Asana/Monday providers |

## Quick Start

```bash
git clone https://github.com/alinaqi/maggy.git
cd maggy && ./install.sh        # Bootstrap only (30s)

# For the full harness:
cd maggy && pip install -e .
maggy serve                     # Dashboard at localhost:8080
```

See [GETTING_STARTED.md](GETTING_STARTED.md) for detailed setup, prerequisites, and configuration.

## Repo Structure

```
.claude/skills/       # 67 skills (Python, TS, React, Supabase, etc.)
.claude/hooks/        # TDD enforcement, quality gates
.claude/rules/        # Security, routing, model tiers
maggy/                # Maggy harness (FastAPI + dashboard)
  maggy/pipeline/     # Chat pipeline orchestrator
  maggy/skills/       # Skill injection + protocols
  maggy/api/          # REST API routes
  maggy/static/       # Web dashboard
cortex-mcp/           # Code intelligence MCP server
plugins/              # Installable plugins
```

## Tests

```bash
cd maggy && python3 -m pytest tests/ -x -q    # 900+ tests
cd cortex-mcp && python3 -m pytest tests/ -q  # 207 tests
```

## Docs

- [Getting Started](GETTING_STARTED.md) — installation, setup, both paths
- [Architecture](maggy/docs/architecture-v5.md) — system design
- [CLI Reference](maggy/docs/maggy-reference.md) — commands, REPL, routing
- [Telos RFC](https://github.com/alinaqi/alinaqi/blob/main/docs/Telos_RFC_v1.1.md) — intent-grounded testing
- [Cortex](cortex-mcp/docs/) — code intelligence server
- [Changelog](CHANGELOG.md) — version history (current: v6.37.0)

## License

MIT — See [LICENSE](LICENSE)

---

**Need help scaling AI in your org?** [Claude Code & MCP experts](https://leanai.ventures/aiops/claude)
