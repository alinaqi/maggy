# Changelog

All notable changes to Claude Bootstrap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [6.25.0] - 2026-05-17

### Added
- **E2E TestKit Plugin** — benchmark, drift detection, intent bug analysis for any project
- **Context-aware benchmark generation** — auto-detects project architecture and generates domain-specific benchmarks
- **Drift detection** — AI compares spec vs implementation, scores divergence
- **Intent bug detection** — finds flaws in original design assumptions
- **Plugin system upgrades** — router auto-registration, heartbeat jobs from manifests
- **Provider plugins extracted** — GitHub, Asana moved from core to plugins
#### Architecture Refactoring — Core → Plugin Extraction
- **Plugin system upgraded** —  now supports router auto-registration and heartbeat job registration
- **PluginManager** accepts FastAPI `app` and `HeartbeatScheduler` — plugins self-register routes and jobs on load
- **Plugin contract**: `plugin.yaml` declares `router: "module:var"` and `heartbeat: [{name, interval, fn}]`
- **Providers extracted from core**: GitHub Issues (`provider-github`), Asana (`provider-asana`) → plugins
- **IssueTrackerProvider protocol** stays in core as abstract interface
- **Forge connector** extracted →  with gap scan heartbeat
- **Kept in core**: routing, memory (Mnemos/Engram), execution, blueprints (learning patterns), competitor intel (autonomous market understanding)
- **8 plugins now**: build-in-public, e2e-testkit, provider-github, provider-asana, forge, and built-in plugins

- **Grok (xAI) integration** — 10th model tier via OpenAI-compatible API at `api.x.ai/v1`
- **10-tier routing**: Qwen3 → Gemini FL → DeepSeek Flash → DeepSeek Pro → Gemini Flash → Gemini CLI → Kimi → Grok → Gemini Pro Search → Codex → Claude
- **Competitor Intelligence Dashboard** — per-project competitor tracking (maggy, chess, edtech)
- **CompetitorIntel service**: auto-discovery, move tracking, threat levels, AI briefings
- **`/api/competitor-intel/{project}`**: competitors, moves, briefing, scan, discover endpoints
- **Usage-aware model routing**: per-model daily budget caps, auto-demote at 50%/80% thresholds
- **Cross-model usage analytics**: `maggy-usage` CLI + `/api/usage/report`
- **Per-response usage summary**: Stop hook shows route, cost, session delta
- **Reddit monitoring**: 21 subreddits, auto-commenting via OAuth2
- **X/Twitter API v2**: search, user lookup, live account monitoring
- **Full AI ecosystem watch map**: 80+ accounts across 8 categories

---

## [6.24.0] - 2026-05-16

### Added
- **Routing landscape comparison** in README — Maggy vs OpenRouter, Martian, Portkey, Semantic Router
- **Three unique differentiators**: fatigue-aware routing, cascading classifier resilience, semantic memory routing
- **Semantic cascading classifier** — `model_escalation.py`: qwen3 → kimi → deepseek-flash → Claude → keyword (keyword only as last resort)
- **Language-agnostic routing** — blast/intent now fully semantic, works across languages and domain jargon

---

## [6.23.0] - 2026-05-16

### Added

#### Build-in-Public Customization System
- **`customization.md`** — user-editable guidelines for channel voice, content rules, brands, and clickouts
- **`/build-in-public enable|disable`** — per-project activation via `projects.json`
- **`/build-in-public add brand <name>`** — explicitly allowlist brand names (all others redacted)
- **`/build-in-public add clickouts to <url>`** — set clickout URLs auto-appended to X posts
- **Per-project state** — `~/.maggy/build-in-public/projects.json` tracks enabled/disabled per project
- **Plugin reads customization on every generation** — no restart needed after edits

#### Buffer GraphQL API Migration
- **GraphQL endpoint** — migrated from deprecated REST `api.bufferapp.com/1` to `api.buffer.com`
- **`createPost` mutation** — posts scheduled via GraphQL with `customScheduled` mode
- **Channel discovery** — org ID + channel IDs auto-fetched via GraphQL queries
- **Auth** — Bearer token header (was query param in old REST API)

#### Content Scheduling
- **22 posts scheduled** — full monthly content calendar (May 18 - Jun 12)
- **8 LinkedIn deep dives** — 2-4 paragraph professional posts, each teaches something
- **14 X posts** — sharp singles + 6-tweet thread, all with `github.com/alinaqi/maggy` clickout
- **No coding stats** — removed "96 files, 14 commits" style metrics per voice guidelines
- **Per-channel differentiation** — LinkedIn teaches, X punches, each with distinct tone

### Fixed
- **PostCompact hook error** — removed invalid `PostCompact` from `settings.json` (not a valid Claude Code hook event)
- **Buffer `UnexpectedError`** — resolved by simplifying special characters in post text

### How It Works with Claude Bootstrap
The build-in-public plugin works standalone via `~/.claude/hooks/plugin-trigger` — no Maggy server needed. Drop the plugin folder into `~/.maggy/plugins/` and trigger events from any Claude Code hook:
```bash
~/.claude/hooks/plugin-trigger on_pr_merged '{"title":"Add auth","branch":"feature/auth"}'
~/.claude/hooks/plugin-trigger on_feature_shipped '{"feature":"JWT login"}'
```

---

## [6.22.0] - 2026-05-16

### Added

#### Plugin System — Event-Driven Architecture
- **`PluginManager`** — auto-discovers plugins from `~/.maggy/plugins/`, `maggy/plugins/`, `plugins/`
- **`HookBus`** — typed event bus with subscribe/emit pattern, async handlers with error isolation
- **`PluginManifest`** — YAML-defined: id, version, permissions, hooks, config schema
- **`/api/plugins`** — list, reload, emit test events via REST API
- **`plugin-trigger` (hook)** — standalone runner for Claude Bootstrap, no Maggy server needed
- **Dynamic module loading** — plugins import at startup, registration lifecycle with `register(bus, manifest)`

#### Build-in-Public Plugin — mWP First Plugin (7/11 Stars)
- **Autonomous storyteller** — notices work (PR merged, feature shipped, review passed), extracts narrative arc, publishes without asking
- **Multi-channel** — per-channel voice: LinkedIn (professional, teaches, 3000 chars) + X (sharp, punchy, 280 chars)
- **AI-powered synthesis** — DeepSeek Flash generates channel-native narratives from event data
- **Auto-redaction** — `anonymize.yaml` replaces sensitive names (company names → generic descriptors), strips revenue/user data via regex
- **Buffer API integration** — multi-profile scheduling per channel with fallback to `posts.jsonl`
- **Playwright screenshots** — captures hero screenshots of deployed features
- **Rate limiting** — configurable max posts/day per channel
- **Per-channel scheduling** — LinkedIn 09:00 UTC, X 10:30 UTC weekdays

#### Build-in-Public Skill
- **`skills/build-in-public/SKILL.md`** — 137-line reference with channel best practices
- What to share (technical decisions, failures, insights) vs never share (revenue, customers)
- Channel-specific formatting, tone, timing, anti-patterns
- Content calendar rhythm: daily X, weekly LinkedIn, per-event triggers
- Engagement rate targets and measurement signals

### Changed
- **`README.md`** — plugin system section with build-in-public as featured plugin
- **`main.py`** — plugin manager initialized at startup, plugins router registered

---

## [6.21.0] - 2026-05-16

### Added

#### Autonomous Plan → Validate → Execute Pipeline
- **`~/bin/validate-plan`** — sends plan to DeepSeek Pro + Codex + Gemini Pro in parallel
- **Multi-model voting** — 2+/3 approvals → auto-execute without user intervention
- **Goal detection** — route-task-hook: CLAUDE tier → PLAN FIRST with auto-validation
- **Approval thresholds**: 3/3 silent execute, 2/3 execute with feedback, 1/3 surface to user, 0/3 revise
- **`CLAUDE.md`** — documented autonomous plan→validate→execute flow

