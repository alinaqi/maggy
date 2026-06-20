# Maggy

**Autonomous AI engineering command center.**

Chat with your codebases across Claude, Codex, and Kimi — with semantic routing that picks the cheapest model that can handle the task.

## Key Features

- **Semantic Routing** — local Ollama model rates task complexity and type, routes to Local/Kimi/Codex/Claude accordingly
- **Interactive Chat** — SSE streaming, session resume, ghost-text suggestions (Tab to accept)
- **Inline Model Forcing** — type "use claude" in any message to override routing
- **Parallel Execution** — Polyphony container orchestration for complex tasks (blast>=7)
- **AI-prioritized Tasks** — ranks open issues by urgency + OKR alignment
- **One-click Execute** — TDD pipeline with iCPG context enrichment
- **Council PR Review** — a multi-model council reviews a GitHub PR from the dashboard: deterministic mega-PR chunking, a static gate (tsc/ruff) as ground truth, an adversarial refute pass to kill false positives, and extensible per-language skills (Python/TS/Go/Rust/Java/C#/Ruby/PHP — drop in more). `pip install maggy-harness[review]`
- **Competitor Intelligence** — auto-discovered competitors, daily AI briefing
- **Engram Memory** — persistent cross-session memory with amnesia diagnostics

## Quick Start

```bash
pip install maggy-harness    # or: pipx install maggy-harness
maggy bootstrap              # installs skills, hooks, ~/bin model wrappers, plugins

# Pull the local model (optional but recommended)
ollama pull qwen3-coder:30b-a3b

# Configure (optional — Maggy runs in local mode without keys)
export GITHUB_TOKEN=ghp_...
export ANTHROPIC_API_KEY=sk-ant-...

# Launch
maggy              # interactive REPL (auto-detects project)
maggy serve        # web dashboard at localhost:8080
maggy chat api     # chat with a specific project
```

Or install from source for development:

```bash
cd maggy
pip install -e .
```

Or from inside Claude Code:

```
/maggy-init   # interactive setup wizard
/maggy        # launch dashboard
```

## How Routing Works

Every message gets a semantic blast score (1-10), then routes to the cheapest capable model:

| Blast | Tier | Models |
|-------|------|--------|
| 1-3 | Low | Local (Qwen3-Coder), Kimi |
| 4-6 | Medium | Codex, Kimi |
| 7-10 | High | Claude, Codex |

The router learns from outcomes — successful tasks reinforce the routing decision.

## Tests

```bash
cd maggy
python3 -m pytest tests/ -x -q
```

887 tests, target coverage >= 80%.

## Docs

- [Full CLI & REPL reference](./docs/maggy-reference.md)
- [Architecture (v5)](./docs/architecture-v5.md)
- [Polyphony spec](./docs/polyphony-spec.md)
- [Mnemos implementation](./docs/mnemos-implementation.md)

## License

MIT
