# Changelog

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