#### Autonomous Testing Agent
- **`services/autonomous_tester.py`** — full test lifecycle: discover → generate → execute → evaluate → fix
- **`api/routes_testing.py`** — `/api/testing/gaps`, `/api/testing/run`, `/api/testing/autonomous`
- **`skills/autonomous-testing/SKILL.md`** — reference for AI-driven test generation
- AI classifies failures as TEST_BUG vs CODE_BUG vs ENV_BUG
- AI auto-repairs TEST_BUGs, escalates CODE_BUGs to CLAUDE tier

#### GitHub Profile README Updated
- **Mission**: "Bringing personal super intelligence to every worker in the world"
- **Multi-model philosophy**: 9-tier routing, memory-first, autonomous agents, right tool for the job

---

## [6.20.0] - 2026-05-16

### Added

#### iCPG-Powered Explore Agent
- **`agents/explore.md`** — enhanced Explorer that uses codebase-memory-mcp graph tools first
- **`search_graph`**, **`trace_path`**, **`get_code_snippet`** over grep/glob for code discovery
- **`query_graph`** for complex dependency analysis and ReasonNode traversal
- Falls back to Grep/Glob/Read only for text content, config, non-code files

#### Plan-vs-Execute Decision Routing
- **route-task-hook** now classifies into PLAN FIRST vs EXECUTE DIRECTLY
- **CLAUDE tier** → "PLAN FIRST — explore, design approach, get approval"
- **DEEPSEEK_PRO / GEMINI_CLI tiers** → "EXECUTE DIRECTLY — no plan needed"
- Prevents unnecessary planning for workhorse coding tasks

#### Gemini CLI Integration
- **`~/bin/gemini-cli`** — full coding agent delegation (v0.42.0)
- Headless mode via `-p`, model selection via `-m` (pro/flash/flash-lite/auto)
- `--skip-trust` for automated environments, `--output-format json`
- Installed and tested: uses gemini-3-flash-preview, full tool support

### Changed
- **`onboard.sh`** — fixed cost display `$0` expansion bug
- **`gemini-cli`** — binary discovery path to avoid `~/bin/gemini` API delegator collision

---

## [6.19.0] - 2026-05-16

### Added

#### Autonomous Multi-Model Review
- **`~/bin/review`** — runs deepseek-pro + kimi + codex in parallel, merges findings
- **`auto-review-hook` (Stop)** — triggers reviews autonomously, no user prompt needed
- **Cascading classifier** for review decisions: qwen3 → kimi → deepseek-flash → skip
- **Dynamic qwen3 gatekeeper** — evaluates git state to decide if review is warranted
- **Cooldown** — minimum 5 turns between checks, 10 turns between reviews

#### Install Integration
- **`bin/`** — all delegation scripts (deepseek, gemini, kimi, qwen3, research, review)
- **`hooks/route-task-hook`** + **`hooks/auto-review-hook`** — packaged for install
- **`install.sh`** — copies scripts to `~/bin/`, hooks to `~/.claude/hooks/`
- **`skills/model-routing/SKILL.md`** — 159-line routing pipeline reference

#### PostCompact Recovery
- **`PostCompact` hook** — `mnemos-post-compact-inject.sh` restores context after compaction
- Routing cache survives compaction via `~/.claude/routing-cache.json`

---

## [6.18.0] - 2026-05-16

### Added

#### Gemini Integration — 9-Tier Model Routing
- **`~/bin/gemini`** — delegation script calling Gemini via OpenAI-compatible endpoint
- **Gemini 2.5 Flash-Lite** (Tier 2, $0.10/$0.40 per M) — bulk extraction, classification, CIG pipelines, cheapest model
- **Gemini 2.5 Flash** (Tier 5, $0.15/$0.60 per M) — multimodal (images, video, audio), brand asset analysis
- **Gemini 3.1 Pro + Search** (Tier 7, $1.25/$10 per M) — deep research, native Google Search grounding, 2M context window
- **`route-task-hook`** — expanded to 9 tiers with GEMINI_FLASH_LITE, GEMINI_FLASH, GEMINI_PRO_SEARCH
- **`model_router.py`** — DEFAULT_TIERS expanded from 6 to 9 entries with Google provider
- **`pi.py`** — DEFAULT_MODELS with Gemini entries and delegation conventions
- **`routing_rules_defaults.py`** — Gemini performance profiles (multimodal, bulk_extraction, deep_research, google_grounding)
- **`chat_router.py`** — added `use gemini` force pattern

### Changed
- **`CLAUDE.md`** — updated routing heuristic: bulk extraction → Gemini Flash-Lite, multimodal → Gemini Flash, deep research → Gemini Pro Search
- **`CLAUDE.md`** — 9-tier table with costs and roles

---

## [6.17.2] - 2026-05-16

### Added
- **Memory comparison table** — README now contrasts Maggy Mnemos vs Codex vs Claude Code across compaction triggers, preservation, transparency, recursive degradation, cross-session memory, team memory, and pre-compaction safety
- **Updated cross-tool table** — added DeepSeek V4 and Memory rows to compatibility matrix

---

## [6.17.1] - 2026-05-16

### Added

#### Research Tool with Auto-Evaluation
- **`~/bin/research`** — multi-backend research script with cascading fallback (deepseek-flash → deepseek-pro)
- **Auto-evaluation** — scores results 0-10 on content quality, structure, length, error detection
- **Backend preference auto-adjust** — tracks scores per backend and promotes the best performer
- **Evaluation log** — `~/.claude/research-eval.jsonl` with per-call scoring
- **Stats command** — `research --eval` shows per-backend success rates and average scores

#### Cascading Classifier Fallback
- **`route-task-hook`** — cascading classifier: qwen3 → kimi → deepseek-flash → cached tier
- **Routing cache** — `~/.claude/routing-cache.json` persists last tier across compactions
- **Per-call logging** — `classifier` field in routing log tracks which model did the classification

#### Tool Fallback Protocol
- Documented in `CLAUDE.md`: WebSearch/WebFetch failures → `~/bin/research` → `~/bin/deepseek`

---

## [6.17.0] - 2026-05-16

### Added

#### Maggy Dashboard UI Overhaul
- **Sidebar navigation** — modern vertical sidebar replacing horizontal tab bar, with grouped sections (Work, Intel, System)
- **Cmd+K / Ctrl+K command palette** — fuzzy project search with keyboard shortcut, instant jump between projects
- **Memory panel** — fatigue gauge with color-coded states (FLOW→COMPRESS→PRE_SLEEP→REM→EMERGENCY), engram stats, recent memories list
- **Progress panel** — real-time execution status per task, active/running/completed indicators with shimmer animations, recent activity signals log
- **Heartbeat indicator** — live status dot with pulse-glow animation, auto-refreshes every 30s
- **Model badge in header** — shows active model, blast score, task type during execution
- **Sidebar fatigue indicator** — compact fatigue percentage with color-coded state
- **CSS variable design system** — consistent dark theme with orange accent, scrollbar styling, badge components

#### Multi-Source Task Aggregator
- **`GET /api/aggregator/tasks`** — unified task list from `_project_specs/todos/` + GitHub Issues + Asana, deduplicated and priority-sorted
- **`POST /api/aggregator/execute-all`** — queue all pending tasks for TDD execution
- **`read_project_specs()`** — parses `active.md` and `backlog.md` markdown checklists into structured task objects

#### Progress Analysis Engine
- **`ProgressEngine`** — cross-model execution tracker with step history, blocker detection, model usage stats
- **Auto-adjust routing** — detects fatigue thresholds and consecutive failures, suggests model escalation
- **Next-action suggestions** — analyzes blocker state, model failures, and unvalidated completions to recommend next steps
- **`ProgressSnapshot`** — structured summary of active/completed/blocked tasks, elapsed time, model distribution

#### Background Heartbeat Jobs
- **`poll_inbox`** — auto-refreshes inbox from GitHub/Asana every 5 minutes (configurable interval)
- **`scan_competitors`** — periodic competitor news scanning for active project
- **`track_research`** — research trend tracking for active project
- All jobs registered in `HeartbeatScheduler` with per-job error isolation and status tracking

