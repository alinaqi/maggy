# Maggy

**Autonomous AI engineering command center.**

Install once, point it at your codebases and issue tracker, and get:

- **Interactive Chat** — auto-connects to all active Claude/Codex/Kimi sessions, take over from the web UI with full session continuity (`--resume`)
- **AI-prioritized Tasks** — ranks open issues by urgency + OKR alignment
- **One-click Execute** — spawns `claude -p` with iCPG-enriched prompts, runs TDD pipeline
- **Competitor Intelligence** — auto-discovers competitors, daily AI briefing
- **Process Insights** — CLI session history analysis, health signals, self-improvement recommendations
- **P2P Mesh** — multi-node session sync and handoff across machines
- **Auto-Bootstrap** — all services seed themselves on startup (history, CIKG, events)

## Install

```bash
cd maggy/maggy
./install.sh
```

## Configure

Edit `~/.maggy/config.yaml`:

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
```

Set credentials:

```bash
export GITHUB_TOKEN=ghp_...
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
python3 -m maggy.main
```

Open `http://localhost:8080`.

## Dashboard

Navigation is grouped by intent:

| Group | Tabs | Purpose |
|-------|------|---------|
| **Work** | Chat, Tasks, Watching | Do things — chat with Claude, triage issues |
| **Intel** | Competitors, Insights | Learn things — competitor news, session analytics |
| **System** | Budget, Models, Forge, Settings | Configure — spend limits, model routing, MCP gaps |

Chat is the default tab — auto-connects to all running CLI sessions on load.

## From inside Claude Code

```
/maggy-init   # interactive setup wizard
/maggy        # launch dashboard
```

## Features

- **Interactive Chat** — SSE streaming, session continuity via `--resume`, path-based history matching, auto-connect to active CLI sessions
- **Activity Scanner** — detects running `claude`, `codex`, `kimi` processes via `ps aux` + `lsof`
- **History Analysis** — parses 260+ CLI sessions, topic extraction, session patterns
- **Self-Improvement** — signal collection, health scoring, actionable recommendations
- **CIKG Knowledge Graph** — codebase nodes, technology detection, landscape queries
- **Event Spine** — structured event emission and querying across all services
- **Engram Memory** — write/query/expire memory entries with metadata
- **Budget Tracking** — daily spend limits with per-provider breakdown
- **Model Routing** — reward-based heatmap for model selection by task type
- **MCP Forge** — detects capability gaps from filesystem, suggests MCP tools
- **P2P Mesh** — WebSocket sync, peer discovery, state quarantine, org-scoped networks
- **Heartbeat** — scheduled jobs (history refresh, engram expiry, self-improve, mesh sync)

## Hardening

- **Working dir whitelist** — Execute and Chat both validate paths against configured codebase roots
- **Chat streaming lock** — per-session `asyncio.Lock` prevents concurrent subprocess spawning
- **SSRF protection** — RSS/blog feed URLs validated before fetch (blocks loopback, private-network)
- **CLAUDECODE env stripping** — subprocess spawning removes `CLAUDECODE` to allow nested Claude sessions
- **Process lifecycle** — Claude subprocesses killed on timeout; non-zero exits marked failed
- **Input validation** — Execute mode `Literal["tdd", "plan"]`; malformed IDs return 404
- **503 onboarding mode** — unconfigured state returns 503 with setup pointer
- **Safe external links** — scheme allowlist + `rel="noopener noreferrer"`
- **No-cache static files** — `Cache-Control: no-store` prevents stale JS in browser

## Architecture

See [PLAN.md](./PLAN.md) for the full architecture rationale.

1. **Provider abstraction** — `IssueTrackerProvider` Protocol (GitHub, Asana, Linear stub)
2. **Config-driven** — zero hardcoded IDs, orgs, or competitor lists
3. **iCPG integration** — context enrichment from code property graph
4. **SQLite-first** — single-user local install, zero setup
5. **Auto-bootstrap** — all services seed on startup, no empty tabs
6. **Grouped UI** — Work / Intel / System navigation by intent

## License

MIT
