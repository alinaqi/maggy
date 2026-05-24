# Maggy — Generic AI Engineering Command Center

Ships as a core component of Maggy. One install, works with any team.

## What Maggy Is

A local, self-improving AI agent that turns your issue tracker into an AI-prioritized inbox with one-click execution. Uses Maggy's iCPG for codebase intelligence and spawns `claude -p` for implementation.

Not a cloud service — runs on your machine, talks to your APIs, uses your Claude Code.

## Vision

```
$ maggy init
Org name: Acme Corp
Issue tracker? (github / asana / linear) → github
GitHub org: acmecorp
Repos to monitor: api, web, mobile
Competitor domain (for intelligence): fintech
Paste your OKRs (or skip): ...

✓ Config saved to ~/.maggy/config.yaml
✓ Bootstrapping iCPG for 3 repos...
✓ Discovering competitors in "fintech"...  (found 28)
✓ Ready: http://localhost:8080
```

That's it. Works the same for any org.

## Architecture

```
maggy/
├── maggy/                          # The Maggy dashboard app
│   ├── PLAN.md                     # this file
│   ├── README.md                   # user docs
│   ├── install.sh                  # one-line install
│   ├── pyproject.toml              # deps
│   ├── config.example.yaml         # config template
│   ├── maggy/                      # Python package (importable as `maggy`)
│   │   ├── main.py                 # FastAPI entry
│   │   ├── config.py               # loads ~/.maggy/config.yaml
│   │   ├── providers/
│   │   │   ├── base.py             # IssueTrackerProvider Protocol
│   │   │   ├── github_issues.py    # GitHub Issues impl
│   │   │   └── asana.py            # Asana impl (linear deferred)
│   │   ├── services/
│   │   │   ├── inbox.py            # AI-prioritized ranking
│   │   │   ├── competitor.py       # discovery + monitoring + briefing
│   │   │   └── executor.py         # TDD pipeline with iCPG enrichment
│   │   ├── api/
│   │   │   └── routes.py           # REST endpoints
│   │   └── static/
│   │       ├── index.html          # dashboard
│   │       └── app.js              # vanilla JS
├── commands/
│   ├── maggy.md                    # /maggy → launch dashboard
│   └── maggy-init.md               # /maggy-init → setup wizard
├── skills/
│   └── maggy/
│       └── SKILL.md                # Maggy capabilities reference
└── scripts/icpg/                   # ALREADY EXISTS — Maggy calls this
```

## Key Design Decisions

### 1. Config-driven, not hardcoded

A single `~/.maggy/config.yaml` drives everything. No hardcoded board IDs, repo names, team members, OKRs, or competitor lists. All that stuff lives in config.

```yaml
org:
  name: "Acme Corp"
  domain: "fintech"                  # drives competitor category + system prompt

issue_tracker:
  provider: "github"                 # "github" | "asana" (linear = stub)
  github:
    org: "acmecorp"
    repos: ["acmecorp/api", "acmecorp/web"]
    # PAT read from env: GITHUB_TOKEN

codebases:
  - path: "~/dev/acmecorp/api"
    key: "api"
  - path: "~/dev/acmecorp/web"
    key: "web"

competitors:
  categories: ["fintech", "embedded-finance"]
  # Maggy auto-discovers. Stores in ~/.maggy/competitors.json

ai:
  provider: "anthropic"
  model: "claude-sonnet-4-5-20250929"
  # API key from ANTHROPIC_API_KEY env

storage:
  # SQLite by default — zero setup. Supabase optional.
  backend: "sqlite"
  path: "~/.maggy/maggy.db"

dashboard:
  port: 8080
  auth_mode: "local"                 # no auth for single-user local use
```

### 2. Provider abstraction for issue trackers

The #1 coupling in the zenloop version is Asana. Generic Maggy defines a Protocol and all services use it:

```python
class IssueTrackerProvider(Protocol):
    async def list_tasks(self, board: str | None = None, state: str = "open") -> list[Task]
    async def get_task(self, task_id: str) -> Task
    async def add_comment(self, task_id: str, text: str) -> None
    async def update_status(self, task_id: str, status: str) -> None
    async def list_followed(self, user_id: str | None = None) -> list[Task]
    async def search_tasks(self, query: str) -> list[Task]
```

`GitHubIssuesProvider` and `AsanaProvider` both implement this. Services call `provider.list_tasks()` — they don't care what's underneath.

### 3. Reuses Maggy's iCPG

Don't duplicate iCPG. Maggy shells out to the iCPG CLI:

```python
# executor.py
async def _get_icpg_context(title: str, notes: str) -> str:
    keywords = extract_keywords(title + notes)
    context = []
    for kw in keywords[:5]:
        result = await run_cmd(["icpg", "query", "symbols", "--keyword", kw, "--json"])
        context.append(result)
    return format_icpg_block(context)
```

This means the dashboard automatically benefits from iCPG upgrades. No duplicate symbol indexing.

### 4. SQLite-first storage

The zenloop version used Supabase for P2P coordination. For a single-user local install, SQLite is simpler and zero-setup. P2P and multi-user stays optional:

- **Default (SQLite):** `~/.maggy/maggy.db`. Zero setup.
- **Optional (Supabase):** For teams that want shared state and P2P handoff.

### 5. Dashboard is minimal but real

Not a React SPA — Tailwind CDN + vanilla JS. Matches Maggy's philosophy (no build step, dead simple). Three views:

1. **Inbox** — AI-prioritized issues with Execute/Plan/Comment buttons
2. **Competitor News** — daily AI briefing + news feed
3. **Settings** — view/edit config, health check

### 6. Ships with Maggy

User installs Maggy, runs `/maggy-init` in Claude Code, and the dashboard is configured + running. `/maggy` in any Claude Code session opens the dashboard.

## MVP Scope (what I'm building now)

**In scope:**
- [x] Directory structure
- [ ] Config loader + example
- [ ] IssueTrackerProvider Protocol + GitHub Issues + Asana impls
- [ ] Inbox service (AI-prioritized)
- [ ] Competitor service (AI-discovered, daily briefing)
- [ ] Executor service (TDD pipeline with iCPG enrichment)
- [ ] FastAPI server + 8 endpoints
- [ ] Minimal HTML dashboard
- [ ] install.sh + pyproject.toml + README
- [ ] /maggy and /maggy-init commands
- [ ] skills/maggy/SKILL.md

**Deferred to v2 (not MVP):**
- Meeting bot (voice)
- Slack integration
- P2P network + session handoff
- Self-improvement (`/improve-maggy`)
- Heartbeat service (background processing)
- BambooHR integration
- Auto-review (PRs, tickets)
- 27 AI tools → starts with 5 core tools
- Linear provider (stub only)

## How to test independently

After install:

```bash
cd ~/Documents/AI-Playground/maggy/maggy
./install.sh

# Configure
cp config.example.yaml ~/.maggy/config.yaml
# Edit ~/.maggy/config.yaml with your GitHub org/repos

# Set env vars
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...

# Run
python -m maggy.main

# Open http://localhost:8080
```

Or from inside Claude Code (after bootstrap install):
```
/maggy-init    # interactive setup
/maggy         # launch dashboard
```

Should work out-of-the-box for any GitHub-based team.

## Success criteria

1. Fresh install on a machine that never saw zenloop → works
2. Points at any GitHub org → inbox populates with issues
3. AI prioritization runs → issues ranked
4. Click Execute → TDD pipeline spawns `claude -p` with iCPG context injected
5. Competitor discovery for any domain → competitors found + daily briefing
6. No hardcoded zenloop anything anywhere in the code

That's the bar.