#### Generic Test Suite Generator
- **`test_generator.py`** — auto-detects Python (pyproject.toml/setup.py) and TypeScript (package.json) projects
- **Python scaffold** — generates `conftest.py`, `__init__.py`, per-module test stubs, `.coveragerc` with configurable thresholds
- **TypeScript scaffold** — generates `vitest.config.ts` with coverage thresholds, sample test file
- **`write_scaffold()`** — one-call detection + generation + file writing with summary output

### Changed
- **`main.py`** — registered `aggregator_router` for task aggregation endpoints
- **`progress_engine.py`** — new module with task state tracking and routing auto-adjustment
- **`routes_aggregator.py`** — new API routes for multi-source task listing and batch execution

### Stats
- 8 files changed across UI (2), backend (4), heartbeat (1), test gen (1)
- New panels: Memory, Progress (2) in redesigned sidebar
- New API endpoints: 3 (aggregator tasks, execute-all, progress status)
- All existing routing tests pass (38/38)

---

## [6.16.0] - 2026-05-16

### Added

#### Multi-Model Delegation Pattern
- **External model delegation via `~/bin/` scripts** — consistent pattern for calling Qwen3, DeepSeek, Kimi, and Codex from both Claude Code hooks and Maggy's executor
- **6-tier routing hook** — `UserPromptSubmit` hook classifies every prompt via qwen3 into QWEN / DEEPSEEK_FLASH / DEEPSEEK_PRO / KIMI / CODEX / CLAUDE tiers
- **`~/bin/deepseek`** — Python delegation script calling DeepSeek's Anthropic-compatible API via httpx, supports `--flash` / `--pro` flags
- **Project CLAUDE.md** — created with full skill references, routing table, and project structure docs

#### DeepSeek V4 in Maggy Routing
- `model_router.py` — expanded DEFAULT_TIERS from 4 to 6: local → deepseek-flash → deepseek-pro → kimi → codex → claude
- `ai_client.py` — DeepSeek API completion via OpenAI-compatible endpoint with httpx
- `adapters/deepseek.py` — DeepSeek orchestrator adapter registered for deepseek, deepseek-flash, deepseek-pro
- `routing_rules_defaults.py` — docs/tests route to deepseek-pro, security/architecture stay on claude
- `fatigue.py` — split deepseek into flash/pro context windows (128K each)
- `chat_router.py` — added `use deepseek` force pattern
- `pi.py` — DEFAULT_MODELS split into flash/pro, `_build_command` handles delegation script conventions

#### Skill Documentation
- `skills/external-model-delegation/SKILL.md` — complete reference: tier table, delegation script contract, routing hook flow, classification tiers, environment setup

### Tests
- `test_deepseek_routing.py` — 16 new tests for 6-tier routing, cost ordering, provider mapping, strength attributes
- Updated `test_routing_service.py`, `test_benchmark_scenario.py`, `test_multimodel_integration.py` for new tier structure
- 80 routing tests pass, 0 failures

---

## [6.15.0] - 2026-05-16

### Added

#### Mnemos Checkpoint Compatibility & Compact Recovery
- **Backward-compatible checkpoint serialization** — `checkpoint.py` extended with compat-layer serialization so older checkpoint formats deserialize cleanly into current `CheckpointNode` schema
- **`mnemos-compact-recovery.sh`** — New recovery script for post-compaction checkpoint restoration; detects compaction markers and re-injects checkpoint context automatically
- **`test_mnemos_checkpoint_compat.py`** — 162-line test suite for backward-compatible checkpoint round-trips across schema versions
- **`test_executor_bridge.py`** — 101-line test suite for chat executor bridge routing decisions and blast-score thresholds

#### Fatigue-Aware Model Routing
- **Mnemos fatigue wired into model routing** — `model_router.py` now queries fatigue state and adjusts routing: high fatigue biases toward simpler models to reduce context pressure
- **`test_fatigue_routing.py`** — 107-line test suite for fatigue-aware routing decisions

### Fixed

#### Defensive Hook Scripts
- **All hook scripts hardened** — Removed `set -euo pipefail` from all mnemos hooks; added `2>/dev/null || true` guards on `cat`/`jq` stdin reads so hooks never block Claude Code sessions
- **Defensive pattern established**: (1) no strict mode, (2) `INPUT=$(cat 2>/dev/null || true)`, (3) jq with `// empty` fallbacks, (4) always `exit 0` on failure
- **Kimi parser fix** — `history/parsers/kimi.py` improved session detection for cross-tool context injection
- **Executor bridge improvements** — `chat_executor_bridge.py` refined routing logic for actionable vs informational messages

### Changed
- **`models.py`** — Extended Mnemos model definitions with additional fields for checkpoint compat
- **`SKILL.md`** — Updated mnemos skill documentation with compact recovery and compat details
- **`templates/CLAUDE.md`** — Added mnemos compact recovery references
- **`templates/mnemos-post-compact-inject.sh`** — Improved injection logic for post-compaction context restoration

### Stats
- 79 files changed, +5,593 / -144 lines across the full PR
- New test files: 28 test files, **243+ tests passing**, 83% coverage

---

## [6.14.1] - 2026-05-15

### Fixed

#### Mnemos Stability — OOM Prevention and Concurrent Access
- **Bounded signal reads**: `read_recent_signals(n=30)` uses `deque` tail-read instead of loading entire `signals.jsonl` into memory — prevents OOM in long sessions
- **SQLite WAL mode**: `MnemosDB` now enables `PRAGMA journal_mode=WAL` on init — prevents "database is locked" errors when multiple hooks fire concurrently
- **Connection lifecycle**: `MnemosDB` implements context manager protocol (`with MnemosDB() as db:`), hook dispatch uses it to guarantee connection cleanup
- **Constant usage**: `_hook_pre_compact` uses `COMPACT_UTILIZATION` constant instead of hardcoded `0.83`
- **Type safety**: Hook handler signatures changed from `db: object` to `db: MnemosDB`
- **Clean imports**: `extraction.py` uses normal `from pathlib import Path` instead of inline `__import__`
- **8 new tests**: `read_recent_signals` (5 tests including malformed JSONL), WAL mode, context manager lifecycle — total now **243 tests**

---

## [6.14.0] - 2026-05-15

### Added

#### Mnemos Full Implementation — Task-Scoped Memory Lifecycle
- **Tier 0 Core**: `constants.py`, `models.py` (12 node types, Pydantic models), `db.py` + `db_queries.py` (SQLite CRUD + bulk ops), `fatigue.py` (token util with 4-dim upgrade path), `checkpoint.py` (write/read/cooldown), `status.py`, `cli.py` + `cli_hooks.py` + `cli_nodes.py`
- **Tier 1 Lifecycle**: `activation.py` (recency/frequency/centrality composite weights), `scope.py` (tag inference + Jaccard overlap), `signals.py` (JSONL tool call logger), `fatigue_dimensions.py` (4-dim: token 0.40, scatter 0.25, reread 0.20, error 0.15), `extraction.py` (tool-to-node pipeline), `consolidation.py` (micro-consolidation at COMPRESS range), `skills.py` (fingerprint + promotion algebra)
- **Full Tier**: `rem.py` + `rem_slow_wave.py` + `rem_skills.py` + `rem_pruning.py` + `rem_wake.py` (4-phase REM process), `delegation.py` (sub-agent inheritance rules), `merge.py` (5 conflict types, absolute ConstraintNode protection), `orchestrator.py` (5 signal types), `handoff.py` (fleet diagnostics)
- **Backward compat**: `_compat.py` preserves v0 `FatigueTracker` and `SignalLog` APIs
- **230 new tests** across 27 test files, 83% coverage

---

## [6.13.0] - 2026-05-15

### Added

#### Self-Healing System
- **`services/frustration.py`** — Frustration detection service with target taxonomy (app_bug / output_quality / task_difficulty), 5 weighted scoring dimensions (repetition 0.30, escalation 0.25, rapid re-sends 0.20, explicit language 0.15, abandonment 0.10), convergence bonus, and 4 threshold actions (log / adjust / notify / ticket)
- **`services/health_watchdog.py`** — Server health watchdog monitoring processes (PID), HTTP endpoints, and system memory (psutil with sysctl fallback); reports aggregate HEALTHY / DEGRADED / UNHEALTHY status
- **RFC Section 15** — "Self-Healing: Autonomous Fault Detection and Recovery" documenting three-signal-collector architecture, frustration target classification, triage engine, and integration points

