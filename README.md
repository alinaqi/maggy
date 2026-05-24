# Maggy

Two things in one repo. Pick the path that fits:

**Path A: Claude Bootstrap** -- Skills, hooks, and rules that make Claude Code (and Codex/Kimi) dramatically better. Install in 30 seconds, keep using Claude as normal.

**Path B: Maggy** -- An autonomous engineering harness. Multi-model routing, intent tracking, memory persistence, and a testing framework that goes beyond TDD. For engineers who want to steer AI agents at scale.

You can start with A and add B later. They're designed to work together.

---

## Path A: Claude Bootstrap

67 skills, TDD enforcement, quality gates, security rules, and agent teams. Works with Claude Code, Codex CLI, Kimi CLI, and Gemini CLI.

### Install

```bash
git clone https://github.com/alinaqi/maggy.git
cd maggy
./install.sh
```

That's it. This copies skills, hooks, rules, and delegation scripts to `~/.claude/`. Now open any project:

```bash
cd your-project
claude
> /initialize-project
```

Claude validates tools, asks about your stack, sets up the repo structure, and optionally spawns an agent team.

### What you get

| Layer | What it does |
|-------|-------------|
| **67 skills** | Python, TypeScript, React, React Native, Flutter, Android, Supabase, Firebase, Stripe, Shopify, and more |
| **TDD hooks** | Tests run after every Claude response. Failures feed back automatically |
| **Quality gates** | Max 20 lines/function, 3 params, 2 nesting levels. Enforced on every file |
| **Security rules** | No secrets in code, parameterized queries, input validation at boundaries |
| **Agent teams** | 6 agents: Lead, Quality, Security, Review, Merger, Feature. Enforced pipeline |
| **Multi-tool** | Also installs to Kimi CLI and Codex CLI if detected |

### Update

```bash
cd "$(cat ~/.claude/.bootstrap-dir)"
git pull && ./install.sh
```

---

## Path B: Maggy -- Autonomous Engineering Harness

Everything in Path A, plus a local engineering command center that routes work across AI models, tracks intent, persists memory, and tests beyond TDD.

### Prerequisites

- Python 3.11+
- pip
- Claude Code CLI (or any supported AI CLI)
- API keys: `ANTHROPIC_API_KEY` (required), `GITHUB_TOKEN` (recommended)

### Install

```bash
# Step 1: Install bootstrap (if you haven't)
git clone https://github.com/alinaqi/maggy.git
cd maggy
./install.sh

# Step 2: Install Maggy
cd maggy
pip install -e .

# Step 3: Set API keys
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...

# Step 4: Run
maggy serve    # web dashboard at localhost:8080
maggy          # CLI REPL (auto-detects current project)
```

### What you get (on top of Bootstrap)

**Multi-model routing** -- 13-tier routing across Qwen (local/free), DeepSeek, Gemini, Kimi, Grok, Codex, and Claude. Routes by task complexity. DeepSeek handles ~80% of coding work. Claude reserved for architecture and security.

**Chat** -- Interactive sessions with streaming, session persistence, model forcing ("use claude"), and project context injection.

**[Telos](https://github.com/alinaqi/alinaqi/blob/main/docs/Telos_RFC_v1.1.md)** -- Intent-grounded testing. Three planes: Conformance (do tests pass), Validation (is there intent drift), Integrity (orphan code, stale intents, scope sprawl). IFS = F1 x F2 x F3. A zero in any plane collapses the score. Runs automatically on every project open.

**[Cortex MCP](cortex-mcp/)** -- Unified code intelligence. Replaces codebase-memory-mcp with a Python MCP server combining structure (AST), intent (iCPG), and memory (Mnemos). 15 tools, single SQLite DB.

**Plugins** -- Drop a folder with `plugin.yaml` + `plugin.py` into `plugins/`. Auto-discovered on startup.

| Plugin | What it does |
|--------|-------------|
| **build-in-public** | Auto-generates and schedules posts from your work (LinkedIn + X via Buffer) |
| **telos** | Intent-grounded testing with IFS scoring |
| **e2e-testkit** | Regression scanning (being replaced by Telos) |
| **forge** | Project scaffolding |
| **provider-github** | GitHub issue sync |
| **provider-asana** | Asana task sync |
| **provider-monday** | Monday.com task sync |

**Memory (Mnemos)** -- Typed graph where goals and constraints are never evicted. 4-dimension fatigue model triggers consolidation early, before context window death spirals. Cross-session memory via Engram.

**Execute** -- One-click TDD pipeline with Cortex context enrichment.

**Tasks** -- AI-prioritized inbox from GitHub Issues or Asana.

### Architecture

```
maggy/
  maggy/              # Python package (FastAPI)
    api/              # REST routes
    services/         # Chat, routing, AI client
    plugins/          # Plugin manager
    static/           # Dashboard UI
  plugins/            # Installable plugins (telos, build-in-public, etc.)
  tests/              # 82+ tests
  docs/               # Architecture, RFC, specs

cortex-mcp/           # Code intelligence MCP server
  src/cortex/         # Structure + Intent + Memory layers
  tests/              # 207 tests
```

### Tests

```bash
cd maggy
python3 -m pytest tests/ -x -q
```

---

## Docs

- [Bootstrap reference](docs/claude-bootstrap-reference.md) -- TDD hooks, Mnemos, iCPG, agent teams, full skills catalog
- [Maggy reference](maggy/docs/maggy-reference.md) -- CLI, REPL, routing, dashboard
- [Architecture v5](maggy/docs/architecture-v5.md) -- System architecture
- [Telos RFC](https://github.com/alinaqi/alinaqi/blob/main/docs/Telos_RFC_v1.1.md) -- Intent-grounded testing spec
- [Cortex docs](cortex-mcp/docs/) -- Code intelligence server
- [Changelog](CHANGELOG.md) -- Version history (current: v6.35.0)
- [GETSTARTED.md](GETSTARTED.md) -- Quick context for AI agents working on this codebase

## License

MIT -- See [LICENSE](LICENSE)

---

**Need help scaling AI in your org?** [Claude Code & MCP experts](https://leanai.ventures/aiops/claude)
