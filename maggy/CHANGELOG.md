# Changelog — Maggy

All notable changes to Maggy will be documented in this file.

---

## [6.49.0] - 2026-06-11

### Zero-config onboarding — it just works out of the box

Council/chief review found the auto-setup machinery existed but the default
path ignored it: the shipped config had `your-org` placeholders, so first boot
landed on a live dashboard with GitHub errors and an empty Execute panel, and
install.sh told users to hand-edit YAML.

#### Changed
- **First boot auto-configures.** `config.load_or_bootstrap()` (used by
  `main.create_app`) detects a missing or placeholder config and runs
  `auto_configure()` — discovers the user's real local repos, sets the GitHub
  org, writes a clean config (keyless local mode), and opens the dashboard
  pointed at their actual work. No `your-org` fakes, no hand-editing.
- `config.is_placeholder()` detects the unmodified example template.
- **install.sh** no longer copies the placeholder template or prints "edit
  config.yaml" steps; it states Maggy auto-configures and lists keys as optional.
- **GETTING_STARTED**: 2-step install, no required API keys (local mode works
  without them).
- **Auto-opens the dashboard** in the browser on `maggy serve` (loopback only;
  opt out with `MAGGY_NO_BROWSER=1`).

#### Tests
- 7 tests (placeholder detection, bootstrap-on-missing/placeholder, keep-real-
  config, discovery-error fallback). Verified live: a fresh boot discovered 30
  local repos with zero config.

## [6.48.0] - 2026-06-10

### Council T4 — Reconcile memory + coordination

#### Fixed (concurrency)
- The concurrent multi-agent SQLite stores set WAL but no `busy_timeout`, so a
  second writer failed immediately with "database is locked". Added
  `PRAGMA busy_timeout=5000` to `orchestrator/store.py` (Polyphony task state),
  `council/audit_log.py`, `mnemos/db.py`, and `services/approval.py` — concurrent
  writers now wait up to 5s instead of erroring/corrupting.

#### Added (memory precedence)
- `memory_precedence.py` — the explicit reconciliation rule the chief asked for:
  **cikg (intent) > mnemos (goals) > history (observational)**. `history` is
  advisory and never overrides cikg/mnemos. `resolve()`/`winner()` give the
  executor gate a single answer when memory systems disagree.
- 16 tests (busy_timeout set, concurrent-writers-wait, precedence resolution).

## [6.47.0] - 2026-06-10

### Architecture Hardening (council T1 + T2)

Council of experts (chief Claude Fable 5 + DeepSeek Pro, Gemini, Grok) reviewed
the architecture; these are the agreed fixes.

#### T1 — Gate the self-tuning router
- `learn_override` now proposes in **shadow** (never applied). `apply_override`
  only honors active rules. `promote_override` gates shadow->active on
  outcome-validity (>= MIN_SAMPLES outcomes at >= MIN_SUCCESS_RATE). Plus
  `revert_override`, `pending_overrides`, and a diffable `routing-rules-audit.jsonl`.

#### T2 — Unify isolation
- **(A)** Pinned, golden-tested CLI manifests (`adapters/cli_manifests.py`) replace
  `--help` auto-discovery for known delegation CLIs; pi.py builds their commands
  from the manifest first.
- **(B)** Autonomous pipeline now runs file/git/shell tool ops **inside a Docker
  container** (`pipeline/container_runner.py`, workspace mounted at /workspace),
  not on the host. `build_tool_executor(isolation=auto|container|process)` makes
  container the default when Docker is available; the host path-sandbox is the
  deprecated, fail-loud fallback. ~28 new tests across the two parts.

## [6.46.0] - 2026-06-09

### Council of Experts: Claude Fable 5 as Chief

