# Maggy

**Generic AI engineering command center that ships with claude-bootstrap.**

Install once, point it at your team's GitHub (or Asana) and codebases, and get:

- **AI-prioritized inbox** — ranks open issues by urgency + OKR alignment
- **One-click execute** — spawns `claude -p` with iCPG-enriched prompts, runs TDD pipeline
- **Competitor intelligence** — auto-discovers competitors in your domain, daily AI briefing
- **Reusable** — no zenloop-specific hardcoding. Works for any team, any stack.

## Install

```bash
cd ~/Documents/AI-Playground/claude-bootstrap/maggy
./install.sh
```

## Configure

Edit `~/.maggy/config.yaml`:

```yaml
org:
  name: "Acme Corp"
  domain: "fintech"   # drives competitor discovery

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
export GITHUB_TOKEN=ghp_...           # repo + issues scopes
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
cd ~/Documents/AI-Playground/claude-bootstrap/maggy
python3 -m src.main
```

Open `http://localhost:8080`.

## From inside Claude Code

Once claude-bootstrap is installed:

```
/maggy-init   # interactive setup wizard
/maggy        # launch dashboard
```

## What's in the MVP

- ✅ GitHub Issues provider (primary)
- ✅ Asana provider (optional, for migration scenarios)
- ✅ AI-prioritized inbox with 30-min cache
- ✅ TDD execute pipeline (plan → tests → implement)
- ✅ Generic competitor discovery + RSS + Google News
- ✅ Daily competitor briefing (cached per day)
- ✅ Minimal dashboard (no build step)
- ✅ SQLite storage (zero setup)

## Not in MVP (v2 work)

- Linear provider (stub)
- Meeting bot, Slack, voice
- P2P network + session handoff
- Self-improvement (`/improve-maggy`)
- Heartbeat background processing
- Full observability dashboard

## Architecture

See [PLAN.md](./PLAN.md) for the full architecture rationale.

Key design decisions:

1. **Provider abstraction** — `IssueTrackerProvider` Protocol. Services never see GitHub/Asana directly.
2. **Config-driven** — zero hardcoded IDs, orgs, or competitor lists.
3. **Reuses bootstrap's iCPG** — no duplicate symbol indexing.
4. **SQLite-first** — single-user local install by default. Supabase optional for team mode.
5. **Generic system prompt** — templated with your org/domain.

## License

MIT — same as claude-bootstrap.