#### iCPG Inspection
- **`api/routes_icpg.py`** — New API to browse iCPG reason graphs across all configured codebases: `/api/icpg/overview`, `/{project}/reasons`, `/{project}/drift`, `/{project}/graph`
- Dashboard iCPG tab with aggregate stats, drill-down by project, drift alerts, ReasonNode grouping by status, and SVG force-layout graph visualization

#### Chat UX Overhaul
- Multi-line textarea input with auto-expand (Shift+Enter for newlines, Enter to send)
- Progressive markdown rendering during streaming (debounced at 300ms instead of only after stream ends)
- Sidebar star/collapse — star projects to pin them top, collapse inactive ones; state persisted in localStorage
- Tab button transitions with hover states and active glow
- User messages preserve whitespace/newlines

#### Orchestrator
- **`orchestrator/isolation.py`**, **`merge.py`**, **`worktree.py`** — Worktree-based isolated agent execution with safe merge-back strategies

#### Phase Specs
- 14 phase documents for Maggy v2–v5 roadmap (PI adapter through event spine)

### Fixed
- **Codex executor timeout** — bumped `_POLL_TIMEOUT` from 300s to 600s; Codex planning tasks were timing out at ~298s and falling back to Claude unnecessarily

### Tests
- 13 tests for frustration detection (target classification, score dimensions, thresholds, edge cases)
- 11 tests for health watchdog (PID checks, endpoint checks, memory, aggregate status)
- 14 test files for budget, event spine, worktree isolation/merge, model routing, process intelligence

---

## [6.12.0] - 2026-05-13

### Added

#### Task Blueprints
- **`blueprint_store.py`** — Self-learning repeatable workflows; Maggy captures tool sequences from successful tasks and replays them with cheaper models on similar future tasks (e.g., generating benchmark reports for 16+ companies routes to local after 3 proven examples)
- SQLite-backed blueprint persistence with keyword overlap matching, project scoping, time-decay confidence, and collective matching (3+ similar blueprints prove a pattern)
- **`blueprint_extract.py`** — keyword extraction with path stripping, sha256 fingerprinting, template capture with `{path}`/`{value}` slots
- **`api/routes_blueprints.py`** — `GET /api/blueprints/` and `GET /api/blueprints/match` endpoints
- **`cli_blueprints.py`** — `/blueprints` CLI command with Rich table display (type, keywords, confidence, uses)

#### Session Persistence
- Chat sessions + messages now saved to SQLite, surviving server restarts
- **`services/session_store.py`** — SQLite store with sessions + messages tables, WAL mode, foreign keys

#### Claude CLI Improvements
- `_run_claude` now logs start/pid/exit/errors to `~/.maggy/server.log`
- Per-line 180s timeout prevents stale sessions from hanging forever; `_read_with_timeout` async generator
- Arrow key history — readline import enables up/down command recall in REPL

### Fixed
- **"Task chat-xxx not found"** — executor bridge created ephemeral Task but only passed ID to `executor.start()`, which tried to re-fetch from issue tracker; now passes pre-built Task object directly
- **Executor tasks not completing** — `executor_stream` read session once immediately after `start()` (which returns instantly); now polls session every 2s via `_poll_session()` until status leaves "running", streaming incremental output
- **Background task auto-finish** — `_bg_loop` now uses `select.select` with 0.3s timeout instead of blocking on `Prompt.ask`, so completed tasks display results immediately

### Changed
- Blueprint context injected into messages when routing matches a proven blueprint
- `routes_chat.py` captures tool_use events during streaming and records blueprints after successful completion
- `chat_router.py` checks blueprint store before standard routing; `RouteDecision` has `blueprint_context` field
- `chat_media.py` extracted from `chat.py` (detect_image, detect_document, stream_vision, stream_doc) for quality gate compliance
- `cwd_project()` moved from `cli_chat.py` to `cli_context.py`

---

## [6.11.0] - 2026-05-13

### Added

#### `/rules` Command
- Comprehensive routing rules summary showing task-type overrides, pipeline phases, model performance (strengths + weaknesses), team conventions, stakes classification patterns, and cascade policy in one panel
- **`cli_rules.py`** — `cmd_rules` with `_fmt_overrides`, `_fmt_phases`, `_fmt_perf`, `_fmt_conventions`, `_fmt_stakes`, `_fmt_cascade` formatters
- Full rules API — `/api/routing/rules` now returns pipeline phases, conventions text, stakes patterns, cascade policy, model weaknesses, and override confidence/source (was only returning overrides + strengths)
- `reviewer_heatmap()` client method (was missing from `cli_client.py`)

---

## [6.10.0] - 2026-05-13

### Added

#### Reviewer Evaluation & Knowledge Map
- Tracks reviewer performance (CodeRabbit vs Codex vs local) by finding category (security, performance, style, logic, architecture) with time-decayed scoring; builds knowledge map so Maggy learns which reviewer is better at what
- **`review_scores.py`** — SQLite-backed `ReviewerTable` with `record`, `best_reviewer`, `heatmap`, `compare` (same decay pattern as model rewards)
- **`services/reviewer_eval.py`** — keyword-based finding categorization, `evaluate_review` records to ReviewerTable, `compare_reviewers` for side-by-side
- **`api/routes_review.py`** — `/api/reviewers/heatmap` and `/api/reviewers/compare` endpoints
- `/reviewers` CLI command shows reviewer × category performance heatmap
- Review findings auto-recorded after review-type chat responses complete

---

## [6.9.0] - 2026-05-13

### Added

#### Non-Blocking REPL
- Long-running tasks (CodeRabbit reviews, Codex analysis, etc.) now run in a background thread; REPL stays responsive with `bg>` prompt for `/status` and `/cancel` commands
- **`cli_bg_task.py`** — thread-safe `TaskState` with `start_task`, `cancel_task`, `get_status`, `is_active`, `collect_result`
- `/status` command shows background task progress (model, chunks, tool calls)
- `/cancel` command stops a running background task

### Changed
- `_send_message()` returns `TaskState` for routed messages (background) or `None` for direct (blocking)
- `_repl_loop()` enters `_bg_loop()` when a background task starts, accepting commands during streaming
- `cmd_stats` moved from `cli_repl_cmds.py` to `cli_repl_info.py`
- `SessionState` has `bg_task` field for background task tracking

---

## [6.8.0] - 2026-05-13

### Fixed
- **Session history detection** — Claude parser `_slug()` now preserves full resolved paths instead of basename-only (was losing `/Users/ali/maggy` → `maggy`); Codex parser reads `cwd` from rollout files instead of using user-defined `thread_name`; Kimi parser reads `work_dirs` from `kimi.json` instead of hardcoding empty string
- **Project matching** — `_matches_project()` uses strict resolved-path comparison instead of loose substring matching that caused false positives
- **Context fallback** — `gather_cli_context()` falls back to `session_detect.detect_all()` when HistoryService returns no matches

### Added

#### Verified Context & Chat-to-Executor Bridge
- **`verified_context.py`** — gathers real git state (branch, status, recent commits) and active CLI sessions; injected alongside history so LLMs don't fabricate project state
- **Collapsible thinking** — tool events accumulate during streaming, collapsed summary (`[N tool calls]`) shown after response; `/thinking` command re-expands the last response's tool events
- **`chat_executor_bridge.py`** — routes actionable messages (blast >= 4, non-search/docs/review) through the full executor pipeline (iCPG, TDD, Mnemos, Engram) instead of raw LLM CLI passthrough
- `cli_repl_info.py` extracted from `cli_repl_cmds.py` for session/info/thinking commands