#### Added
- **`chief` role on the council** — `CouncilConfig.chief` (default `claude-fable-5`,
  Anthropic's most capable widely-released model, GA today). The chief leads every
  panel (plan/review/architecture) as first reviewer and is exposed via
  `get_chief()` for deciding-synthesis logic.
- `claude-fable-5` added to the council model registry, `adapters/pi.py`
  (model_id `claude-fable-5`, ~/bin/claude-fable-5 wrapper, 1M context), and the
  model-health allowlist.
- Tests for chief default, lead-reviewer ordering, resolution, and round-trip.

---

## [6.45.0] - 2026-06-08

### Reddit Agent: Voice Rules + Reply Monitoring

Build-in-public's Reddit channel is now a full agent — it posts in a
human, Reddit-safe voice and replies to comments on its own posts.

#### Added
- **Voice rules** (`voice.py`, user-definable under `config.voice`, per-channel
  override) applied before every Reddit post/reply:
  - `no_em_dash` — strips em/en dashes
  - `strip_markdown` — flattens Markdown to plain text (Reddit fancy-editor
    renders stray Markdown literally)
  - `typos` — injects occasional realistic typos (seedable, rate-controlled) so
    posts don't read like a bot
- **Reply-monitoring agent** — a heartbeat (`reddit_reply_monitor`, every 30 min)
  tracks Maggy's submitted posts (`~/.maggy/build-in-public/reddit-posts.json`),
  finds new non-self comments, drafts a short voice-applied reply, and posts it.
  Never replies to itself or the same comment twice; rate-limited per cycle.
- `social_api`: `reddit_post` now returns the post fullname (for tracking) and
  posts cleanly via `api_type=json`; `reddit_post_comments()` fetches comments.
- Default publish target set to **r/ClaudeCode**.
- 24 tests (voice rules, post-id tracking, self-skip + reply-once monitoring).

---

## [6.44.0] - 2026-06-07

### Build-in-Public: Reddit Publishing Channel

#### Added
- **Reddit as a third publish channel** (alongside LinkedIn + X). The narrative engine generates a Reddit-native self-post; `_schedule_posts` routes Reddit directly (not a Buffer service) while the rest go via Buffer (`_schedule_buffer_posts`). `ScheduledPost` gained a `title`.
- **Autonomous subreddit** — `_resolve_reddit_subreddit()` picks the target automatically (defaults to r/buildinpublic, or `topics.yaml` `reddit_publish`); `config.channels.reddit.subreddit` is an optional override.
- **Credential fallback from ideaminer** — `reddit_cred()` reads Reddit creds from the environment, then a sibling ideaminer checkout (`~/Documents/AI-Playground/ideaminer/.env`), so local Maggy reuses ideaminer's Reddit app with no extra setup.
- **Write-auth flexibility** — `_get_reddit_access_token` now supports both a web-app refresh token and a script-app password grant (`REDDIT_USERNAME`/`REDDIT_PASSWORD`); `reddit_post`/`reddit_comment` gate on available write creds. Posting uses the existing `reddit_post`.
- 12 tests (cred resolution, grant selection, post success/no-creds, title plumbing, autonomous + override subreddit, routing).

#### Notes
- `reddit.write` permission added. Reading/monitoring works with ideaminer's creds out of the box; **posting** still needs a write credential (a refresh token or username/password) — ideaminer ships read-only creds only.

---

## [6.43.0] - 2026-06-04

### Dashboard iCPG Auto-Build, Orchestrator Isolation, Followed-Model Routing

#### Added
- **iCPG graph auto-build** — "Visualize Graph" on an empty graph now offers to bootstrap the iCPG from git history (`POST /api/icpg/{key}/build`), runs `icpg bootstrap` off the event loop, with a per-project in-flight lock to prevent concurrent builds corrupting `reason.db`
- **Orchestrator isolated workspaces** — each subtask gets a per-session git worktree (via `orchestrator.isolation`) mounted into its container, cleaned up after the run; fixes the empty `-v :/workspace` mount
- **Isolation modes honored** — `orchestrator.isolation` (`auto`/`worktree`/`local`) resolves to a strategy (`auto` probes docker > worktree > lock-only); non-container levels run locally instead of requiring Docker
- **`minimax` model** in `adapters/pi.py` (dispatches `~/bin/minimax`) + `process/model_preference.py` so `chat_router.decide()` follows the user's shared primary model for real work
- Tests for build endpoint, isolation/provisioning, model preference

#### Fixed
- **Orchestrator image mismatch** — `route_subtask` hardcoded `polyphony:latest`; now config-driven (`orchestrator.image`, default `polyphony-worker:latest`, the image that's actually built)
- **Security (HIGH):** local (non-container) agent runs no longer pass `--dangerously-skip-permissions`; `_run_local` refuses unless `orchestrator.local_sandbox` (firejail/bwrap) is configured — fail-safe by default
- Two stale `pi_adapter` tests with hardcoded model counts

---

## [6.42.0] - 2026-05-29

### Autonomous Agent Pipeline — Tool Execution, Steering, Contracts, Approvals

Full 5-phase autonomous agent system: Pi models can now execute typed tools (file read/write, grep, git ops, test run) inside a sandbox, with advise-only steering detection, execution contracts, selective skill loading, and an inbox-based approval flow for write operations.

#### Added
- `maggy/pipeline/tool_schema.py` — 9 typed tools (6 read, 3 write) with allowlist-only enforcement, no shell passthrough
- `maggy/pipeline/tool_sandbox.py` — path validation, symlink escape prevention, secret file blocking (.env, credentials.json, etc.)
- `maggy/pipeline/tool_parser.py` — extracts `tool_call` fenced JSON blocks from model text output
- `maggy/pipeline/tool_handlers.py` — concrete handlers: file_read, grep, git_status/diff/log, test_run, file_write, file_edit, git_commit
- `maggy/pipeline/tool_executor.py` — sandboxed execution with backup/rollback, max 10 calls per round, approval store notifications
- `maggy/pipeline/steering.py` — detects advise-only responses ("here's what you should do") and injects "act now" re-prompt
- `maggy/pipeline/contracts.py` — `ExecutionContract` enforces `strict-agentic` mode: rejects planning-only responses
- `maggy/skills/selective.py` — on-demand skill loading: index (names only) in prompt, full content loaded by keyword match (max 3)
- `maggy/services/approval.py` — SQLite-backed approval store with pending/resolve/history, thread-safe (WAL + check_same_thread=False)
- `maggy/api/routes_approval.py` — REST endpoints: GET pending, GET history, POST approve, POST reject
- `tests/test_e2e_autonomous.py` — 24 end-to-end integration tests covering full pipeline
- `tests/test_tool_schema.py` — 15 unit tests
- `tests/test_tool_sandbox.py` — 10 unit tests
- `tests/test_tool_parser.py` — 7 unit tests
- `tests/test_tool_handlers.py` — 11 unit tests
- `tests/test_tool_executor.py` — 7 unit tests
- `tests/test_steering.py` — 10 unit tests
- `tests/test_selective_skills.py` — 9 unit tests
- `tests/test_approval.py` — 10 unit tests
- `tests/test_execution_contracts.py` — 8 unit tests
- `tests/test_routes_approval.py` — 9 unit tests
- `tests/test_pi_tool_wiring.py` — 6 unit tests
- `tests/test_agent_prompt.py` — 8 unit tests
- `scripts/test-autonomous.sh` — consolidated test runner for all autonomous agent tests (134 tests, <0.5s)

#### Changed
- `maggy/pipeline/backend_pi.py` — wired tool executor + steering + contracts into Pi execution loop (parse → sandbox → execute → steer → validate)
- `maggy/prompt/assembly.py` — uses `build_skill_index()` for index-only skill references in prompts
- `maggy/main.py` — registers approval_router, initializes ApprovalStore
- `maggy/static/app.js` — Inbox UI: pending approvals with Approve/Reject buttons, history with status badges
- `maggy/static/index.html` — pane-inbox overflow styling

---

## [6.41.0] - 2026-05-28

### Updated Model Tiers + Local System Validator

Research-backed tier update (12 tiers) with Gemini 3.5 Flash and Claude Opus 4.7. Hardware detection suggests which local models fit the user's system.

#### Added
- `maggy/process/model_tiers.py` — extracted tier definitions: 12 tiers from local (Qwen3) to Claude Opus 4.7, adding Gemini 3.5 Flash (tier 8, agentic coding, 278 t/s)
- `maggy/process/model_budget.py` — extracted daily budget tracking + spend estimation from routing log
- `maggy/services/system_validator.py` — `detect_hardware()` (RAM, CPU, GPU/Metal/CUDA, disk), `suggest_local_models()` with fit classification (comfortable/tight/too_large), 12 local model profiles (Qwen3 0.6B–32B, DeepSeek R1 distilled, Codestral, Llama 4 Scout/Maverick)
- `tests/test_system_validator.py` — 12 tests: hardware detection, model requirements, suggestion filtering by RAM/disk/GPU
- `tests/test_routes_system_validator.py` — 2 tests: hardware + suggest-models API routes
- API routes: `GET /api/system/hardware`, `GET /api/system/suggest-models`

#### Changed
- `maggy/process/model_router.py` — split into model_tiers.py (data) + model_budget.py (budget tracking); imports from both
- `maggy/static/app.js` — Settings: "Suggested Local Models" card with Scan Hardware button, hardware summary, model list with fit indicators
- `maggy/static/index.html` — cache bust v18

---

## [6.40.0] - 2026-05-28

### User Model Registry — Custom AI Models + Council Persona Fallback

Users can add custom AI models (CLI or API) via Settings, with validation on add. Council of Experts falls back to persona-based prompts when only one model is available.

#### Added
- `maggy/services/model_registry.py` — add, remove, validate, list custom models; `build_council_reviewers()` with single-model persona fallback (security, architecture, pragmatist); `build_routing_tiers()` merges custom models into routing tiers
- `tests/test_model_registry.py` — 17 tests: add CLI/API, duplicate rejection, validation, persistence, remove, list with custom flag, council persona fallback
- `tests/test_routes_models_crud.py` — 9 tests: POST/DELETE/validate API routes with mocked registry
- `tests/test_registry_wiring.py` — 7 tests: custom models in routing tiers, persona injection into deliberation, fallback compatibility
- API routes: `POST /api/models`, `DELETE /api/models/{id}`, `POST /api/models/check/validate`

#### Changed
- `maggy/api/routes_models.py` — `GET /api/models` now uses model_registry with `custom` flag; added CRUD + validate endpoints
- `maggy/council/deliberation.py` — added `run_with_personas()` that injects persona system prompts into the query function per reviewer
- `maggy/routing.py` — `RoutingService.route()` now loads custom models via `build_routing_tiers()`; `_find_tier()` searches custom models too
- `maggy/static/app.js` — Settings pane: "Custom Models" card with add form (validates CLI/API before adding), list with remove buttons
- `maggy/static/index.html` — cache bust v17

---

## [6.39.0] - 2026-05-28

### Layered System Prompt Architecture (ADR-001)

Council-approved 3-layer prompt system replacing the static system prompt. Maggy now assembles context-aware prompts dynamically based on where it's running — existing project, git workspace, or empty directory.

#### Added
- `maggy/prompt/modes.py` — mode detection (project/workspace/bootstrap) with confidence scoring and marker tracking
- `maggy/prompt/sections.py` — composable PromptSection dataclass + stable layer builders (identity, capabilities, rules, mode semantics, safety)
- `maggy/prompt/context_layer.py` — context layer: file tree, git state, tech stack detection, CLAUDE.md loading, mode display
- `maggy/prompt/assembly.py` — PromptAssemblyService combining all layers with fallback to legacy prompt on error
- `maggy/prompt/skill_index.py` — Hermes-style compact skill index (one-line per skill in prompt, not full content dump)
- `maggy/services/chat_grounding.py` — balanced grounding instructions covering code AND non-code tasks (research, planning, brainstorming)
- `docs/ADRs/001-layered-system-prompt.md` — full council verdict with 8 design decisions
- `docs/ADRs/002-agy-prototype-evaluation.md` — prototype assessment and adoption strategy
- 40 new tests across 6 test files (modes, sections, context, assembly, skill_index, chat_grounding)

#### Changed
- `maggy/services/chat_stream.py` — `_build_system_prompt()` now uses PromptAssemblyService instead of static string; removed `_load_skills()` full-content dump (skills now indexed via assembly)

#### Architecture
| Layer | Lifetime | Content |
|-------|----------|---------|
| Stable | Per session, cacheable | Identity, capabilities, rules, safety |
| Context | Session + invalidation | Mode, file tree, git state, tech stack, CLAUDE.md, skill index |
| Volatile | Per turn (future) | Intent flags, conversation state |

---

## [6.38.1] - 2026-05-26

### Model Health + Dashboard Regression Guards

#### Added
- `maggy/services/model_health.py` — parallel health checks via ThreadPoolExecutor, command allowlist/blocklist, timeout + latency tracking
- `tests/test_model_health.py` — 7 tests: success, output capture, missing binary, timeout, parallel, null cmd, allowlist security
- `tests/test_sidebar_structure.py` — 8 tests: tab/pane consistency, stale tab detection, plugin pane isolation
- `tests/test_project_scoping.py` — 9 tests: project key passed to inbox, team, cortex, memory, plugins, activity endpoints
- `tests/test_routes_models.py` — 5 tests: routes_models.py exists, exposes list/health/council endpoints, registered in main

---

## [6.38.0] - 2026-05-25

### Council of Experts — Multi-Model Deliberation + Auto-Execution Gating

Multi-round deliberation engine where 3+ AI models independently evaluate, cross-examine, and reach consensus before changes auto-execute. Blast radius analysis via file/function/subsystem scoring gates execution through a decision matrix: low-blast + objective = auto-execute, critical/subjective = always human.

#### Added
- `maggy/council/models.py` — ContextPackage, ReviewerVote, DeliberationResult, BlastAnalysis, ValidationClassification, ExecutionDecision
- `maggy/council/deliberation.py` — 3-round engine: independent eval, cross-examination, final position (async, parallel reviewers)
- `maggy/council/blast_analyzer.py` — file/subsystem impact scoring, objective/subjective validation classification
- `maggy/council/executor_gate.py` — decision matrix: AUTO_EXECUTE, AUTO_WITH_ROLLBACK, AUTO_WITH_NOTIFY, HUMAN_REVIEW
- `maggy/council/audit_log.py` — SQLite WAL persistence for all deliberation decisions
- `maggy/services/council_config.py` — YAML config for reviewer panels, model registry, thresholds
- 62 tests across 6 test files (models, deliberation, blast, gate, audit, config)

#### Decision Matrix
| Severity | Validation | Action |
|----------|-----------|--------|
| Critical (auth/PII/API) | Any | ALWAYS HUMAN |
| High (10+ files) | Any | HUMAN REVIEW |
| Medium (4-10 files) | Objective + tests | AUTO + rollback |
| Medium | Subjective | HUMAN REVIEW |
| Low (1-3 files) | Objective | AUTO-EXECUTE |
| Low | Subjective | HUMAN REVIEW |

#### Fixed
- Build-in-public plugin: PluginManifest dataclass/dict compatibility (`getattr` instead of `.get()`)

---

## [6.37.0] - 2026-05-24

### Skill Protocols — Intent-Driven Execution

When a user says "push to git", Maggy detects the intent, matches it to a protocol, and executes: lint → test → stage → commit → push. AI generates the commit message via DeepSeek Flash.

#### Added
- `maggy/skills/protocol_models.py` — Protocol and ProtocolStep dataclasses
- `maggy/skills/protocol_loader.py` — loads YAML protocols from directory
- `maggy/skills/intent_matcher.py` — longest-match trigger matching
- `maggy/skills/protocol_executor.py` — step runner with conditions, variables, abort-on-failure
- `maggy/skills/protocols/git-push.yaml` — lint → test → stage → commit → push
- `maggy/skills/protocols/run-tests.yaml` — lint → typecheck → pytest
- `maggy/skills/protocols/create-pr.yaml` — test → push → gh pr create
- Frontend: protocol step rendering with status icons and expandable output
- 24 tests (models, loader, matcher, executor)

#### Architecture
- Protocols checked before LLM routing in `send_routed()`
- Steps that need AI input (`requires: message`) generate via DeepSeek Flash
- Variables: `{branch}`, `{message}`, `{title}` auto-populated
- Failed required step → protocol aborts with error; optional steps warn and continue
- Condition checks: `condition: "*.py"` skips step if no Python files exist

---

## [6.36.0] - 2026-05-24

### Unified Chat Pipeline + CLI Refresh + URL Routing

Replaced the fragmented chat pipeline (3 separate execution paths in `routes_chat.py`) with a single `ChatPipeline` orchestrator. All backends (Claude, Pi/DeepSeek, Executor) now go through one entry point with real-time streaming, fallback, logging, and post-send hooks.

#### Pipeline Architecture
- `pipeline/orchestrator.py` — `ChatPipeline.run()` streams chunks in real-time (no buffering)
- `pipeline/backend_claude.py` — wraps `ChatManager.send()` for Claude CLI
- `pipeline/backend_pi.py` — wraps `PiAdapter` for DeepSeek, Kimi, Gemini, etc.
- `pipeline/log_store.py` — SQLite WAL logging of every pipeline decision
- `pipeline/hooks.py` — budget, outcome, review, blueprint recording for all backends

#### Added
- **CLI Refresh** (`/refresh`) — imports Claude Code CLI session history into Maggy project chat
- **RefreshService** — reads `~/.claude/history.jsonl`, extracts conversation turns per project
- **Message persistence** — Pi backend messages now persisted to SQLite (user + assistant)
- **Conversation history in Pi** — PiBackend includes last 10 messages as context
- **URL-based project routing** — `http://localhost:8080/claude-skills-package` opens correct project
- **Quick actions** — contextual action buttons based on project state (CLI sessions, git, tests)
- **Pipeline Logs tab** — dashboard pane showing routing decisions, latency, cost, model usage
- **Pipeline stats API** — `GET /api/pipeline/stats` with aggregated metrics
- **Project persistence** — active project remembered across page refreshes via localStorage
- **Skill injection system** — `maggy/skills/` with registry, loader, validator, and injector
- **Project bootstrap service** — auto-detects project type and generates context
- **Sidebar navigation** — redesigned with project sections and system tabs

#### Fixed
- **Streaming buffered** — orchestrator collected all chunks before yielding; now streams real-time
- **Pi backend had no memory** — each message was independent; now includes recent conversation
- **Messages not persisted** — Pi/DeepSeek responses vanished on page reload
- **Previous response replaced** — sending new message while streaming overwrote old response
- **Empty message bubbles** — blank content rendered as empty gray boxes
- **Import returned 0** — `session_store` was local variable, not exposed on `app.state`
- **URL routing mismatch** — `/claude-skills-package` didn't match project key `maggy`; now matches by directory name
- **Message ordering** — imported messages appeared in wrong order

#### Tests
- 7 pipeline tests (orchestrator, backends, hooks, log_store, models)
- 8 refresh tests (service, import, quick-actions, project filter)
- 15 skill tests (registry, loader, validator, injector, models)

---

## [6.35.0] - 2026-05-24

### Telos — Intent-Grounded Testing Framework

Replaced fragile AI subprocess calls in e2e-testkit with **[Telos](https://github.com/alinaqi/alinaqi/blob/main/docs/Telos_RFC_v1.1.md)**, an intent-grounded testing framework backed by **[Cortex MCP](../cortex-mcp/)**. Three scoring planes, multiplicative IFS formula — a zero in any plane collapses the total score. Telos reads Cortex's `reasons`, `drift_events`, `symbols`, and `edges` tables directly via read-only SQLite.

#### IFS (Intent Fidelity Scale)

| Plane | Metric | Source |
|-------|--------|--------|
| F1 — Conformance | `passed / total` tests | pytest/vitest subprocess |
| F2 — Validation | drift severity | Cortex `drift_events` table |
| F3 — Integrity | IF-3 to IF-8 checks | Cortex `reasons` + `symbols` + `edges` |
| **IFS** | **F1 × F2 × F3** | Multiplicative — all planes matter |

#### Integrity Checks (Plane 3)

- **IF-3** Orphan symbols (no reason edges)
- **IF-4** Empty contracts (no pre/post/invariants)
- **IF-6** Stale reasons (proposed > 7 days, never fulfilled)
- **IF-7** Scope sprawl (reason scopes > 10 files)

#### Added
- `plugins/telos/` — full plugin: models, cortex_reader, 3 planes, IFS scorer, routes, manifest
- `CortexReader` — read-only SQLite from `.cortex/cortex.db` (no MCP overhead)
- `/api/telos/status?project_dir=.` — IFS breakdown endpoint
- `project.connected` hook — auto-computes IFS on project open
- Graceful degradation — no Cortex DB → F2=F3=1.0, IFS = F1 only
- 55 new tests across 7 test files (models, reader, planes, scorer, integration)

#### Fixed
- `test_cli_chat.py` stale import — `cwd_project` moved to `cli_context`, test still pointed at `cli_chat`
- `chat_stream.py` whitespace bug — `--resume` accepted whitespace-only session IDs
- Plugin hook wiring gap — manifest `hooks` were declared but never subscribed by `PluginManager`
- `project.connected` emission — added to `create_session`, `auto_connect`, `preload_sessions`

#### Architecture
- Telos reads Cortex directly (sync SQLite, `PRAGMA query_only=ON`) — same monorepo, zero MCP overhead
- Per-reason drift severity capped at 1.0 (council feedback: prevents one noisy reason from dominating F2)
- `e2e-testkit` kept during transition per council recommendation

---

## [6.34.0] - 2026-05-23

### LLM-First Input Architecture + Cortex Integration

Redesigned input routing to be strictly LLM-first, beating Hermes Agent and OpenClaw on UX. Added Cortex MCP as unified code intelligence layer.

#### Input Routing (vs Hermes Agent / OpenClaw)

| Feature | Hermes Agent | OpenClaw | Maggy |
|---------|-------------|----------|-------|
| Command dispatch | `/` prefix heuristic | `/` prefix heuristic | `!` explicit shell, `/` slash |
| NL routing | LLM tool-calling only | 15-dim heuristic scorer | LLM blast-score + Pi (7 models) |
| Ambiguous input | Silently swallowed | Routes to mid-tier | Always goes to LLM |
| Model routing | None (single model) | ClawRouter tiers | Pi adapter (7+ models, cost-ordered fallback) |
| False positives | First-word match on programs | First-word match | Zero — only `!` prefix runs shell |

#### Changed
- **`!` prefix for shell** — `!ls`, `!git status`, `!npm test`. Explicit opt-in, no heuristic word lists
- **`/` prefix for slash commands** — `/status`, `/routing`, `/budget`, etc.
- **Everything else goes to LLM** — no word lists, no regex gatekeeping, no `_looksLikeCommand` heuristic
- **System prompt injection** — Claude CLI sessions get Maggy context via `--append-system-prompt`, preventing "command interpretation" responses
- **Pi-direct routing** — non-Claude models (deepseek, kimi, qwen, gemini, codex, grok) route through Pi adapter directly, bypassing Claude Code subprocess
- **User message styling** — constrained to 65% width with proper word-break

#### Fixed
- **Thinking block loop** (`Invalid signature in thinking block`) — stale `claude_session_id` re-resolved from history on every preload; now tracked with `session_cleared` flag + immediate SQLite persistence
- **Project switch** — chat window now resets session and loads correct project chat
- **Natural language treated as commands** — removed all hardcoded word lists (`_SHELL_PREFIXES`, `_KNOWN_PROGRAMS`) from input classification

---

## [6.33.0] - 2026-05-23

### Cortex MCP — Unified Code Intelligence

Cortex replaces codebase-memory-mcp + iCPG + Mnemos with a single Python MCP server. Three layers: Structure (AST), Intent (iCPG), Memory (Mnemos). 15 tools, not 30.

#### Benchmark (claude-skills-package, 526 files)

| Metric | Cortex | codebase-memory-mcp | Delta |
|--------|-------:|--------------------:|-------|
| Symbols | 5,501 | 3,916 | +40% |
| Total edges | 14,850 | 12,010 | +24% |
| CALLS | 5,280 | 2,918 | +81% |
| HANDLES | 352 | 5 | +6940% |
| Incremental reindex | 0.03s | ~2s | 66x faster |
| Symbol search | 0.40ms | ~5ms | 12x faster |
| 3-hop traverse | 0.18ms | ~10ms | 55x faster |

#### Added
- 10 edge types: CALLS, IMPORTS, DEFINES_METHOD, USAGE, TESTS, WRITES, ASYNC_CALLS, HANDLES, RAISES, HTTP_CALLS
- Python edge extraction via full AST analysis
- TypeScript/JavaScript edge extraction via regex
- Cyclomatic complexity scoring per function
- Phantom symbol resolution for external/builtin references
- Git co-change analysis (FILE_CHANGES_WITH edges)
- FTS5 camelCase splitting for better search
- Bidirectional graph traversal

#### Tools (15 consolidated)
- **Structure**: `cortex_index`, `cortex_search`, `cortex_inspect`, `cortex_trace`, `cortex_changes`, `cortex_adr`
- **Intent**: `cortex_intent`, `cortex_analyze`, `cortex_bootstrap`, `cortex_contracts`
- **Memory**: `cortex_memory`, `cortex_checkpoint`, `cortex_fatigue`
- **Cross-layer**: `cortex_explain`, `cortex_status`

---

## [6.32.0] - 2026-05-22

### Elixir Support + System Wiring

- Elixir AST extraction: `defmodule`, `def`, `defp`, route macros
- Cortex wired into Claude Code CLI, Claude Desktop, Maggy codebases
- Build-in-public plugin: native X thread support via Buffer API

---

## [6.31.0] - 2026-05-21

### ADR-Enforced Code Reviews

- ADR enforcement across all bootstrap projects
- 13-tier model routing (AGY, Gemini CLI, Grok added)

---

## [6.29.0] - 2026-05-20

### In-Browser File Editor

- Tab-based file editor with syntax highlighting
- Self-healing commands with fuzzy matching
- Icons-only sidebar, compact working zone
