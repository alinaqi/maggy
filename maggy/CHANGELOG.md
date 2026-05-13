# Changelog

## v0.6.12 — 2026-05-13

### Added
- **Task blueprints** — self-learning repeatable workflows; Maggy captures tool sequences from successful tasks and replays them with cheaper models on similar future tasks (e.g., generating benchmark reports for 16+ companies routes to local after 3 proven examples)
- `blueprint_store.py` — SQLite-backed blueprint persistence with keyword overlap matching, project scoping, time-decay confidence, and collective matching (3+ similar blueprints prove a pattern)
- `blueprint_extract.py` — keyword extraction with path stripping, sha256 fingerprinting, template capture with `{path}`/`{value}` slots
- `api/routes_blueprints.py` — `GET /api/blueprints/` and `GET /api/blueprints/match` endpoints
- `cli_blueprints.py` — `/blueprints` CLI command with Rich table display (type, keywords, confidence, uses)
- **Session persistence** — chat sessions + messages now saved to SQLite, surviving server restarts
- `services/session_store.py` — SQLite store with sessions + messages tables, WAL mode, foreign keys
- **Claude CLI logging** — `_run_claude` now logs start/pid/exit/errors to `~/.maggy/server.log`
- **Claude CLI timeout** — per-line 180s timeout prevents stale sessions from hanging forever; `_read_with_timeout` async generator
- **Arrow key history** — readline import enables up/down command recall in REPL

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

## v0.6.11 — 2026-05-13

### Added
- **`/rules` command** — comprehensive routing rules summary showing task-type overrides, pipeline phases, model performance (strengths + weaknesses), team conventions, stakes classification patterns, and cascade policy in one panel
- `cli_rules.py` — `cmd_rules` with `_fmt_overrides`, `_fmt_phases`, `_fmt_perf`, `_fmt_conventions`, `_fmt_stakes`, `_fmt_cascade` formatters
- Full rules API — `/api/routing/rules` now returns pipeline phases, conventions text, stakes patterns, cascade policy, model weaknesses, and override confidence/source (was only returning overrides + strengths)
- `reviewer_heatmap()` client method (was missing from `cli_client.py`)

## v0.6.10 — 2026-05-13

### Added
- **Reviewer evaluation & knowledge map** — tracks reviewer performance (CodeRabbit vs Codex vs local) by finding category (security, performance, style, logic, architecture) with time-decayed scoring; builds knowledge map so Maggy learns which reviewer is better at what
- `review_scores.py` — SQLite-backed `ReviewerTable` with `record`, `best_reviewer`, `heatmap`, `compare` (same decay pattern as model rewards)
- `services/reviewer_eval.py` — keyword-based finding categorization, `evaluate_review` records to ReviewerTable, `compare_reviewers` for side-by-side
- `api/routes_review.py` — `/api/reviewers/heatmap` and `/api/reviewers/compare` endpoints
- `/reviewers` CLI command shows reviewer × category performance heatmap
- Review findings auto-recorded after review-type chat responses complete

## v0.6.9 — 2026-05-13

### Added
- **Non-blocking REPL** — long-running tasks (CodeRabbit reviews, Codex analysis, etc.) now run in a background thread; REPL stays responsive with `bg>` prompt for `/status` and `/cancel` commands
- `cli_bg_task.py` — thread-safe `TaskState` with `start_task`, `cancel_task`, `get_status`, `is_active`, `collect_result`
- `/status` command shows background task progress (model, chunks, tool calls)
- `/cancel` command stops a running background task

### Changed
- `_send_message()` returns `TaskState` for routed messages (background) or `None` for direct (blocking)
- `_repl_loop()` enters `_bg_loop()` when a background task starts, accepting commands during streaming
- `cmd_stats` moved from `cli_repl_cmds.py` to `cli_repl_info.py`
- `SessionState` has `bg_task` field for background task tracking

## v0.6.8 — 2026-05-13

### Fixed
- **Session history detection** — Claude parser `_slug()` now preserves full resolved paths instead of basename-only (was losing `/Users/ali/maggy` → `maggy`); Codex parser reads `cwd` from rollout files instead of using user-defined `thread_name`; Kimi parser reads `work_dirs` from `kimi.json` instead of hardcoding empty string
- **Project matching** — `_matches_project()` uses strict resolved-path comparison instead of loose substring matching that caused false positives
- **Context fallback** — `gather_cli_context()` falls back to `session_detect.detect_all()` when HistoryService returns no matches

### Added
- **Verified context injection** — `verified_context.py` gathers real git state (branch, status, recent commits) and active CLI sessions; injected alongside history so LLMs don't fabricate project state
- **Collapsible thinking** — tool events accumulate during streaming, collapsed summary (`[N tool calls]`) shown after response; `/thinking` command re-expands the last response's tool events
- **Chat-to-executor bridge** — `chat_executor_bridge.py` routes actionable messages (blast >= 4, non-search/docs/review) through the full executor pipeline (iCPG, TDD, Mnemos, Engram) instead of raw LLM CLI passthrough
- `cli_repl_info.py` extracted from `cli_repl_cmds.py` for session/info/thinking commands