### Changed
- `stream_chunks()` now returns `dict` with `tool_events` list instead of `None`
- `SessionState` has `last_tool_events` field for `/thinking` command
- `_format_sessions()` uses full-path project values (no more basename matching)
- REPL command handlers split across `cli_repl_cmds.py` (routing/budget) and `cli_repl_info.py` (session/info/thinking)

---

## [6.7.0] - 2026-05-13

### Added

#### Tool Progress Display
- CLI now surfaces `tool_use` events from Claude CLI's stream-json, showing what Claude is doing (Read, Edit, Bash, Grep, etc.) as dim progress lines above the spinner, matching Claude Code's work-progress UX
- `_format_tool_use()` renders readable labels per tool type (file paths, commands, patterns)
- `parse_chunks()` replaces `parse_chunk()` — returns list of chunks, extracting both `text` and `tool_use` blocks from assistant messages

### Fixed
- **Model label duplication** — model name (codex, kimi, etc.) no longer repeats on every Live refresh; now printed once above the live area via `console.print` instead of being re-rendered inside the Live display
- **SSE timeout** — increased HTTP streaming timeout from 120s to 600s so long-running Claude/Codex operations don't get killed mid-response; also increased `ai_client.py` subprocess timeout to match
- `_StreamState` simplified — removed `model_label` field; routing/tool events print above Live area, Live only manages spinner + content

---

## [6.6.0] - 2026-05-13

### Changed
- **Claude Code-style streaming UX** — removed knock-knock jokes and joke thread; display is now a clean spinner ("Thinking...") with markdown output, matching Claude Code's minimal style
- Model label shown as dim text instead of a Rule separator
- `/history`, `/sessions`, `/monitor` commands moved to central dispatch in `cli_repl_cmds.py`

### Added

#### Multi-CLI Context Injection
- On startup, Maggy gathers recent session history from Claude Code, Codex, and Kimi and injects it into the first message so the LLM knows what you've been working on across tools
- **`cli_context.py`** — module for history gathering and project matching
- Server accepts `history_context` on session creation and uses it in the first Claude prompt

### Removed
- Knock-knock joke cycling thread and all 15 jokes from `cli_stream.py`
- Threading/lock machinery from `_StreamState`
- `_show_resume_info` startup dump (replaced by context injection)

---

## [6.5.0] - 2026-05-13

### Changed
- **CWD = project** — running `maggy` from any directory uses that directory as the project (like Claude Code), no config lookup needed
- Sessions now matched by `working_dir` path instead of `project_key` name, ensuring correct resume across identically-named folders
- Server accepts any existing directory as a project path (no codebase config required)
- REPL prompt pushed to bottom of terminal after welcome panel

### Removed
- Config-based project detection (`detect_project`, `detect_candidates`, `_is_inside`)
- Multi-project disambiguation prompt

---

## [6.4.0] - 2026-05-12

### Added

#### Claude Code-Style Streaming UX
- CLI REPL now shows animated spinner, model label (`Working with <model> · blast N`), and cycling knock-knock jokes during response streaming
- Web dashboard 4-zone chat layout — top progress shimmer, messages scroll, working zone (model label + jokes), sticky input bar with dividers

### Changed
- Streaming display extracted to `cli_stream.py` for cleaner separation of concerns
- Web chat switched from `/send` to `/send-routed` to display model metadata during streaming
- Jokes and response content render in separate DOM elements (web) / Rich Group zones (CLI), fixing invisible jokes

---

## [6.3.0] - 2026-05-12

### Added

#### Document Processing
- Paste Excel, DOCX, PDF, CSV, JSON, TXT paths in chat; text is extracted locally and forwarded to Claude for analysis
- **Auto-install dependencies** — missing optional packages (openpyxl, python-docx, pymupdf) are pip-installed automatically on first use
- **Ollama → Claude API escalation** — vision and intent classification auto-fallback to Claude API when local models are unavailable
- **`maggy restart`** — new CLI command to stop and restart the server

### Changed
- Intent classifier and blast scorer now use escalation (Ollama → Claude API → keyword fallback)
- Chat models extracted to `chat_models.py` for cleaner architecture

---

## [6.2.0] - 2026-05-12

### Added

#### Semantic Blast Score
- **`services/intent_classifier.py`** — `classify_blast()` estimates task complexity (1-10) via local Ollama model instead of keyword matching. Uses same pattern as `classify_intent()`: JSON prompt, `num_predict: 20`, `/no_think` directive. Falls back to keyword `estimate_blast()` on failure. ~200ms warm, 11/12 accuracy on edge cases.
- **`RoutedChat.decide()`** — now calls `classify_blast()` instead of keyword `estimate_blast()` when no override is provided. Both blast and intent are fully semantic.

#### Ghost-Text Suggestions
- **`static/app.js`** — Claude Code-style autocomplete suggestions in the chat input. Tracks recent messages and response context, shows a light-colored suggestion based on 14 context-aware rules (e.g., after fixing a bug → "now run the tests to verify the fix"). Tab accepts the suggestion, typing clears it.

### Stats
- 887 tests passing (881 + 6 new blast classifier tests)

---

## [6.1.0] - 2026-05-12

### Added

#### Semantic Intent Classification
- **`services/intent_classifier.py`** — Replaces brittle keyword matching with semantic classification via local Ollama model (`qwen3-coder:30b-a3b-q8_0`). Sends a short JSON-mode prompt to `localhost:11434/api/chat`, classifies into: review, security, search, docs, tests, frontend, general. 5s timeout, temperature 0. Falls back to keyword `estimate_type()` when Ollama is unavailable. Zero cost (local model).

#### Natural Language Model Forcing
- **`services/chat_router.py`** — `parse_model_force()` detects "use claude" / "use codex" / "use kimi" / "use local" inline in any chat message. Strips the directive, forces the model regardless of blast score. No flags or config needed — just type "use claude and review my code".

#### Review Task Type
- **`services/chat_router.py`** — Added "review" to `TYPE_KEYWORDS` (review, code_review, pr, pullrequest, audit, inspect, validate, verify) as keyword fallback. Semantic classifier handles primary detection.

#### Chat UX — Input Anchored to Bottom
- **`static/index.html`** — Outer container switched from `min-h-screen` to `h-screen flex flex-col overflow-hidden`. Main fills remaining viewport. Panes take full height. Input bar permanently anchored at bottom like Claude Code.

#### Chat UX — Knock-Knock Jokes While Waiting
- **`static/app.js`** — 50 dev-themed knock-knock jokes (git, docker, async, vim, regex, etc.) cycle every 1.8s while the model is thinking. Stops immediately when the first response chunk arrives.

### Changed
- `RoutedChat.decide()` is now async — calls `classify_intent()` for semantic classification, with keyword `estimate_type()` as degraded fallback path.

### Stats
- 881 tests passing (874 + 7 new intent classifier tests)

---

## [6.0.0] - 2026-05-12

### Added

#### Polyphony Container Orchestration — Parallel Execution
- **`maggy/orchestrator/`** — Polyphony orchestrator integrated as first-class Maggy subpackage. 20 files (~2700 lines) covering Docker container lifecycle, git workspace cloning, adapter routing (Claude/Codex/Kimi), 5-dimension complexity scoring, SQLite state tracking, and 7-state task machine.
- **`orchestrator/async_runtime.py`** — Async wrappers (`asyncio.to_thread`) around sync Docker subprocess calls. Non-blocking container create/start/wait/stop/remove.
- **`orchestrator/decomposer.py`** — LLM-based task decomposition. Asks Claude to split complex tasks into 2-5 independent subtasks. Falls back to single-task on failure. Capped at 5 subtasks.
- **`services/orchestrator.py`** — `OrchestratorService` manages team lifecycle: `spawn_team()` launches containers in parallel via `asyncio.gather`, `_run_one()` handles per-container Docker lifecycle (create → start → wait → logs → remove), `cancel_team()` for graceful shutdown.
- **`services/executor_helpers.py`** — `select_strategy()` decides parallel vs sequential: blast≥7 OR files≥5 OR user_requested → parallel.
- **`api/routes_orchestrator.py`** — REST endpoints: `POST /spawn` (decompose + launch team), `GET /teams` (list), `GET /teams/{id}` (status), `POST /teams/{id}/cancel`, all under `/api/orchestrator/`.
- **`config.py`** — `OrchestratorConfig` dataclass: `enabled`, `max_concurrent` (default 3), `workspace_root`, `container_timeout` (600s), `decompose_threshold` (7).
- **`main.py`** — Orchestrator router registered, service initialized when `orchestrator.enabled = true`.

