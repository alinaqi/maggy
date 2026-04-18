# Changelog

All notable changes to Claude Bootstrap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [3.5.0] - 2026-04-19

### CI
- **`skill-review.yml`**: both `tessl` and `skills-ref` jobs now space-join the detected-skills list before writing to `$GITHUB_OUTPUT`. The old plain `echo "skills=$CHANGED"` with a multi-line `$CHANGED` value failed GHA's output parser ("Invalid format") AND broke the downstream `for skill in ${{ outputs.skills }}` loop. Space-joining keeps both happy and unblocks multi-skill PRs (like this one, which touches both `maggy/` and `mnemos/`).

### Third review pass fixes (Copilot iteration)
- **Package renamed `src/` → `maggy/`.** The top-level `src` package name was a well-known Python packaging anti-pattern that collides with other projects. The Python code now lives at `claude-bootstrap/maggy/maggy/` and imports as `from maggy.X import Y` (matching the icpg/mnemos/skill_lint convention). `pyproject.toml` entrypoint + includes, `install.sh`, and the launcher commands updated to `python3 -m maggy.main`.
- **SQLite PRAGMAs** — `InboxService` and `CompetitorService` open connections via a shared helper that sets `journal_mode=WAL`, `foreign_keys=ON`, and `busy_timeout=30000`. Matches the convention used by `scripts/icpg/store.py` and prevents "database is locked" errors when the FastAPI handlers race the heartbeat worker.
- **Host-safety startup check** — `create_app()` now refuses to boot when `dashboard.auth_mode="local"` is combined with a non-loopback host (anything other than `127.0.0.1`/`localhost`/`::1`). Execute spawns `claude --dangerously-skip-permissions`, so binding to `0.0.0.0` with no auth would expose that to the local network. Users are directed to switch to token auth or rebind.
- **`is_configured()` no longer accepts `linear`** — `providers.build()` raises `NotImplementedError` for Linear (stub), so treating it as configured would crash `create_app()` at startup. Now returns `False` cleanly.
- **`providers.build()`** raises `NotImplementedError` with a clear "use github or asana" hint for `linear`.
- **GitHub provider logs non-200s** in `list_tasks` — previously a 401/403/404 silently yielded an empty inbox. Now WARNING-logged with the repo slug and first 200 chars of the response body for debuggability.
- **Removed unused `timedelta` import** from `inbox.py`.

