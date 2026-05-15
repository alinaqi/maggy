# CLAUDE.md

## Skills
Read and follow these skills before writing any code:
- skills/base.md
- skills/security.md
- skills/project-tooling.md
- skills/session-management.md
- skills/python.md
- skills/typescript.md
- skills/react-web.md
- skills/pwa-development.md
- skills/llm-patterns.md
- skills/supabase.md
- skills/external-model-delegation/SKILL.md

## Project Overview
Maggy — A local AI engineering command center bundled with claude-bootstrap. AI-prioritized inbox across issue trackers (GitHub Issues/Asana), one-click TDD execute with iCPG context enrichment, Mnemos fatigue-aware memory lifecycle, and multi-model routing across Qwen3, DeepSeek, Kimi, Codex, and Claude.

## Tech Stack
- **Backend**: Python (FastAPI)
- **Database**: SQLite (via aiosqlite)
- **AI/ML**: OpenAI, Anthropic, DeepSeek, Moonshot (Kimi), Ollama (local Qwen3)
- **Testing**: pytest
- **Linting**: ruff, mypy

## Project Structure
```
maggy/
├── maggy/                 # Main Python package
│   ├── api/               # FastAPI routes
│   ├── mnemos/            # Memory lifecycle (fatigue, checkpoint, REM)
│   ├── process/           # Model routing, blast scoring
│   ├── services/          # AI client, chat router, executor
│   ├── orchestrator/      # Agent adapters (claude, codex, deepseek, kimi)
│   ├── providers/         # Issue tracker integrations
│   └── coordination/      # Lock manager, escalation
├── tests/                 # pytest test suite
└── pyproject.toml
skills/                    # Shared skill definitions
├── external-model-delegation/
└── ...
templates/                 # Hook and config templates
```

## Key Commands
```bash
# Maggy
cd maggy
pip install -e ".[dev]"
pytest
ruff check .
mypy src/

# Skills verification
./scripts/verify-tooling.sh

# Deploy
vercel --prod
```

## Model Routing

Maggy routes tasks to the optimal model based on complexity, security sensitivity, and fatigue. See `skills/external-model-delegation/SKILL.md` for the full delegation pattern.

| Tier | Model | Cost | Role |
|------|-------|------|------|
| 0 | Qwen3 (local) | $0 | File reads, quick edits, boilerplate |
| 1 | DeepSeek V4 Flash | $0.14 / $0.28 | Sub-agents, cheap internal calls |
| 2 | DeepSeek V4 Pro | $0.435 / $0.87 | Main coding workhorse |
| 3 | Kimi K2.6 | $0.60 / $2.50 | Long agentic loops, routing alt |
| 4 | Codex | varies | Code review, bulk generation |
| 5 | Claude Sonnet/Opus | $3-5 / $15-25 | Quality-critical, security |

## Project-Specific Patterns

### Backend Patterns
- FastAPI with dependency injection
- Model routing via blast-score and fatigue-aware selection
- Mnemos memory lifecycle: checkpoint → compact → REM recall
- Polyphony multi-agent orchestration with container isolation

### AI Patterns
- Structured outputs from LLMs using Pydantic models
- Retry with exponential backoff for API failures
- Token budget management for cost control
- External model delegation via ~/bin/ scripts