### Stats
- 868 tests passing (843 + 25 new orchestrator tests)
- 5 new test files: strategy selector, async runtime, decomposer, orchestrator service, orchestrator routes

---

## [5.9.0] - 2026-05-12

### Added

#### Auto-Start — Zero-Config Bootstrap
- **`maggy/main.py`** — Server auto-starts on first CLI command if not already running. No separate `maggy serve` step needed.

#### Qwen3-VL Vision — `/screenshot` Command
- **`maggy/services/vision.py`** — Ollama HTTP vision client for Qwen3-VL (`qwen3-vl:32b`). Base64-encodes images, streams analysis via `POST /api/chat`. Supports `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`.
- **`/screenshot <path> [prompt]`** in REPL — Analyze screenshots for UI review, bug spotting, OCR, design-to-code. Custom prompts supported.

#### Module Extraction — Large Files Decomposed
- **`routing_rules.py`** split into 3 files — `routing_rules.py` (core), `routing_rules_defaults.py` (tier definitions), `routing_rules_io.py` (file I/O). Was 450+ lines, now each under 200.
- **`services/executor.py`** split into 4 files — `executor.py` (orchestration), `executor_helpers.py` (subprocess), `executor_prompts.py` (prompt templates), `executor_types.py` (dataclasses). Was 600+ lines.
- **`services/chat.py`** split — streaming extracted to `chat_stream.py`.
- **New service modules**: `cascade.py` (cascading model fallback), `context_compactor.py` (context size management), `convention_inferrer.py` (project convention detection), `convention_scanner.py` (file pattern scanning), `output_reviewer.py` (LLM output quality check), `stakes.py` (task risk assessment), `tdd_verifier.py` (TDD pipeline verification).
- **`cikg/graph.py`** decomposed — queries extracted to `cikg/queries.py`.

#### Reward Recording
- **`routes_chat.py`** — Routed chat endpoint now records routing outcomes (model, task type, blast score, quality score) after completion via `RoutingService.record_outcome()`. Feeds the reward heatmap for learning-based routing.

#### User Management
- **`services/users.py`** — User creation with bcrypt password hashing, SQLite storage, email uniqueness validation.
- **`api/routes_users.py`** — `POST /api/users` endpoint for user registration.

#### CI/CD
- **`.github/workflows/integration.yml`** — GitHub Actions workflow: pytest on Python 3.11 + 3.12, coverage >= 80%.

#### Documentation
- **`docs/architecture-v5.md`** — Full v5 architecture reference (v3→v4→v5 evolution, Pi agent harness, multi-project dashboard).
- **`docs/mnemos-implementation.md`** — Mnemos implementation addendum (signal access, hook integration, fatigue dimensions).
- **`docs/polyphony-spec.md`** — Polyphony multi-agent orchestration specification (6-layer architecture, task state machine, routing rules).

### Changed
- **GPT tier removed** from `DEFAULT_TIERS` — OpenAI deprecated the free research tier. Codex promoted to primary mid-range model (`routing_rules_defaults.py`, `model_router.py`).
- **Engram seed** now fills only missing memory types instead of requiring an empty store. Existing engrams preserved (`engram/seed.py`).

### Fixed
- **Routing rewards not recorded** — routed chat responses weren't feeding the reward heatmap. Added `record_outcome()` call after stream completion (`routes_chat.py`).
- **Engram seed skipped non-empty stores** — stores with some memory types but missing others weren't seeded. Now checks per-type and fills gaps (`engram/seed.py`).

### Tests
- `tests/test_routing_config.py` — 3 tests for GPT removal, codex promotion
- `tests/test_chat_routed.py` — 3 tests for reward recording
- `tests/test_engram.py` — +4 tests for seed edge cases (fill missing types, skip when all present)
- `tests/test_routes_users.py` — 7 tests for user registration
- **Total: 843 tests passing** (825 + 18 new)

---

## [5.8.0] - 2026-05-12

### Fixed

#### UX Fix Pass (12 issues from manual CLI testing)
- **Prompt character** — Changed from `maggy:` to `>` for cleaner input (`cli_chat.py:76`)
- **Ctrl+C during streaming** — Now cancels current response instead of exiting REPL. Added `except KeyboardInterrupt` in `_stream_chunks` (`cli_chat.py:161`)
- **`/health` 404** — Client was calling `/api/health/memory` (non-existent). Fixed to call `/api/engram/diagnostics` (`cli_client.py:260`)
- **`/route`, `/models`, `/budget`, `/stats`, `/health`, `/config` crash on server down** — Added `_call(fn, default)` safe wrapper that catches `Exception` and `SystemExit` from unreachable server. All display commands return fallback data instead of crashing (`cli_repl_cmds.py:18`)
- **Models shows "0 tracked" / "No data yet"** — When heatmap is empty, now shows the 5 known model tiers (local, kimi, gpt, claude, codex) with 0 samples (`cli_repl_cmds.py:129`)
- **`/use` accepts invalid model names** — Now validates against `_KNOWN_MODELS`, prints warning for unknown names while still setting the restriction (`cli_repl_cmds.py:147`)
- **Dir shows "?"** — Welcome banner now falls back to `os.getcwd()` when session `working_dir` is empty (`cli_welcome.py:36`)

### Added

#### Budget Subscription Awareness
- **`plan` field** on `BudgetConfig` — Users set `budget.plan: subscription` in `~/.maggy/config.yaml` (`config.py:150`)
- **`BudgetManager.budget_status()`** includes `plan` in response (`budget.py:163`)
- **`/budget`** shows "Subscription" instead of "$0.00 / $10.00" when plan is subscription (`cli_repl_cmds.py:87`)
- **Welcome banner** shows "Subscription" for subscription plans (`cli_welcome.py:54`)

#### Welcome Banner Improvements
- **Models count** — Shows "5 available" (known model count) instead of "0 tracked" when no heatmap data (`cli_welcome.py:62`)

### Changed
- **`_HELP` compressed** — 2-column layout saves 6 lines, fits all new features within 200-line limit (`cli_repl_cmds.py:191`)

### Tests
- `test_repl_cmds.py` — +5 tests: models_empty_shows_known, use_warns_unknown_model, budget_subscription_plan, health_graceful_failure, stats_server_down
- `test_cli_welcome.py` — +3 tests: dir_shows_cwd_fallback, models_shows_available_count, budget_subscription_welcome
- `test_cli_chat.py` — +1 test: chat_prompt_uses_angle_bracket
- **Total: 825 tests passing** (816 + 9 new)

---

## [5.7.0] - 2026-05-12

### Added

#### `/monitor` Command — Background Tracker Polling
- **`maggy/services/monitor.py`** — MonitorService with SQLite-backed polling for GitHub PRs and Monday.com items. `MonitorConfig` and `MonitorEvent` dataclasses, `add/remove/list_active/is_new/mark_seen/status/poll` methods
- **`maggy/providers/monday.py`** — Monday.com provider implementing `IssueTrackerProvider` protocol via GraphQL API. Maps board items to Task dataclass
- **`maggy/api/routes_monitor.py`** — REST endpoints: `GET /api/monitor/status`, `POST /api/monitor/start`, `POST /api/monitor/stop`
- **`/monitor` handler** in REPL — shows active monitor count (`cli_chat.py:94`)

#### `/health` Command — Memory Health Dashboard
- **`cmd_health()`** — Shows Engram health score (color-coded) and Mnemos fatigue state in Rich Panel (`cli_repl_cmds.py:180`)
- **`health_dashboard()`** and **`engram_diagnostics()`** client methods (`cli_client.py:259`)

