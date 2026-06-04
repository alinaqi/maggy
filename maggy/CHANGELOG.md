# Changelog — Maggy

All notable changes to Maggy will be documented in this file.

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