### Second review pass fixes (CodeRabbit iteration 2)
- `AsyncAnthropic` used in async methods — inbox ranking + competitor discovery + daily briefing no longer block the event loop on multi-second LLM round-trips
- RSS/Google News feed date handling uses `parsedate_to_datetime` + ISO parser and compares real `datetime` objects — RFC 822 strings aren't lexicographically ordered (day-of-week cycles weekly)
- iCPG CLI invocation fixed: `python3 -m scripts.icpg query prior --text ...` against the real argparse entrypoint, not the utility submodule `scripts.icpg.symbols` which has no `__main__`
- Background `asyncio.create_task()` reference kept in a set + `add_done_callback(discard)` so GC can't kill the TDD pipeline mid-run
- `GitHubIssuesProvider.list_followed()` and `search_tasks()` refuse to run when `repos` is empty (otherwise the query has no repo filter and searches all of public GitHub)
- `AsanaProvider.list_tasks()` drops the dead `completed_filter` variable and skips sending `completed_since=""` (Asana validator rejects empty string); filters `closed` state properly
- `install.sh` enforces Python 3.11+ minimum (was only checking `python3` existed)
- `/static/index.html`: added CSP meta tag; Font Awesome pinned with SHA-384 SRI; Tailwind Play CDN annotated with vendor-for-prod TODO
- `static/app.js`: added `jsStr()` for JS-string-context escaping in inline onclick handlers (esc() alone leaves single quotes intact — XSS via ticket titles was possible)
- `regenerateBriefing()` catches and displays errors instead of swallowing them
- `commands/maggy.md`: reads `dashboard.host`/`dashboard.port` from config before probing health (was hardcoded 8080)
- `commands/maggy-init.md`: removed the "offer to write to .env" suggestion — the runtime doesn't load that file, so it would leave tokens on disk with no reader
- `config.example.yaml`: removed the Linear section (stub only, shouldn't be in the advertised selectable set)
- `PLAN.md`: config sample aligned with the actual runtime schema (removed spurious `config:` nesting)
- `maggy/README.md`: install path no longer assumes `~/Documents/AI-Playground/...`; uses relative `cd claude-bootstrap/maggy`
- `providers/__init__.py`: `__all__` alphabetized (RUF022)
- `skills/maggy/SKILL.md`: explicit permission-model disclosure box explaining the `--dangerously-skip-permissions` tradeoff and the `working_dir` whitelist mitigations

### Added
- **Maggy — AI engineering command center** (optional extension under `maggy/`)
  - Local FastAPI + vanilla JS dashboard; install with `maggy/install.sh`, zero build step
  - Provider abstraction: `GitHubIssuesProvider`, `AsanaProvider`, `LinearProvider` (stub) implement a single `IssueTrackerProvider` Protocol — swap trackers without touching services
  - AI-prioritized inbox with 30-min SQLite cache; stale-cache fallback when provider is unavailable
  - Generic competitor discovery + RSS + Google News monitoring with daily AI briefing (cached per day)
  - TDD execute pipeline (plan → tests → implement) spawns `claude -p --dangerously-skip-permissions` locally in the right codebase, with iCPG context auto-injected from the bootstrap's iCPG CLI
  - Config-driven (`~/.maggy/config.yaml`) — no hardcoded org IDs, repo names, or competitor lists
  - `/maggy` command launches dashboard; `/maggy-init` runs interactive setup
  - `skills/maggy/SKILL.md` documents capabilities; README skills table updated
- Maggy skill included in the skills table (fixes RI002 lint error for this PR)

### Fixed
- Added YAML frontmatter to `skills/mnemos/SKILL.md` (fixes FM001 lint error that was blocking CI on main)
- Skill lint now passes across all 60 skills

### Security (Maggy)
- RSS URL validation before fetching competitor feeds — blocks loopback, link-local, private-network, and non-HTTP(S) targets (SSRF prevention)
- `safeHref()` in dashboard JS — only allows `http(s)`/`mailto` schemes in external links, blocks `javascript:`/`data:` URIs that would slip past HTML escaping
- `working_dir` validated against configured codebase roots before launching Claude Code — prevents arbitrary-cwd execution of `--dangerously-skip-permissions`
- Execute-mode input validated via `Literal["tdd", "plan"]`; typos rejected at request boundary
- GitHub `_decode_id()` returns `None` on malformed input instead of raising — surfaces as 404 not 500
- LLM ranking output validated (index range, numeric rank, dedupe) before applying

### Resilience (Maggy)
- `provider.list_tasks` failure falls back to last cached ranking (flagged `stale=true`) instead of 500
- Route-level `_require_configured()` returns 503 + onboarding hint when `~/.maggy/config.yaml` is missing, instead of dereferencing `None` services
- `is_configured()` requires provider credentials (token) in addition to org/repos; refreshes cache on each check
- Claude subprocess kill on timeout (`proc.kill()` + `await proc.wait()`), non-zero exits marked as failed sessions
- `_run_claude()` returns `(ok, output)` tuple — TDD pipeline now aborts chain on first-step failure
- Competitor news events use deterministic SHA-256 IDs with `INSERT OR IGNORE` — prevents duplicate rows on cursor reset / overlapping scans

### Changed (Maggy)
- `pyproject.toml` console script `maggy = "src.main:main"` (proper callable) instead of `"src.main:app"` (ASGI instance)

---

## [3.4.1] - 2026-04-10

### Fixed
- Fixed broken `build-backend` in all three pyproject.toml files (icpg, mnemos, skill_lint). Changed `setuptools.backends._legacy:_Backend` to `setuptools.build_meta`. (Community reported)

### Added
- Cheeky personality section in CLAUDE.md template for new projects

---

## [3.4.0] - 2026-04-07

### Added
- **Skill Quality Gates** — Automated linter, CI integration, and behavioral evals
  - `scripts/skill_lint/` — Python package with 20 check rules across 4 categories:
    - Frontmatter (FM001-FM009): YAML validation, name/description/field checks
    - Spec (SP001-SP003, SR001): SKILL.md existence, line count limits, skills-ref integration
    - Content (CQ001-CQ006): ASCII art detection, vague phrase detection, filler intensity, code block density, stale references, H1 heading
    - References (RI001-RI002): Cross-skill link validation, README coverage
  - CLI: `PYTHONPATH=scripts python3 -m skill_lint [--format text|json] [--severity error|warning|info] [--skill NAME] [--fail-on error|warning] skills/`
  - Inline suppression: `<!-- skill-lint: disable=SP002 -->` in first 10 lines
  - 28 unit tests covering all check modules, report formatters, and CLI
  - `.github/workflows/skill-lint.yml` — Runs linter + tests on PR/push to skills/ or scripts/skill_lint/
  - `.github/workflows/skill-review.yml` — Tessl skill review + skills-ref validation on PRs (requires TESSL_TOKEN)
  - `evals/` — 18 behavioral eval scenarios for 15 skills with deterministic and LLM-judged criteria
  - `evals/run-evals.sh` — Eval runner with baseline comparison mode
- Updated `CONTRIBUTING.md` with quality gate requirements and linter usage

### Scan Results (59 skills)
- Errors: 1 (mnemos/ missing frontmatter)
- Warnings: 85 (19 skills over 500 lines, 30+ with ASCII art)
- Clean: 3 skills

---

## [3.3.2] - 2026-04-07

### Fixed
- Removed stale `Load with: base.md` line from all 53 skills. Since v3.0, base skill loads via `@include` in CLAUDE.md, not per-skill. The leftover line caused confusion about missing files. (Fixes #13)

### Housekeeping
- Closed #10 (Gen Agent Trust Hub security audit) — false positives from scanning markdown code samples as executable code.
- Closed #12 (Dispatch discoverability) — will address skill description metadata in a future cleanup pass.
- Closed #11 (Low quality skills) — will revisit with specific eval criteria.

---

## [3.3.1] - 2026-04-03

### Added
- **Post-Compaction Task Restoration** (Two-Layer Defense)
  - `templates/mnemos-post-compact-inject.sh` — PreToolUse hook (no matcher, fires on ALL tools) that detects compaction via `.mnemos/just-compacted` marker and re-injects the full checkpoint into Claude's context. Fast path ~5ms when no compaction, ~100ms injection when triggered.
  - `build_task_narrative()` in `checkpoint.py` — Reads signals.jsonl to build human-readable summary of recent activity (files edited, read counts, focus area, error patterns). Automatically included in checkpoints.
  - `format_for_post_compact_injection()` in `checkpoint.py` — Formats checkpoint as structured restoration block with goal, constraints, activity narrative, progress, key files, git state.
  - Compaction marker system (`write_compaction_marker`, `check_compaction_marker`, `consume_compaction_marker`) — Atomic marker write/consume to prevent parallel injection.

### Changed
- **`mnemos-pre-compact.sh`** — Enhanced from advisory to assertive. Now includes inline checkpoint content in preservation instructions, writes compaction marker for Layer 2, builds task narrative from signals, and uses stronger verbatim framing.
- **`CheckpointNode`** — Added `task_narrative` (str) and `recent_files` (list[dict]) fields for richer checkpoint content.
- **`settings.json`** — Added new PreToolUse entry (no matcher) for `mnemos-post-compact-inject.sh` before the existing Edit|Write matcher.
- **`SKILL.md`** — Documented post-compaction recovery mechanism.
- **`README.md`** — Rewrote Mnemos section with two-layer defense architecture, resilience failure mode table, "why not just a plain file" rationale, and post-compaction restoration flow diagram.

## [3.3.0] - 2026-04-03

### Added

#### Mnemos — Task-Scoped Memory Lifecycle
Agents crash when context fills up. Claude Code's compaction is lossy — it summarizes everything uniformly. Mnemos solves this with typed memory, continuous fatigue monitoring, and checkpoint/resume.

- **`scripts/mnemos/`** — Python package (zero external dependencies)
  - `models.py` — MnemoNode (8 types with typed eviction policies), FatigueState, CheckpointNode
  - `store.py` — SQLite MnemoGraph storage with mnemo_nodes, checkpoints, fatigue_log tables
  - `fatigue.py` — 4-dimension fatigue model from passively observed signals (no agent cooperation needed)
  - `signals.py` — Behavioral signal collection from hooks (scope scatter, re-read ratio, error density)
  - `checkpoint.py` — CheckpointNode write/load with iCPG bridge, git state capture, formatted resume output
  - `consolidation.py` — Micro-consolidation: compress ResultNodes, evict cold ContextNodes, decay weights
  - `__main__.py` — CLI: init, status, fatigue, checkpoint, resume, consolidate, nodes, add, bridge-icpg

- **4-Dimension Fatigue Model** (all passively observed from hooks):
  - Token utilization (0.40) — real context_window.used_percentage from statusline
  - Scope scatter (0.25) — unique directories in recent tool calls (from PreToolUse)
  - Re-read ratio (0.20) — files Read more than once, strongest signal of context loss (from PreToolUse)
  - Error density (0.15) — failed tool calls ratio (from PostToolUse)
  - States: FLOW (0-0.4), COMPRESS (0.4-0.6), PRE-SLEEP (0.6-0.75), REM (0.75-0.9), EMERGENCY (0.9+)

- **Auto-Feeding Token Signal**:
  - `templates/mnemos-statusline.sh` — Statusline receives `context_window` JSON from Claude Code, writes `fatigue.json`, delegates display to ccusage (if installed) or shows simple context %
  - JSONL fallback in PostToolUse — reads conversation JSONL to estimate context usage when statusline not configured (0.75 correction factor for cache overhead, ~1-2pp accuracy)
  - `statusLine` config added to `templates/settings.json` — auto-activates on install, no separate configuration needed

- **Fatigue-Aware Hook System**:
  - `templates/mnemos-pre-edit.sh` — PreToolUse: logs file signals, reads fatigue, auto-checkpoints at 0.60+, auto-consolidates at 0.40+, includes iCPG context
  - `templates/mnemos-post-tool.sh` — PostToolUse: logs tool success/failure for error density, auto-feeds token signal from JSONL when statusline is stale
  - `templates/mnemos-session-start.sh` — SessionStart: loads checkpoint on resume, bridges iCPG state
  - `templates/mnemos-pre-compact.sh` — PreCompact: emergency checkpoint + typed preservation priorities (NEVER DROP goals/constraints, OK TO DROP file contents)
  - `templates/mnemos-stop-checkpoint.sh` — Stop: writes final session checkpoint

- **MnemoNode Eviction Policies**:
  - GoalNodes, ConstraintNodes, CheckpointNodes, HandoffNodes: NEVER evicted
  - ResultNodes, WorkingNodes, SkillNodes: compressed first (summary kept), then evictable
  - ContextNodes: evictable when activation weight drops below threshold

- **iCPG Bridge**: `mnemos bridge-icpg` imports ReasonNodes as GoalNodes, postconditions/invariants as ConstraintNodes

- **Skill + Commands**:
  - `skills/mnemos/SKILL.md` — Full skill documentation with fatigue states, CLI reference, agent instructions
  - `commands/mnemos-status.md` — `/mnemos-status` slash command
  - `commands/mnemos-checkpoint.md` — `/mnemos-checkpoint` slash command

- **Documentation**:
  - `docs/mnemos-implementation.md` — Implementation addendum for the Mnemos RFC

### Changed

#### iCPG Fixes
- `scripts/icpg/bootstrap.py` — Fixed `_get_commits()` git log parsing (was producing 0 symbols linked)
- `scripts/icpg/drift.py` — Added `check_file_drift()` for fast, file-scoped drift (O(symbols-in-file))
- `scripts/icpg/__main__.py` — Added `drift file <path>` subcommand, `_resolve_path()` for relative path handling
- `templates/icpg-pre-edit.sh` — Now includes file-scoped drift detection alongside context and constraints

#### Settings Template
- `templates/settings.json` — Added `statusLine` config for auto-feeding token signal, Mnemos hooks replace standalone iCPG hooks, added PostToolUse hook, added mnemos permission allows
- `templates/CLAUDE.md` — Added `@.claude/skills/mnemos/SKILL.md` to skill includes

---

## [3.2.0] - 2026-04-02

### Added

#### iCPG Full Implementation (Intent-Augmented Code Property Graph)
- **`scripts/icpg/`** — Python CLI package implementing the full iCPG RFC v8
  - `models.py` — ReasonNode, Symbol, Edge, DriftEvent data models with Design by Contract (preconditions, postconditions, invariants)
  - `store.py` — SQLite storage layer with 4 tables, WAL mode, indexed queries
  - `symbols.py` — Language-aware symbol extraction: Python (AST), TypeScript/JS (regex), Go, Rust, Elixir
  - `drift.py` — 6-dimension drift detection: spec, decision, ownership, test, usage, dependency
  - `contracts.py` — Design by Contract layer with LLM inference (Claude/OpenAI) and heuristic fallback
  - `vectors.py` — Tiered duplicate detection: ChromaDB → TF-IDF → exact match fallback
  - `bootstrap.py` — Git history inference: cluster commits, LLM-infer ReasonNodes, link symbols
  - `__main__.py` — CLI with subcommands: init, create, record, query, drift, bootstrap, status
  - `pyproject.toml` — pip-installable with optional deps (chromadb, sentence-transformers, openai)

- **3 Canonical Pre-Task Queries** (RFC Section 2.1):
  - `icpg query prior "<goal>"` — Vector-based duplicate detection before starting work
  - `icpg query constraints <file>` — Get invariants/contracts for files being modified
  - `icpg query risk <symbol>` — Drift score, ownership history, modification count

- **Hook Integration**:
  - `templates/icpg-pre-edit.sh` — PreToolUse hook: injects intent context + constraints before every Edit/Write
  - `templates/icpg-stop-record.sh` — Stop hook: auto-records symbols to active ReasonNode after implementation

- **Slash Commands**:
  - `commands/icpg-impact.md` — `/icpg-impact <id>` blast radius visualization
  - `commands/icpg-why.md` — `/icpg-why <symbol>` trace symbol to creating intent
  - `commands/icpg-drift.md` — `/icpg-drift` full drift report across all dimensions
  - `commands/icpg-bootstrap.md` — `/icpg-bootstrap` infer intents from git history

### Changed

#### iCPG Skill Rewrite
- **`skills/icpg/SKILL.md`** — Complete rewrite aligning with RFC v8
  - ReasonNode now carries formal contracts (preconditions, postconditions, invariants)
  - Drift formally defined as predicate failure (not vague metric)
  - 6-dimension drift model with 0-1 severity scores per dimension
  - CLI reference for all `icpg` subcommands
  - Hook integration documentation (PreToolUse + Stop)
  - Agent Teams integration section with updated pipeline

#### Agent Team iCPG Integration
- **`skills/agent-teams/agents/team-lead.md`** — Team lead now creates ReasonNodes and checks for duplicates before creating task chains
- **`skills/agent-teams/agents/feature.md`** — Feature agents query constraints/risk before implementing, auto-record symbols after
- **`skills/agent-teams/agents/quality.md`** — Quality agent runs drift checks during GREEN verify, validates spec-intent alignment
- **`skills/agent-teams/SKILL.md`** — Updated "Integration with Existing Skills" table with iCPG + code-graph entries

#### Settings Template
- **`templates/settings.json`** — Added PreToolUse hook (icpg-pre-edit.sh), Stop hook extension (icpg-stop-record.sh), icpg permission allows

---

## [3.1.0] - 2026-04-02

### Added

#### iCPG Skill (Initial Spec)
- **`skills/icpg/SKILL.md`** — Initial iCPG skill spec (now superseded by 3.2.0 full implementation)

---

## [3.0.0] - 2026-03-31

### Breaking Changes

This release aligns Claude Bootstrap with how Claude Code actually works internally. Several features that referenced non-existent infrastructure have been replaced with real Claude Code mechanisms.

- **Ralph Wiggum plugin removed** — The `/ralph-loop` command, `claude-plugins-official` marketplace, and plugin stop-hook mechanism never existed in Claude Code. All references removed.
- **TDD loops now use real Stop hooks** — Claude Code's Stop hook (exit code 2 feeds stderr back to the model) replaces the fake plugin. `scripts/tdd-loop-check.sh` runs tests/lint/typecheck after each response.
- **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` removed** — Agent spawning and task management are standard Claude Code features, not gated behind an env var. All references removed.
- **CLAUDE.md template uses `@include` directives** — Skills are loaded via `@.claude/skills/base/SKILL.md` syntax which Claude Code resolves at parse time (recursive, max depth 5, cycle detection).
- **Quality gates moved from CLAUDE.md to `.claude/rules/`** — Rules use YAML frontmatter with `paths:` globs for conditional activation.
- **"STRICTLY ENFORCED" / "Non-Negotiable" language removed** — Claude Code treats CLAUDE.md as user-level context (not system prompt) wrapped in `<system-reminder>` tags with "may or may not be relevant" caveat. Aggressive language wastes tokens without creating binding constraints.

### Added

#### Stop Hook TDD Loops
- **`templates/tdd-loop-check.sh`** — Universal TDD loop script for Stop hooks
  - Runs tests, lint, typecheck after each Claude response
  - Exit 0 (all pass) = Claude stops; Exit 2 (failures) = stderr fed back to Claude
  - Iteration counter with configurable max (default 25)
  - Detects project type (Node.js/Python) and runs appropriate commands
  - Distinguishes code errors (loop) from environment errors (stop)

- **`templates/settings.json`** — Pre-configured Claude Code settings
  - Stop hook configuration for TDD loops
  - SessionStart hook for auto-context injection
  - Permission allow rules: test runners, linters, git read commands, gh CLI
  - Permission deny rules: `rm -rf`, `git push --force`, writing `.env` files
  - Ready to copy into any project's `.claude/settings.json`

#### Conditional Rules System
- **`.claude/rules/` directory** with 7 rule files using proper YAML frontmatter:
  - `quality-gates.md` — Always active: 20 lines/function, 200 lines/file, 3 params, 80% coverage
  - `tdd-workflow.md` — Always active: RED-GREEN-VALIDATE workflow
  - `security.md` — Always active: no secrets in code, parameterized queries, bcrypt
  - `react.md` — Active on `**/*.tsx`, `**/*.jsx`, `src/components/**`
  - `typescript.md` — Active on `**/*.ts`, `**/*.tsx`
  - `python.md` — Active on `**/*.py`
  - `nodejs-backend.md` — Active on `src/api/**`, `src/routes/**`, `server/**`

#### CLAUDE.local.md
- **`templates/CLAUDE.local.md`** — Private developer override template
  - Not checked into git (higher priority than project CLAUDE.md)
  - Template with common overrides: preferences, local environment, quality gate tweaks

#### Agent Definition Frontmatter
- All 6 agent definitions now use proper Claude Code frontmatter:
  - `name` — Agent identifier
  - `description` — When-to-use hint
  - `model` — Model selection (sonnet, inherit)
  - `tools` — Tool allowlist (e.g., `[Read, Glob, Grep, TaskCreate]`)
  - `disallowedTools` — Tool denylist (e.g., `[Write, Edit, Bash]`)
  - `maxTurns` — Maximum agentic turns before stopping
  - `effort` — Thinking depth (medium/high)

#### @include Directives in CLAUDE.md
- CLAUDE.md template now uses `@.claude/skills/base/SKILL.md` syntax
- Claude Code resolves these at load time (recursively inlined)
- Skills actually become part of the prompt instead of decorative text

#### CLAUDE.md Template Structure
- Added **Project Structure** section — tells Claude where things live without filesystem exploration
- Added **Key Decisions** section — prevents Claude from re-litigating settled architectural choices
- Added **Conventions** section — patterns Claude should follow (test colocation, API shape, etc.)
- Added **Don't** section — short guardrails (no .env writes, no secret leaks)
- Removed Session Persistence section (belongs in skills, not root template)

#### PreCompact Hook for Smarter Compaction
- **`templates/pre-compact.sh`** — PreCompact hook that injects project-specific preservation priorities into the compaction summarizer
  - Auto-detects project type (TypeScript, Python, Next.js, FastAPI, Flutter, etc.)
  - Finds schema files (Drizzle, Prisma, SQLAlchemy) and tells summarizer to preserve all schema discussion verbatim
  - Finds API directories and tells summarizer to preserve exact endpoint paths, request/response shapes
  - Extracts Key Decisions from CLAUDE.md and tells summarizer to reference them by name
  - Injects live git state (branch, uncommitted changes, staged files) into summary priorities
  - Tells summarizer to preserve exact error messages and fix context (not paraphrased)
  - Tells summarizer what NOT to preserve (dead ends, full file contents, formatting noise)
  - Zero overhead during normal usage — only runs when compaction fires
  - Configured in `.claude/settings.json` under `hooks.PreCompact`

#### Full Skill Frontmatter (all 57 skills)
- Added undocumented-but-functional Claude Code skill frontmatter to all 57 skills:
  - `when-to-use` — guidance for when Claude should invoke the skill
  - `user-invocable` — 11 skills are user-invocable (code-review, codex-review, gemini-review, security, existing-repo, ticket-craft, workspace, cpg-analysis, playwright-testing, ai-models), 46 are model-only
  - `effort` — thinking depth per skill (6 high, 47 medium, 4 low)
  - `paths` — file glob patterns for 24 language/framework/database skills (e.g., `["**/*.py"]` for Python, `["**/*.tsx"]` for React)
  - `allowed-tools` — restricted tool access for 3 review/security skills (`[Read, Glob, Grep, Bash]`)

### Changed
- `install.sh` now copies rules/, templates/, and no longer checks for Ralph Wiggum plugin
- `iterative-development/SKILL.md` completely rewritten for Stop hooks
- `base/SKILL.md` — Ralph Wiggum auto-invoke section replaced with Stop hook explanation
- `agent-teams/SKILL.md` — Removed experimental env var requirement
- `commands/spawn-team.md` — Removed env var check, removed Shift+Up/Down and Ctrl+T UI references
- All agent definitions in `skills/agent-teams/agents/` rewritten with frontmatter
- Total files: 57 skills + 7 conditional rules + 3 templates

### Removed
- All Ralph Wiggum plugin references (`/ralph-loop`, `/plugin install`, `--completion-promise`, `<promise>` tags)
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` env var requirement
- Plugin marketplace references (`claude-plugins-official`)
- `Shift+Up/Down` and `Ctrl+T` UI interaction assumptions
- "STRICTLY ENFORCED" and "Non-Negotiable" language throughout

### Migration

```bash
cd "$(cat ~/.claude/.bootstrap-dir)"
git pull
./install.sh

# Then in each project:
claude
> /initialize-project
# Will update to v3.0.0 structure
```

**Manual steps for existing projects:**
1. Copy `templates/settings.json` to `.claude/settings.json`
2. Copy `templates/tdd-loop-check.sh` to `scripts/tdd-loop-check.sh` and `chmod +x`
3. Replace skill listings in CLAUDE.md with `@include` directives
4. Copy `rules/` files to `.claude/rules/`
5. Add `CLAUDE.local.md` to `.gitignore`
6. Remove `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` from environment

---

## [2.7.0] - 2026-03-23

### Added

#### Tiered Code Graph System (MCP-based)
- **Code Graph skill** (`code-graph/SKILL.md`) - Always-on code intelligence via MCP
  - "Graph first, file second" workflow — Claude queries the graph before reading files
  - Integrates with codebase-memory-mcp: 14 MCP tools, 64 languages, sub-ms queries
  - Decision tables for when to use graph vs direct file reads
  - Workflow: LOCATE → UNDERSTAND → BLAST → TRACE → CHANGE → VERIFY
  - Anti-patterns guide for common graph-ignoring mistakes

- **CPG Analysis skill** (`cpg-analysis/SKILL.md`) - Opt-in deep code analysis
  - Tier 2: Joern CPG via CodeBadger MCP (40+ tools, AST+CFG+CDG+DDG+PDG)
    - Control flow graph analysis, data flow tracing, dead code detection
    - CPGQL query examples for common analysis patterns
    - 12 language support (Java, Python, TypeScript, Go, C/C++, etc.)
  - Tier 3: CodeQL MCP for interprocedural taint analysis and security auditing
    - OWASP vulnerability detection, source-to-sink data flow
    - 10+ languages including Rust (which Joern doesn't support)
  - Combined workflow: Tier 1 scope → Tier 2 flow → Tier 3 security

- **Graph tools installer** (`scripts/install-graph-tools.sh`)
  - Platform-detecting installer (macOS/Linux, ARM64/AMD64)
  - `--joern` flag for Tier 2 (Docker + Python setup)
  - `--codeql` flag for Tier 3 (CodeQL CLI + query packs)
  - `--all` flag for all tiers

- **Post-commit graph hook** (`hooks/post-commit-graph`)
  - Lightweight (~10ms) hook that signals codebase-memory-mcp file watcher
  - Filters to code files only, never blocks git workflow
  - Auto-installed by `/initialize-project`

- **Graph freshness check** (`hooks/workspace/check-graph-freshness.sh`)
  - Session-start advisory warns if graph data is stale
  - Cross-platform timestamp comparison (macOS/Linux)

#### Initialize Project Updates
- New question 4b: "Code graph analysis level?" (Standard/Deep/Security/Full)
- New Step 4b: Automatic MCP server configuration (`.mcp.json`)
- `.code-graph/` auto-added to `.gitignore`
- Post-commit graph hook auto-installed
- CLAUDE.md template now includes "Code Graph (MCP)" section
- Summary output shows graph tier configuration

### Changed
- Total skills increased from 55 to **57 skills**
- `install.sh` now copies `install-graph-tools.sh` to `~/.claude/`
- `install.sh` summary output includes graph tools commands

---

## [2.6.0] - 2026-02-14

### Added

#### AI-Native Ticket Writing
- **Ticket Craft skill** - Write Jira/Asana/Linear tickets optimized for Claude Code execution
  - INVEST+C criteria: standard INVEST plus "Claude-Ready" verification
  - 4 ticket templates: Feature, Bug, Tech Debt, Epic Breakdown
  - Claude Code Context section: file refs, pattern refs, verification commands, constraints
  - Claude Code Ready Checklist: 16-point validation before tickets enter sprint
  - Anti-patterns guide: 6 common ticket-writing mistakes that cause AI agents to fail
  - Story point calibration for AI agents (different from human estimation)
  - Epic slicing techniques: by workflow, data variation, user role, CRUD, happy path
  - Given-When-Then acceptance criteria format
  - Integration guide for Jira, Asana, Linear, and GitHub Issues
  - Maps tickets directly to the agent-teams 10-task pipeline

#### Bug Fixes
- **Fix pre-push hook false positive** - Hook was blocking pushes even when review passed with 0 Critical/High issues (fixes #8, reported by @shawnyeager)
  - `grep` pattern matched "Critical" in table headers and pass messages
  - Now checks for explicit `Status: ✅ PASS` / `Status: ❌` lines instead

#### Community Contributions
- **Flexible install directory** - Bootstrap can now be cloned anywhere, not just `~/.claude-bootstrap` (PR #9 by @victortrac)
  - Install path saved to `~/.claude/.bootstrap-dir` for runtime resolution
  - Removes fragile symlink approach
- **Workspace skill frontmatter fix** - Added missing YAML frontmatter to workspace skill (PR #9 by @victortrac)

### Changed
- Total skills increased from 54 to **55 skills**

### Contributors
- @victortrac - Flexible install path, workspace skill fix (PR #9)
- @shawnyeager - Pre-push hook bug report (#8)

---

## [2.5.0] - 2026-02-07

### Added

#### Agent Teams (Default Workflow)
- **Agent Teams skill** - Coordinated team of AI agents as the default development workflow
  - Strict TDD pipeline: Specs > Tests > Fail > Implement > Test > Review > Security > Branch > PR
  - Task dependency chains enforce pipeline ordering (no step can be skipped)
  - Multiple features run in parallel with shared verification agents
  - Quality gates at every stage with cross-agent verification

- **Default agent roster** (5 permanent agents):
  - **Team Lead** - Orchestration only (delegate mode), task breakdown, feature agent spawning
  - **Quality Agent** - TDD verification (RED/GREEN phases), spec review, coverage >= 80%
  - **Security Agent** - OWASP scanning, secrets detection, dependency audit
  - **Code Review Agent** - Multi-engine code review (Claude/Codex/Gemini)
  - **Merger Agent** - Feature branches, PR creation via `gh` CLI

- **Feature agents** - One per feature, each follows the strict pipeline end-to-end
  - Writes spec, tests, implementation, validation
  - Hands off to Quality, Review, Security, Merger at each gate

- **Agent definition files** in `skills/agent-teams/agents/`:
  - `team-lead.md`, `quality.md`, `security.md`, `code-review.md`, `merger.md`, `feature.md`
  - Copied to `.claude/agents/` during project initialization

- **`/spawn-team` command** - Spawn the agent team on any project
  - Checks prerequisites (env var, agent definitions, feature specs)
  - Spawns all agents and creates task dependency chains
  - Shows team status summary

- **10-task dependency chain per feature**:
  1. Spec → 2. Spec Review → 3. Tests → 4. RED Verify → 5. Implement →
  6. GREEN Verify → 7. Validate → 8. Code Review → 9. Security Scan → 10. Branch+PR

### Changed
- Total skills increased from 53 to **54 skills**
- `/initialize-project` Phase 6 now sets up agent team by default (replaces manual next steps)
- CLAUDE.md template includes agent teams section
- `team-coordination.md` superseded by `agent-teams.md` for automated coordination

---

## [2.4.0] - 2026-01-20

### Added

#### Multi-Repo Workspace Awareness
- **Workspace skill** - Dynamic multi-repo and monorepo awareness for Claude Code
  - Workspace topology discovery (monorepo, multi-repo, hybrid detection)
  - Dependency graph generation (who calls whom)
  - API contract extraction (OpenAPI, GraphQL, tRPC, TypeScript, Pydantic)
  - Key file identification with token estimates
  - Cross-repo capability index (search before reimplementing)
  - Token budget management (P0-P3 priority allocation)

- **`/analyze-workspace` command** - Full workspace analysis
  - Phase 1: Topology discovery (~30s)
  - Phase 2: Module analysis (~60s)
  - Phase 3: Contract extraction (~45s)
  - Phase 4: Dependency graph (~30s)
  - Phase 5: Key file identification (~30s)
  - Generates TOPOLOGY.md, CONTRACTS.md, DEPENDENCY_GRAPH.md, KEY_FILES.md, CROSS_REPO_INDEX.md

- **`/sync-contracts` command** - Lightweight incremental contract sync
  - Checks only contract source files (~15s)
  - Diff mode to preview changes
  - Validate mode to check consistency
  - Lightweight mode for hooks

#### Contract Freshness System
- **Session start hook** - Staleness check (~5s, advisory)
- **Post-commit hook** - Auto-sync when contracts change (~15s)
- **Pre-push hook** - Validation gate (~10s, blocking)
- `.contract-sources` file to track monitored files
- Freshness indicators: 🟢 Fresh, 🟡 Stale, 🔴 Outdated, ⚠️ Drift

#### Cross-Repo Change Detection
- Automatic detection when changes affect other modules
- Impact analysis with recommended action order
- Breaking change protocol

### Changed
- Total skills increased from 52 to **53 skills**
- Added 3 new commands: `/analyze-workspace`, `/sync-contracts`, `/workspace-status`
- Added 3 workspace hooks for contract freshness

---

## [2.3.0] - 2026-01-17

### Added

#### Google Gemini Code Review
- **Gemini Review skill** - Google Gemini CLI for code review with Gemini 2.5 Pro
  - 1M token context window - analyze entire repositories at once
  - Free tier: 1,000 requests/day with Google account
  - Code Review Extension: `/code-review` command in Gemini CLI
  - Headless mode for CI/CD: `gemini -p "prompt"`
  - Benchmarks: 63.8% SWE-Bench, 56.3% Qodo PR, 70.4% LiveCodeBench

- **Multi-engine code review** - `/code-review` now supports up to 3 engines
  - Claude (built-in) - quick, context-aware reviews
  - OpenAI Codex - 88% security issue detection
  - Google Gemini - 1M token context for large codebases
  - Dual engine mode - run any two engines, compare findings
  - Triple engine mode - maximum coverage for critical/security code

- **GitHub Actions workflows** for all configurations
  - Gemini-only workflow
  - Triple engine (Claude + Codex + Gemini) workflow
  - Updated dual engine workflow

### Changed
- Total skills increased from 51 to **52 skills**
- Updated `/code-review` to support engine selection: `--engine claude,codex,gemini`
- Added `--gemini` and `--all` shortcuts for common configurations

---

## [2.2.0] - 2026-01-17

### Added

#### Existing Repository Support
- **Existing Repo skill** - Analyze existing codebases, maintain structure, setup guardrails
  - Repo structure detection (monorepo, full-stack, frontend-only, backend-only)
  - Tech stack auto-detection (TypeScript, Python, Flutter, Android, etc.)
  - Convention detection (naming, imports, exports, test patterns)
  - Guardrails audit (pre-commit hooks, linting, formatting, type checking)
  - Structure preservation rules - work within existing patterns, don't reorganize
  - Gradual implementation strategy for adding guardrails to legacy projects
  - Cross-repo coordination for separate frontend/backend repos

- **`/analyze-repo` command** - Quick analysis of any existing repository
  - Directory structure mapping
  - Guardrails status audit (Husky, pre-commit, ESLint, Ruff, commitlint, etc.)
  - Convention detection and documentation
  - Generates analysis report with recommendations
  - Offers to add missing guardrails
  - **Auto-triggered** by `/initialize-project` when existing codebase detected

#### Initialize Project Enhancement
- **Auto-analysis for existing codebases** - `/initialize-project` now automatically analyzes existing repos before making changes
- **User choice after analysis** - Options: skills only, skills + guardrails, full setup, or just view analysis
- **Existing-repo skill auto-copied** - When working with existing codebases

#### Guardrails Setup (for JS/TS and Python)
- **Husky + lint-staged** setup for JavaScript/TypeScript projects
- **pre-commit framework** setup for Python projects
- **commitlint** configuration for conventional commits
- **ESLint 9 flat config** template
- **Ruff + mypy** configuration for Python

### Changed
- Total skills increased from 50 to **51 skills**
- Updated README with `/analyze-repo` usage pattern

---

## [2.1.0] - 2026-01-17

### Added

#### Mobile Development (contributed by @tyr4n7)
- **Android Java skill** - MVVM architecture, ViewBinding, Espresso testing, GitHub Actions CI
- **Android Kotlin skill** - Coroutines, Jetpack Compose, Hilt DI, MockK/Turbine testing
- **Flutter skill** - Riverpod state management, Freezed models, go_router, mocktail testing
- **Android/Flutter auto-detection** - `/initialize-project` now detects Flutter, Android Java, and Android Kotlin projects

#### Database Skills (addresses #7)
- **Firebase skill** - Firestore, Auth, Storage, real-time listeners, security rules, offline persistence
- **Cloudflare D1 skill** - Serverless SQLite with Workers, Drizzle ORM integration, migrations
- **AWS DynamoDB skill** - Single-table design, GSI patterns, SDK v3 TypeScript/Python
- **AWS Aurora skill** - Serverless v2, RDS Proxy, Data API, connection pooling for Lambda
- **Azure Cosmos DB skill** - Partition key design, consistency levels, change feed, SDK patterns

#### Code Review Enhancements
- **Codex Review skill** - OpenAI Codex CLI for code review with GPT-5.2-Codex (88% detection rate)
- **Code review engine choice** - `/code-review` now lets you choose: Claude, OpenAI Codex, or both engines
- **Dual engine review mode** - Run both Claude and Codex, compare findings, catch more issues
- **CI/CD templates** - GitHub Actions workflows for Claude, Codex, and dual-engine reviews

### Changed
- Total skills increased from 44 to **50 skills**
- Updated README with new database and mobile skill listings

### Contributors
- @tyr4n7 - Android Java, Android Kotlin, Flutter skills and auto-detection
- @johnsfuller - Feature request for database skills (#7)

---

## [2.0.0] - 2026-01-08

### Breaking Changes
- **Skills structure changed** - Skills now use folder/SKILL.md structure instead of flat .md files
  - Before: `~/.claude/skills/base.md`
  - After: `~/.claude/skills/base/SKILL.md`
- All skills now require YAML frontmatter with `name` and `description` fields

### Added
- **Validation test** (`tests/validate-structure.sh`) - Validates skills structure, commands, hooks
  - `--full` mode: All 142 checks
  - `--quick` mode: Essential checks for initialize-project
- **Phase 0 validation** in `/initialize-project` - Checks bootstrap installation before setup
- **Conversion script** (`scripts/convert-skills-structure.sh`) - Migrates flat skills to folder structure
- Install script now runs validation automatically
- Symlink created at `~/.claude-bootstrap` for easy access to validation tools

### Fixed
- Skills now load properly in Claude Code (fixes #1)
- Install script properly copies skill folders instead of merging contents

### Migration
```bash
cd ~/.claude-bootstrap
git pull
./install.sh
```

---

## [1.5.0] - 2026-01-07

### Added
- **Code Deduplication skill** - Prevent semantic code duplication with capability index
- **Team Coordination skill** - Multi-person projects with shared state and todo claiming
- `/check-contributors` command - Detect solo vs team projects
- `/update-code-index` command - Regenerate CODE_INDEX.md
- Pre-push hook for code review enforcement

### Changed
- Code reviews now mandatory before push (blocks on Critical/High issues)

---

## [1.4.0] - 2026-01-06

### Added
- **Code Review skill** - Mandatory code reviews via `/code-review`
- **Commit Hygiene skill** - Atomic commits, PR size limits
- Pre-push hooks installation script

---

## [1.3.0] - 2026-01-05

### Added
- **MS Teams Apps skill** - Teams bots and AI agents with Claude/OpenAI
- **Reddit Ads skill** - Agentic ad optimization service
- **PWA Development skill** - Service workers, caching, offline support

---

## [1.2.0] - 2026-01-04

### Added
- **Playwright Testing skill** - E2E testing with Page Objects
- **PostHog Analytics skill** - Event tracking, feature flags
- **Shopify Apps skill** - Remix, Admin API, checkout extensions

---

## [1.1.0] - 2026-01-03

### Added
- Session management with automatic state tracking
- Decision logging for architectural choices
- Code landmarks for quick navigation

---

## [1.0.0] - 2026-01-01

### Added
- Initial release with 30+ skills
- `/initialize-project` command
- TDD-first workflow with Ralph Wiggum loops
- Security-first patterns
- Support for Python, TypeScript, React, React Native
- Supabase integration skills
- AI/LLM patterns for Claude and OpenAI
