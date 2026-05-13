# Changelog

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