#### Enhanced Welcome Banner
- **`cli_welcome.py`** — New file with Rich Panel welcome banner showing project info, budget, models, status, and memory health score

#### Search Routing to Local Model
- **"search" type** added to `TYPE_KEYWORDS` in `chat_router.py` — 11 keywords (find, search, grep, where, locate, which, look, scan, show, list, read) route to local/Qwen model for free

#### Account Switching Guidance
- **`maggy/services/account_guide.py`** — Detects CLI auth profiles from `~/.claude/`, `~/.codex/`. `suggest_switch()` returns CLI instructions, `render_switch_guide()` prints Rich-formatted guidance
- **Quota error detection** — `_QUOTA_MARKERS` in `cli_chat.py` triggers account switch guidance on rate limit errors

### Tests
- `test_monitor.py` — 8 tests for MonitorService
- `test_monday_provider.py` — 6 tests for MondayProvider
- `test_account_guide.py` — 5 tests for account switching
- `test_chat_router.py` — +3 tests for search type detection
- `test_repl_cmds.py` — +3 tests for health command
- `test_cli_welcome.py` — +2 tests for health and session history
- `test_cli_chat.py` — +1 test for quota error guidance
- **Total: 816 tests passing** (788 + 28 new)

---

## [5.1.0] - 2026-05-11

### Added

#### REPL Slash Commands — Stats, Routing, Model Control
- **`maggy/cli_repl_cmds.py`** — 9 command handlers for the interactive REPL:
  - `/stats` — Budget + model performance summary (spend, status, reward heatmap)
  - `/budget` — Detailed per-provider breakdown with visual progress bar
  - `/route` — Routing rules, task type overrides, model strengths/success rates
  - `/models` — Full reward heatmap grid by model × task type × blast tier
  - `/use claude,codex` — Restrict routing to specific models for this session
  - `/use all` — Remove model restriction
  - `/config` — Configuration summary (codebases, routing mode, budget limit)
  - `/claude-md` — Render project's CLAUDE.md in terminal
  - `/help` — List all available commands
- **`SessionState`** dataclass — Mutable session-level state (session_id, working_dir, allowed_models)
- **`dispatch()`** router — Parses slash commands, routes to handlers, returns True if handled
- **`GET /api/routing/rules`** endpoint — Exposes routing mode, task type overrides, model performance
- **`allowed_models`** field on `RoutedMessageRequest` — Server-side model restriction: if routed model not in allowed list, picks first allowed model with updated reason

#### Qwen3-Coder Benchmarks
- **75.7 tok/s average** — 3.4× faster than Qwen2.5-Coder (22.1 tok/s), 2× faster than Claude API (37.4 tok/s)
- MoE architecture (3.3B active / 30B total params) on M4 Max 128GB
- Quality: 10/10 BST correctness, 9/10 async rate limiter (token bucket + asyncio.Lock)
- Cold start: ~13s model load; hot runs: <100ms start

#### mWP Mindset — Full Framework
- **`skills/base/SKILL.md`** — Added complete mWP section with 11-Star Framework (Brian Chesky), mWP planning checklist (obvious → magical → multiplier)
- **`routing_rules.py`** — Expanded mWP convention injected into all CLI prompts (codex, kimi, qwen3, claude) with 3-question framework and 11-star reference

### Changed
- **`cli_chat.py`** — Integrated `SessionState` and `dispatch()` from `cli_repl_cmds`; passes `allowed_models` to `chat_send_routed()`; mode hint now shows `/help for commands`
- **`cli_client.py`** — Added `budget_by_provider()`, `routing_rules()` methods; updated `chat_send_routed()` signature to accept `allowed_models`
- **`benchmark-results.md`** — Qwen3-Coder results filled in (was TBD), quality assessment section added

### Tests
- `tests/test_repl_cmds.py` — 10 tests (dispatch routing, stats, budget, route, models, use, claude-md, help)
- `tests/test_cli_chat.py` — Updated 2 assertions for `allowed_models=None` parameter
- **Total: 653 tests passing** (643 maggy + 10 session detect)

---

## [5.0.0] - 2026-05-10

### Added

#### Interactive Chat — Session Takeover
- **`maggy/services/chat.py`** — ChatManager for interactive Claude sessions with SSE streaming
  - Auto-connects to all active CLI sessions (Claude, Codex, Kimi) via ActivityService process scanning
  - Session continuity with `--resume <session-id>` for multi-turn conversations
  - `CLAUDECODE` env var stripping to allow nested Claude subprocess spawning
  - `--verbose` flag for `--output-format stream-json` compatibility
  - Deduplication via dict keyed by project name
- **`maggy/services/chat_context.py`** — Context builder for session enrichment
  - Path-based history matching (not just exact project name) via `_path_candidates()`
  - `_SKIP_DIRS` set prevents matching common system directories (Users, Documents, Library)
  - Recent prompt injection from activity data per project
  - Claude `session_id` resolution from `~/.claude/history.jsonl` for true `--resume`
- **`maggy/api/routes_chat.py`** — Chat API (5 endpoints)
  - `POST /api/chat/auto-connect` — detect all active sessions, enrich with history context
  - `POST /api/chat/sessions` — create session
  - `GET /api/chat/sessions` — list sessions
  - `GET /api/chat/sessions/{id}` — get session + messages
  - `POST /api/chat/sessions/{id}/send` — send message, stream response via SSE
  - `DELETE /api/chat/sessions/{id}` — delete session
- **Chat UI** in `app.js` — full web-based chat interface
  - Auto-connects on tab load, shows all active project sessions in sidebar
  - Message thread with user/Claude bubbles
  - SSE EventSource for real-time streaming
  - Session history context display
  - New session creation from active + configured projects

#### Auto-Bootstrap — No Empty Tabs
- **`_bootstrap()` in `main.py`** — seeds all services on startup
  - `history.analyze()` — parses CLI sessions immediately (260+ sessions, 11,994 prompts)
  - `introspector.analyze()` — collects signals, emits events
  - `_seed_cikg()` — scans configured codebases, creates nodes for repos + detected languages

#### UI Navigation Cleanup
- **Grouped navigation** — 9 flat tabs reorganized into 3 logical groups:
  - **Work** (Chat, Tasks, Watching) — things you do
  - **Intel** (Competitors, Insights) — things you learn
  - **System** (gear dropdown: Budget, Models, Forge, Settings) — things you configure
- **Tab renames** — Inbox→Tasks, Followed→Watching, Process→Insights
- **Chat is default tab** — loads on startup, auto-connects immediately
- **Gear dropdown** — system tabs collapsed into icon menu, reduces nav clutter
- **Section labels** — tiny uppercase "WORK" / "INTEL" separators

#### Process Intelligence Tab Enhancement
- Parallel fetch of activity, history, improve, events, CIKG data
- Health signals display (routing, memory, reliability, cost percentages)
- Live activity section showing active sessions + recent prompts
- Session patterns from history analysis
- Button spinner feedback + success toast on Analyze History / Self-Improve

#### Infrastructure
- **No-cache static middleware** — `_NoCacheStatic` adds `Cache-Control: no-store` to `/static`
- **Cache-busting** — `?v=3` on script tag
- **`showToast()`** — green success notification for async operations

### Security
- **Chat path validation** — `project_path` now validated against configured codebase roots (blocks arbitrary filesystem access via `--dangerously-skip-permissions`)
- **Chat streaming lock** — per-session `asyncio.Lock` rejects concurrent `/send` requests, preventing duplicate subprocess spawning and workspace corruption

### Fixed
- Engram `expire_engrams` referencing `self` outside class context
- `auto_connect` returning duplicate sessions for same project
- `CLAUDECODE` env var blocking nested Claude subprocess spawning
- `--verbose` flag required when using `--output-format stream-json` with `-p`
- History matching missing projects stored under parent dir name (e.g. "AI-Playground" vs "claude-skills-package")
- Process tab buttons doing nothing due to browser-cached old JS
- 500-row limit in history store masking projects — switched to aggregated report data

### Changed
- Default tab: `inbox` → `chat`
- Org name in config: `"Your Org"` → read from `~/.maggy/config.yaml`
- README fully rewritten to reflect current feature set (was still describing MVP)

