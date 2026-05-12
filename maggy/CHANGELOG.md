# Changelog

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
