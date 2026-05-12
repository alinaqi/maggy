# Maggy

**Autonomous AI engineering command center.**

Install once, point it at your codebases and issue tracker, and get:

- **Interactive Chat** — auto-connects to all active Claude/Codex/Kimi sessions with multi-model routing and ghost-text suggestions
- **Semantic Classification** — local Ollama model classifies both task type and blast score semantically, not keyword matching
- **Inline Model Forcing** — type "use claude" in any message to force a model, no flags needed
- **Parallel Execution** — Polyphony container orchestration decomposes complex tasks into parallel subtasks
- **AI-prioritized Tasks** — ranks open issues by urgency + OKR alignment
- **One-click Execute** — spawns TDD pipeline with iCPG context enrichment and Codex/CodeRabbit review
- **Multi-Model Routing** — blast-score routing across Local/Kimi/Codex/Claude with reward learning
- **Engram Memory** — persistent cross-session memory with amnesia diagnostics
- **Competitor Intelligence** — auto-discovers competitors, daily AI briefing
- **Process Insights** — CLI session history analysis, health signals
- **Vision** — `/screenshot` analyzes images via local Qwen3-VL

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) (for local models)

```bash
# Pull the local models (optional but recommended)
ollama pull qwen3-coder:30b-a3b
ollama pull qwen3-vl:32b
```

## Install

```bash
cd maggy
pip install -e .
```

This installs the `maggy` CLI command globally. Verify:

```bash
maggy --help
```

## Configure

Create `~/.maggy/config.yaml`:

```yaml
org:
  name: "Acme Corp"
  domain: "fintech"

issue_tracker:
  provider: "github"
  github:
    org: "acmecorp"
    repos: ["acmecorp/api", "acmecorp/web"]

codebases:
  - { path: "~/dev/acmecorp/api", key: "api" }
  - { path: "~/dev/acmecorp/web", key: "web" }

competitors:
  categories: ["fintech", "embedded-finance"]

budget:
  plan: "subscription"  # or set daily_limit_usd: 10.0

dashboard:
  host: "127.0.0.1"
  port: 8080
```

Set credentials:

```bash
export GITHUB_TOKEN=ghp_...
export ANTHROPIC_API_KEY=sk-ant-...
```

## Running Maggy

### Quick Start — Interactive REPL

Run `maggy` from inside a project directory:

```bash
cd ~/dev/acmecorp/api
maggy
```

This will:
1. Auto-start the server if not already running
2. Detect the current project from your working directory
3. Drop you into an interactive REPL with multi-model routing

### Start the Server + Web Dashboard

```bash
maggy serve
```

Opens the web dashboard at `http://localhost:8080`. The server runs in the foreground — use a separate terminal or background it.

### Chat with a Specific Project