### Changed
- `stream_chunks()` now returns `dict` with `tool_events` list instead of `None`
- `SessionState` has `last_tool_events` field for `/thinking` command
- `_format_sessions()` uses full-path project values (no more basename matching)
- REPL command handlers split across `cli_repl_cmds.py` (routing/budget) and `cli_repl_info.py` (session/info/thinking)

## v0.6.7 — 2026-05-13

### Added
- **Tool progress display** — CLI now surfaces `tool_use` events from Claude CLI's stream-json, showing what Claude is doing (Read, Edit, Bash, Grep, etc.) as dim progress lines above the spinner, matching Claude Code's work-progress UX
- `_format_tool_use()` renders readable labels per tool type (file paths, commands, patterns)
- `parse_chunks()` replaces `parse_chunk()` — returns list of chunks, extracting both `text` and `tool_use` blocks from assistant messages

### Fixed
- **Model label duplication** — model name (codex, kimi, etc.) no longer repeats on every Live refresh; now printed once above the live area via `console.print` instead of being re-rendered inside the Live display
- **SSE timeout** — increased HTTP streaming timeout from 120s to 600s so long-running Claude/Codex operations don't get killed mid-response; also increased `ai_client.py` subprocess timeout to match
- `_StreamState` simplified — removed `model_label` field; routing/tool events print above Live area, Live only manages spinner + content

## v0.6.6 — 2026-05-13

### Changed
- **Claude Code-style streaming UX** — removed knock-knock jokes and joke thread; display is now a clean spinner ("Thinking...") with markdown output, matching Claude Code's minimal style
- Model label shown as dim text instead of a Rule separator
- `/history`, `/sessions`, `/monitor` commands moved to central dispatch in `cli_repl_cmds.py`

### Added
- **Multi-CLI context injection** — on startup, Maggy gathers recent session history from Claude Code, Codex, and Kimi and injects it into the first message so the LLM knows what you've been working on across tools
- `cli_context.py` module for history gathering and project matching
- Server accepts `history_context` on session creation and uses it in the first Claude prompt

### Removed
- Knock-knock joke cycling thread and all 15 jokes from `cli_stream.py`
- Threading/lock machinery from `_StreamState`
- `_show_resume_info` startup dump (replaced by context injection)

## v0.6.5 — 2026-05-13

### Changed
- **CWD = project** — running `maggy` from any directory uses that directory as the project (like Claude Code), no config lookup needed
- Sessions now matched by `working_dir` path instead of `project_key` name, ensuring correct resume across identically-named folders
- Server accepts any existing directory as a project path (no codebase config required)
- REPL prompt pushed to bottom of terminal after welcome panel

### Removed
- Config-based project detection (`detect_project`, `detect_candidates`, `_is_inside`)
- Multi-project disambiguation prompt

## v0.6.4 — 2026-05-12

### Added
- **Claude Code-style streaming UX** — CLI REPL now shows animated spinner, model label (`Working with <model> · blast N`), and cycling knock-knock jokes during response streaming
- **Web dashboard 4-zone chat layout** — top progress shimmer, messages scroll, working zone (model label + jokes), sticky input bar with dividers

### Changed
- Streaming display extracted to `cli_stream.py` for cleaner separation of concerns
- Web chat switched from `/send` to `/send-routed` to display model metadata during streaming
- Jokes and response content render in separate DOM elements (web) / Rich Group zones (CLI), fixing invisible jokes

## v0.6.3 — 2026-05-12

### Added
- **Document processing** — paste Excel, DOCX, PDF, CSV, JSON, TXT paths in chat; text is extracted locally and forwarded to Claude for analysis
- **Auto-install dependencies** — missing optional packages (openpyxl, python-docx, pymupdf) are pip-installed automatically on first use
- **Ollama → Claude API escalation** — vision and intent classification auto-fallback to Claude API when local models are unavailable
- **`maggy restart`** — new CLI command to stop and restart the server

### Changed
- Intent classifier and blast scorer now use escalation (Ollama → Claude API → keyword fallback)
- Chat models extracted to `chat_models.py` for cleaner architecture

## v0.6.2 — 2026-05-12

### Added
- Semantic blast scoring via Qwen3-Coder
- Ghost-text suggestions in chat input (Tab to accept)
- Image path auto-detection in chat → Qwen3-VL vision analysis

### Fixed
- Duplicate greeting ("Hi! How can I help you today?" appeared twice)
- 64KB stream limit crash on long Claude responses

## v0.6.1 — 2026-05-12

### Added
- Sticky chat input pinned to bottom of viewport
- Simplified READMEs, moved reference docs to `docs/`

## v0.6.0 — 2026-05-11

### Added
- Polyphony multi-agent orchestration
- Session resume and multi-CLI detection
- Multi-model routing REPL and session management
- Interactive chat REPL via `maggy chat <project>`
- Upgraded local model to Qwen3-Coder 30B-A3B (MoE, Q8_0)