### Tests
- `tests/test_chat.py` — 17 tests (ChatManager + AutoConnect)
- `tests/test_chat_context.py` — 18 tests (path candidates, history matching, prompts, session ID)
- Total: **466 tests passing**

---

## [4.0.0] - 2026-05-05

### Added

#### Polyphony — Multi-Agent Orchestration (Core)
- **`scripts/polyphony/`** — Full multi-agent orchestration package with container-isolated workspaces. Each agent session runs in its own Docker container with independent git branches.
- **Domain models** (`models.py`) — Task, Identity, AgentProfile, RunSpec, Result dataclasses
- **Task state machine** (`state_machine.py`) — DISCOVERED -> CLAIMED -> ROUTED -> PROVISIONED -> RUNNING -> VERIFYING -> LANDED with FAILED/BLOCKED paths
- **SQLite store** (`store.py`) — Persistent CRUD for tasks, run_specs, results with state audit log
- **YAML config** (`config.py`) — Configuration loading from `~/.polyphony/` with defaults merging
- **5-dimension complexity scoring** (`scoring.py`) — Cyclomatic depth, fan-out, security boundary, concurrency, domain invariants (0-10 scale)
- **Pure function router** (`router.py`) — Task x Policy -> RunSpec, first-match rules with fallback chains
- **Identity broker** (`identity.py`) — Named credential bundles with volume mounts and env overlays
- **Workspace manager** (`workspace.py`) — Per-task git clone lifecycle with `--reference`/`--dissociate` mirror support
- **Docker runtime** (`runtime.py`) — Container create/start/stop/wait/logs/rm lifecycle
- **Event parser** (`events.py`) — NDJSON/stream-json parsing from container stdout
- **Orchestrator** (`orchestrator.py`) — Supervisor loop: discover -> claim -> route -> provision -> run -> verify -> land
- **Agent adapters** (`adapters/`) — Claude (`-p --output-format stream-json`), Codex (`exec --full-auto`), Kimi (`--print -y`)
- **Work sources** (`sources/`) — GitHub Issues via `gh api`, local SQLite task queue
- **CLI** (`__main__.py`) — `polyphony {init|spawn|status|cleanup}` commands
- **Skill** (`skills/polyphony/SKILL.md`) — Full documentation for the orchestration system
- **Commands** — `/polyphony-init`, `/polyphony-spawn`, `/polyphony-status`
- **Templates** — `Dockerfile.polyphony`, `polyphony-config.yaml`, `polyphony-identities.yaml`, `polyphony-agents.yaml`, `polyphony-routing.yaml`
- **Spec** (`docs/polyphony-spec.md`) — Full specification reference (12 sections)
- **173 tests** across 13 test files with full TDD coverage

---

## [3.6.1] - 2026-05-04

### Changed
- **Complexity-based delegation replaces file-count heuristic** (`skills/cross-agent-delegation/SKILL.md`) — Kimi delegation now scored on 5 dimensions (cyclomatic depth, fan-out, security boundary, concurrency, domain invariants) × 0-2 each, sourced from iCPG signals + Claude reasoning. Routing: 0-3 → Kimi solo, 4-6 → Kimi + Codex auto-review, 7-10 → Claude direct. Adds trivial-case shortcut (<2 files + no risk keywords → auto-Kimi without scoring) and single-dimension override (7+ in any one dim keeps Claude). PR #16.

---

## [3.6.0] - 2026-05-03

### Added

#### Cross-Tool Compatibility (Claude + Kimi + Codex)
- **`scripts/detect-agents.sh`** — Detects installed AI CLI tools (Claude Code, Kimi CLI, Codex CLI)
- **`scripts/install-skills.sh`** — Reusable skill copier for any target directory
- **`templates/AGENTS.md`** — Codex project instructions template (mirrors CLAUDE.md with `.agents/skills/` paths)
- **`templates/config.toml`** — Hooks in TOML format for Kimi/Codex compatibility
- **`scripts/convert-hooks-to-toml.sh`** — JSON to TOML hook converter (requires jq)
- **`commands/sync-agents.md`** — `/sync-agents` command for cross-tool config sync
- **`install.sh`** auto-detects and installs skills to `~/.kimi/skills/` and `~/.codex/skills/`
- **`/initialize-project`** question 9: "Which AI CLI tools do you use?" with auto-detection
- Cross-tool directories (`.kimi/`, `.codex/`, `.agents/`) added to `.gitignore` template

#### Cross-Agent Intelligence
- **`templates/codex-auto-review.sh`** — Stop hook that auto-runs Codex review on changed files
  - Checks for Critical/High severity issues only
  - Exit 0 = pass, Exit 2 = feed findings back to Claude for fixing
  - Truncates diff to 8000 chars to prevent Codex token overflow
  - Gracefully skips if Codex CLI not installed
- **`skills/cross-agent-delegation/SKILL.md`** — Delegation skill with:
  - Tool detection (checks `command -v` for each CLI)
  - iCPG blast radius rules for Kimi delegation (<=3 files suggest Kimi, 4-8 offer option, 9+ stay Claude)
  - iCPG mandatory pre-task queries for all agents (prior, constraints, risk)
  - Mnemos mandatory memory lifecycle for all agents (goals, checkpoints, fatigue)
  - 10-step cross-agent workflow summary
- **Codex auto-review Stop hook** added to `settings.json` (after TDD, before iCPG record, 120s timeout)
- **Codex auto-review TOML hook** added to `config.toml` for Kimi/Codex compatibility
- **Cross-Agent Workflow** section added to both `CLAUDE.md` and `AGENTS.md` templates
- **`cross-agent-delegation/`** added to always-copy skill list in `/initialize-project`

#### Tests
- **`tests/test_cross_tool.py`** — 12 tests for cross-tool compatibility (detect-agents, install-skills, templates, sync-agents)
- **`tests/test_cross_agent.py`** — 22 tests for cross-agent intelligence (codex-auto-review, delegation skill, settings.json hook ordering, config.toml, template refs)

### Changed
- `install.sh` bumped to v3.6.0
- `install.sh` now makes `codex-auto-review.sh` executable during install
- `tests/validate-structure.sh` includes cross-tool template validation
- Total skills increased from 60 to **61 skills**
- Total tests: 62 pytest + 238 validation checks

---

## [3.5.2] - 2026-04-22

### Fixed
- **Hook error behavior revised** — the 3.5.1 fix silently no-op'd missing scripts, which hid real installation problems. Hook commands now:
  - **Fail loud on real errors** — if the script exists and crashes, its stderr + non-zero exit propagate to Claude Code so you can debug
  - **Print one actionable line on missing installs** — `[claude-bootstrap] hook script 'X' not installed — run <claude-bootstrap>/install.sh …` and exit 0 (no blocking error, but you see exactly what to do)
  - **Use `exec` to run the resolved script** — exit code + stderr pass through unchanged
- **Hook scripts stop swallowing stderr** — removed 19 instances of `2>/dev/null` across `mnemos-*.sh`, `icpg-*.sh`, and `tdd-loop-check.sh`. Python tracebacks and Python stderr now surface to Claude Code's hook diagnostics. Command substitution (`$(...)`) only captures stdout, so this doesn't affect any value parsing.

## [3.5.1] - 2026-04-21

### Fixed
- **PreToolUse hook "Bash hook error" on any tool call.** `templates/settings.json` declared hook commands as relative paths (`scripts/mnemos-*.sh`) that don't exist in most projects — the scripts live in `templates/` and nothing copies them to `<project>/scripts/`. Every tool call triggered a hook-not-found error shown as `PreToolUse:Bash hook error` in the session (non-blocking but noisy).
- Hook commands now try `.claude/scripts/<name>.sh` first (project-local override), fall back to `$HOME/.claude/templates/<name>.sh` (always installed by `install.sh`), and no-op cleanly when neither exists. Applied to all 8 hook script references across `PreCompact`, `PreToolUse`, `PostToolUse`, `Stop`, and `SessionStart`.

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
