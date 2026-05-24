# Changelog — Maggy

All notable changes to Maggy will be documented in this file.

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
