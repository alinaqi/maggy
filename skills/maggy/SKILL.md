---
name: maggy
description: Maggy is a local AI engineering command center. AI-prioritized inbox across issue trackers (GitHub Issues/Asana), one-click TDD execute with iCPG context enrichment, daily competitor intelligence briefing.
when-to-use: "When you want a persistent dashboard to triage tickets and spawn Claude Code runs against any repo"
user-invocable: true
effort: medium
---

# Maggy Skill

**Maggy** is a generic, local AI engineering command center. Install once, point it at your team's issue tracker and codebases, and get:

- **AI-prioritized inbox** — ranks open issues by urgency, OKR alignment, and recency
- **One-click Execute** — spawns Claude Code locally with iCPG context injected
- **Competitor intelligence** — daily AI briefing on your competitive landscape
- **No hardcoding** — works for any team, any stack, any issue tracker

### ⚠️ Execute permission model (important)

Execute currently runs `claude -p --dangerously-skip-permissions` so the TDD
pipeline isn't blocked waiting on approval prompts (subprocess has no terminal).
That flag **grants Claude full permission to write/edit files and run shell
commands** inside the target codebase, and the prompt it receives includes
content from the issue tracker (which any team member can author).

**Hardening already in place:**
- `working_dir` is validated against the list of codebase roots in
  `~/.maggy/config.yaml` — Claude can't be pointed at arbitrary filesystem paths.
- Only tickets from your configured trackers reach Execute; no public-internet
  input flows into the prompt.

**Roadmap:** move the unconditional flag behind per-codebase config
(`auto_approve: true|false`) so privileged execution becomes opt-in.
Until then, treat Execute like `git pull && make` on any ticket you push
the button for — only run it on repos you own, against tickets from
authors you trust.

```
┌──────────────────────────────────────────────────────────────┐
│  maggy               ──────────────┐                          │
│  ├── skills/         ← installed globally → ~/.claude/       │
│  ├── commands/       ← installed globally → ~/.claude/       │
│  ├── scripts/icpg/   ← used by Maggy for context enrichment  │
│  └── maggy/          ← dashboard: run `./install.sh` to use  │
│      ├── src/                                                │
│      │   ├── providers/   ← GitHub / Asana / Linear          │
│      │   ├── services/    ← inbox, competitor, executor      │
│      │   └── api/         ← FastAPI routes                   │
│      └── install.sh                                          │
└──────────────────────────────────────────────────────────────┘
```

---

## When Maggy Helps

| Scenario                                 | How Maggy helps                               |
|------------------------------------------|-----------------------------------------------|
| Morning triage of 50 open issues         | AI ranks them; top items stay top             |
| Implementing a ticket                    | `Execute` → iCPG-enriched TDD pipeline        |
| "What are competitors shipping?"         | Daily briefing + filterable news feed         |
| Multiple repos per team                  | Auto-picks right repo based on ticket content |
| New team onboarding                      | Configure via `/maggy-init`, no code writing  |

---

## Install and Configure

```bash
# One-time install
cd $(cat ~/.claude/.bootstrap-dir)/maggy
./install.sh

# Configure
# Edit ~/.maggy/config.yaml — see maggy/config.example.yaml for the schema

# Credentials
export GITHUB_TOKEN=ghp_...
export ANTHROPIC_API_KEY=sk-ant-...

# Run
python3 -m src.main

# Or from Claude Code:
#   /maggy-init    # interactive wizard
#   /maggy         # launch dashboard
```

---

## Provider Abstraction

Maggy services never see GitHub/Asana directly — they talk to an `IssueTrackerProvider` Protocol. Drop-in swap between:

- `GitHubIssuesProvider` — scans multiple repos, aggregates open issues, maps "done" → closed
- `AsanaProvider` — queries projects, respects workspace scope
- `LinearProvider` — stub for future

The same inbox, Execute pipeline, and Competitor features work with any provider.

---

## Execute Pipeline

When you click Execute on a ticket:

1. Maggy queries the configured iCPG for relevant symbols, blast radius, and prior intents
2. Picks the right working directory based on ticket keywords + configured codebases
3. Spawns `claude -p --dangerously-skip-permissions` in that directory
4. Runs analyze → write failing tests → implement
5. Captures output in a session you can follow in the Sessions tab

Because the spawned Claude Code runs in the target repo, it picks up:
- That repo's `CLAUDE.md`
- Your global `~/.claude/CLAUDE.md`
- All bootstrap skills
- `.claude/hooks/`, `.mcp.json`

So Execute gets the full bootstrap experience — not a stripped-down version.

---

## Competitor Intelligence

Generic — works for any domain:

1. Configure `competitors.categories: ["fintech", "embedded-finance"]` in `~/.maggy/config.yaml`
2. Click Discover — Claude identifies 12-18 competitors (market leaders, AI-first challengers, vertical specialists)
3. Maggy monitors their RSS blogs + Google News daily
4. Daily briefing is generated once per day (cached), regeneratable on demand

---

## Not Included

Maggy MVP is focused. Not shipped:

- Meeting bot (voice)
- Slack integration
- P2P network + session handoff
- Self-improvement (`/improve-maggy`)
- Linear provider (stub only)

These are v2 work.

---

## Files

- `maggy/PLAN.md` — architecture rationale
- `maggy/README.md` — user docs
- `maggy/src/providers/base.py` — IssueTrackerProvider Protocol
- `maggy/src/services/executor.py` — TDD pipeline
- `maggy/src/services/competitor.py` — discovery + briefing
- `maggy/src/services/inbox.py` — AI prioritization
- `commands/maggy.md` — `/maggy` launcher
- `commands/maggy-init.md` — `/maggy-init` setup wizard
