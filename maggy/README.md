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
- ✅ AI-prioritized inbox with 30-min cache + stale-cache fallback
- ✅ TDD execute pipeline (plan → tests → implement), validated `working_dir`
- ✅ Generic competitor discovery + RSS + Google News, SSRF-hardened
- ✅ Daily competitor briefing (cached per day)
- ✅ Minimal dashboard (no build step), safe external-URL rendering
- ✅ SQLite storage (zero setup)

## Hardening notes

- **Working dir whitelist** — Execute validates any caller-supplied `working_dir`
  against configured codebase roots. You can't point `claude --dangerously-skip-permissions`
  at arbitrary paths.
- **SSRF protection** — RSS/blog feed URLs from the AI-discovered registry are
  validated before fetch: non-HTTP(S), loopback, link-local, private-network,
  and unspecified addresses are rejected.
- **Process lifecycle** — Claude subprocesses are explicitly killed on timeout;
  non-zero exits flip the session to `failed` instead of silently "completed".
- **Input validation** — Execute mode uses `Literal["tdd", "plan"]`; malformed
  task IDs return 404 not 500; LLM ranking output is validated before applying.
- **503 onboarding mode** — When `~/.maggy/config.yaml` is missing or incomplete,
  only `/api/health` and `/api/config` respond. All other routes return 503 with
  a pointer to the example config.
- **Safe external links** — Dashboard uses a scheme allowlist + `rel="noopener noreferrer"`
  when rendering competitor/issue URLs.

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
