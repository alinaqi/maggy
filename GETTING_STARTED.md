# Getting Started

Two paths in one repo. Pick the one that fits:

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

### Preview, back up & uninstall

```bash
maggy diff             # what would change vs your current setup
maggy backup           # snapshot your existing files (bootstrap also auto-backs-up first)
maggy restore          # roll back to your pre-Maggy files (--list to choose one)

maggy uninstall        # dry-run — preview exactly what would be removed
maggy uninstall --yes  # remove the managed assets (your own files are spared)
pip uninstall maggy-harness
```

Full backup/restore + revert guide (incl. `~/.maggy` data, `settings.json` hooks, srooter): [UNINSTALL.md](UNINSTALL.md).

---

## Path B: Maggy -- Autonomous Engineering Harness

Everything in Path A, plus a local engineering command center that routes work across AI models, tracks intent, persists memory, and tests beyond TDD.

### Prerequisites

- Python 3.11+ and pip
- That's it. **No API keys required to start** — Maggy runs in local mode and
  auto-configures from your local git repos on first launch.

### Install

```bash
# pip / pipx (recommended)
pipx install maggy-harness      # or: pip install maggy-harness
maggy bootstrap                 # skills, hooks, ~/bin model wrappers, plugins
maggy serve                     # dashboard at http://localhost:8080

# — or from source —
git clone https://github.com/alinaqi/maggy.git
cd maggy/maggy && ./install.sh && maggy serve
```

> The PyPI package is `maggy-harness` (the name `maggy` is taken); you still
> `import maggy` and run the `maggy` command. `maggy bootstrap` installs the
> Claude Code skills/hooks/commands, the `~/bin` model-delegation wrappers, and
> plugins — the parts that live in the wider claude-bootstrap repo.

On first launch Maggy discovers your local repos and opens the dashboard
pointed at them — nothing to hand-edit.

**Optional** (add later when you want them, not needed to start):

```bash
export GITHUB_TOKEN=ghp_...        # GitHub issue sync in the Inbox
export ANTHROPIC_API_KEY=sk-ant-...# API-model features
```

### Recommended: route through srooter ([www.srooter.ai](https://www.srooter.ai))

For transparent multi-model routing across **Maggy, Claude Code, and Codex**, point your tools at **[srooter](https://www.srooter.ai)** — an Anthropic/OpenAI-compatible gateway that routes each request to the right model (Claude, MiniMax, DeepSeek, Kimi, Gemini, Grok, local Qwen) with budget caps, fallbacks, and a usage dashboard. No per-tool config.

```bash
# Get a key at www.srooter.ai, then point Claude Code / Codex at the gateway:
export ANTHROPIC_BASE_URL="https://www.srooter.ai/anthropic"   # or your local gateway
export ANTHROPIC_API_KEY="<your-srooter-key>"
claude        # now routed through srooter

# Choose the model you "follow" once — Maggy, the route-task hooks, and srooter
# all honor the same choice (trivial asks stay cheap/local):
/model-config minimax
```

### What you get (on top of Bootstrap)

**Multi-model routing** -- 13-tier routing across Qwen (local/free), DeepSeek, Gemini, Kimi, Grok, Codex, and Claude. Routes by task complexity. DeepSeek handles ~80% of coding work. Claude reserved for architecture and security.

**Chat** -- Interactive sessions with streaming, session persistence, model forcing ("use claude"), and project context injection.

**Skill Protocols** -- YAML-defined workflows that match user intent and execute step sequences. "Push to git" triggers lint, test, stage, commit (AI-generated message), push. Extensible by dropping a `.yaml` file in `protocols/`.

**[Telos](https://github.com/alinaqi/alinaqi/blob/main/docs/Telos_RFC_v1.1.md)** -- Intent-grounded testing. Three planes: Conformance (do tests pass), Validation (is there intent drift), Integrity (orphan code, stale intents, scope sprawl). IFS = F1 x F2 x F3. A zero in any plane collapses the score.

**[Cortex MCP](cortex-mcp/)** -- Unified code intelligence. Structure (AST), Intent (iCPG), Memory (Mnemos). 15 tools, single SQLite DB.

**Plugins** -- Drop a folder with `plugin.yaml` + `plugin.py` into `plugins/`. Auto-discovered on startup.

| Plugin | What it does |
|--------|-------------|
| **build-in-public** | Auto-generates and schedules posts from your work (LinkedIn + X via Buffer) |
| **telos** | Intent-grounded testing with IFS scoring |
| **forge** | Project scaffolding |
| **provider-github** | GitHub issue sync |
| **provider-asana** | Asana task sync |
| **provider-monday** | Monday.com task sync |

**Memory (Mnemos)** -- Typed graph where goals and constraints are never evicted. 4-dimension fatigue model triggers consolidation early, before context window death spirals.

### Architecture

```
maggy/
  maggy/              # Python package (FastAPI)
    api/              # REST routes
    services/         # Chat, routing, AI client
    pipeline/         # Unified chat pipeline (orchestrator, backends, hooks)
    skills/           # Skill injection + protocols
    plugins/          # Plugin manager
    static/           # Dashboard UI
  plugins/            # Installable plugins (telos, build-in-public, etc.)
  tests/              # 900+ tests
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
- [Changelog](CHANGELOG.md) -- Version history

**Need help scaling AI in your org?** [Claude Code & MCP experts](https://leanai.ventures/aiops/claude)