```bash
maggy chat api           # routed mode (blast-score picks the model)
maggy chat api --direct  # direct mode (always Claude)

# Inside chat, force a model inline:
> use claude and review the auth module
> use codex to fix the failing tests
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `maggy` | Interactive REPL (auto-detects project) or starts dashboard |
| `maggy serve` | Start server + web dashboard |
| `maggy chat <project>` | Chat with a specific project |
| `maggy status` | Server health and config summary |
| `maggy inbox [--refresh]` | AI-ranked task inbox |
| `maggy sessions` | List active AI sessions |
| `maggy execute <task-id>` | Run TDD pipeline on a task |
| `maggy execute <task-id> --plan` | Plan mode (no code changes) |
| `maggy spawn <task>` | Spawn a background AI session |
| `maggy ps` | List all managed sessions |
| `maggy kill <session-id>` | Stop a managed session |
| `maggy route <blast> [--type bug]` | Get routing decision for a complexity score |
| `maggy budget` | Per-provider token budget |
| `maggy models` | Model performance heatmap |
| `maggy competitors [--briefing]` | Competitor intelligence |
| `maggy process <project>` | Process health for a project |
| `maggy config` | Show current config (redacted) |

All commands accept `--json` for machine-readable output.

### REPL Slash Commands

Inside the interactive chat:

| Command | Description |
|---------|-------------|
| `/stats` | Budget + model performance summary |
| `/budget` | Per-provider spend breakdown |
| `/route` | Routing rules and model strengths |
| `/models` | Reward heatmap (model x task type x blast tier) |
| `/use claude,codex` | Restrict to specific models this session |
| `/use all` | Remove model restriction |
| `/health` | Memory health + Mnemos fatigue |
| `/config` | Configuration summary |
| `/screenshot <path> [prompt]` | Analyze image via Qwen3-VL |
| `/claude-md` | Render project's CLAUDE.md |
| `/help` | List all commands |

### From Inside Claude Code

```
/maggy-init   # interactive setup wizard
/maggy        # launch dashboard
```

## How Routing Works

Every message gets a **semantic blast score** (1-10) via the local Ollama model, then routes to the cheapest model that can handle it:

| Blast Score | Tier | Models |
|-------------|------|--------|
| 0-3 | Low | Local (Qwen3-Coder), Kimi |
| 4-6 | Medium | Codex, Kimi |
| 7-10 | High | Claude, Codex |

**Semantic blast score** — the local Ollama model rates task complexity (1-10) semantically instead of keyword matching. Understands nuance: "refactor the entire auth system" → 8, "fix the typo in README" → 2. Falls back to keyword heuristics when Ollama is down.

**Semantic intent classification** — same local model classifies task type (review, security, search, docs, tests, frontend) for routing specialization. Falls back to keywords when Ollama is down.

**Inline model forcing** — type "use claude" / "use codex" / "use kimi" / "use local" anywhere in your message to override routing. The directive is stripped before sending to the model.

**Ghost-text suggestions** — after each response, the chat input shows a context-aware suggestion in gray (like Claude Code). Press Tab to accept. Suggestions are based on the last 10 messages and recent response content.

The router learns from outcomes — every completed task records a reward that shifts future routing decisions. Security-sensitive tasks always route to premium models.

## Dashboard

Navigation is grouped by intent:

| Group | Tabs | Purpose |
|-------|------|---------|
| **Work** | Chat, Tasks, Watching | Do things — chat with Claude, triage issues |
| **Intel** | Competitors, Insights | Learn things — competitor news, session analytics |
| **System** | Budget, Models, Forge, Settings | Configure — spend limits, model routing, MCP gaps |

Chat is the default tab — auto-connects to all running CLI sessions on load.

## Architecture

- **Provider abstraction** — `IssueTrackerProvider` Protocol (GitHub, Asana)
- **Multi-model routing** — semantic blast-score + intent classification + reward learning across 4 tiers
- **Polyphony orchestration** — parallel container execution for complex tasks (blast>=7)
- **Config-driven** — zero hardcoded IDs, orgs, or competitor lists
- **iCPG integration** — context enrichment from code property graph
- **Engram memory** — SQLite-backed persistent memory with amnesia diagnostics
- **SQLite-first** — single-user local install, zero infrastructure
- **Auto-bootstrap** — all services seed on startup, no empty tabs

See [docs/architecture-v5.md](./docs/architecture-v5.md) for the full v5 architecture reference.

## Hardening

- **Working dir whitelist** — Execute and Chat validate paths against configured codebase roots
- **Chat streaming lock** — per-session `asyncio.Lock` prevents concurrent subprocess spawning
- **SSRF protection** — RSS/blog feed URLs validated before fetch (blocks loopback, private-network)
- **Host-safety check** — refuses to bind to non-loopback with local auth mode
- **Process lifecycle** — Claude subprocesses killed on timeout; non-zero exits marked failed
- **Input validation** — execute mode `Literal["tdd", "plan"]`; malformed IDs return 404

## Tests

```bash
cd maggy
python3 -m pytest tests/ -x -q        # unit tests
python3 -m pytest tests/ -x --tb=short # with tracebacks
python3 -m pytest tests/ --cov=maggy   # with coverage
```

887 tests, target coverage >= 80%.

## License

MIT
