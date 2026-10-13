---
name: model-routing
description: 9-tier model routing system with cascading classifier fallback and result auto-evaluation
when-to-use: When configuring or debugging how prompts are classified and routed to the cheapest capable model
user-invocable: false
effort: medium
---

# Model Routing System

## How Routing Decisions Are Made

Every user prompt goes through a 9-tier classification pipeline before any AI model processes it. The system answers three questions:

1. **Which model should handle this?** — 9-tier cost/complexity classification
2. **Is the classifier itself working?** — Cascading fallback (qwen3 → kimi → deepseek → cache)
3. **Can we verify the result?** — Tool-level fallback + auto-evaluation

### The Pipeline

```
User types prompt
    ↓
UserPromptSubmit hook fires (~/.claude/hooks/route-task-hook)
    ↓
Classifier: qwen3 (local, free) classifies into tier
    ↓  (fails?)
Classifier: kimi (local, free) retries
    ↓  (fails?)
Classifier: deepseek-flash (~$0.0001) retries
    ↓  (fails?)
Classifier: cached tier from last success
    ↓
Hook injects routing decision into Claude's context
    ↓
Claude delegates to the right model or handles directly
```

## 9-Tier Routing Table

| Tier | Model | Input (per M) | Output (per M) | Handles |
|------|-------|---------------|----------------|---------|
| 1 | **Gemini 2.5 Flash-Lite** | $0.10 | $0.40 | Bulk extraction, classification, CIG pipelines |
| 2 | **DeepSeek V4 Flash** | $0.14 | $0.28 | Simple code, CRUD, test writing, small fixes |
| 3 | **DeepSeek V4 Pro** | $0.44 | $0.87 | Multi-file features, refactors, debugging (~80% of work) |
| 4 | **Gemini 2.5 Flash** | $0.15 | $0.60 | Multimodal (images, video, audio), brand analysis |
| 5 | **Kimi K2.6** | $0.60 | $2.50 | Code review, commit messages, diff summaries |
| 6 | **Gemini 3.1 Pro + Search** | $1.25 | $10.00 | Deep research, Google grounding, 2M context |
| 7 | **Codex** | varies | varies | Bulk generation, code review |
| 8 | **Claude Sonnet/Opus** | $3-5 | $15-25 | Architecture, security, quality-critical |

## Delegation Commands

When the hook says "delegate to X", run the matching command and return its output:

```bash

# Tier 1 — Gemini Flash-Lite
~/bin/gemini --flash-lite "prompt"

# Tier 2 — DeepSeek Flash
~/bin/deepseek --flash "prompt"

# Tier 3 — DeepSeek Pro
~/bin/deepseek --pro "prompt"

# Tier 4 — Gemini Flash
~/bin/gemini --flash "prompt"

# Tier 5 — Kimi
~/bin/kimi --quiet -p "prompt"

# Tier 6 — Gemini Pro Search
~/bin/gemini --pro-search "prompt"

# Tier 7 — Codex
codex exec "prompt"

# Tier 8 — Claude
# Handle directly (no delegation)
```

## Delegation Script Contract

Every `~/bin/` script follows the same pattern:

1. **Accepts prompt as argument**: `script "what is 2+2"`
2. **Model flags**: `--flash`, `--pro`, `--flash-lite`, `--pro-search`
3. **Quiet mode**: `--quiet` (where applicable)
4. **Output**: writes response to stdout, errors to stderr
5. **Exit codes**: 0 on success, non-zero on failure

### Available Scripts

```
~/bin/
├── qwen3       # Shell: curl to local Ollama API
├── kimi        # Shell: execs Kimi CLI binary
├── deepseek    # Python: httpx to DeepSeek Anthropic-compat API
├── gemini      # Python: httpx to Gemini OpenAI-compat API
├── research    # Python: multi-backend research with auto-evaluation
└── route-task  # Shell: qwen3-powered task classification
```

## Classifier Fallback Chain

The classifier itself can fail. When it does, cascading fallback kicks in:

| Level | Classifier | Cost | Threshold |
|-------|-----------|------|-----------|
| 1 | **qwen3** (Ollama) | $0 | 2s connect, 8s classify |
| 2 | **kimi** CLI | $0 | Local process |
| 3 | **deepseek-flash** | ~$0.0001 | API call |
| 4 | **Cached tier** | $0 | From `~/.claude/routing-cache.json` |

The cache (`~/.claude/routing-cache.json`) saves the last successful tier and timestamp. After compaction, when Ollama may be briefly unreachable, the cache ensures routing continues without dropping to CLAUDE by default.

## Missing Wrapper Fallback

Before the hook emits a delegation instruction it checks that the tier's wrapper
exists (the resolved flash/pro binary, `~/bin/gemini-api`, `~/bin/gemini-cli`,
`~/bin/kimi`, `~/bin/grok`, or `codex` on PATH). If it is missing, the decision
becomes `ROUTING DECISION: CLAUDE (fallback from <tier>)` and Claude handles the
task directly, without the PLAN FIRST step. A cached tier the hook no longer
knows is discarded the same way. There is no qwen3 delegation tier any more.

## Tool Fallback Protocol

When Claude's built-in tools fail, external backends take over:

| Failed Tool | Fallback 1 | Fallback 2 |
|-------------|------------|------------|
| **WebSearch** / **WebFetch** | `~/bin/research "query"` | `~/bin/deepseek --pro "query"` |
| **Read** / file access | `cat` via Bash | — |
| **Grep** | `grep -r` via Bash | — |

### Research Tool (`~/bin/research`)

Multi-backend research with auto-evaluation:
- Tries **deepseek-flash → deepseek-pro** in sequence
- Scores results 0-10 on content quality, structure, length
- Auto-adjusts preferred backend based on evaluation scores
- View stats: `~/bin/research --eval`
- Score log: `~/.claude/research-eval.jsonl`

## Maggy Integration

Maggy's `model_router.py` mirrors the same 9-tier structure in `DEFAULT_TIERS`. The `PiAdapter` uses the same delegation scripts for execution. Task type overrides in `routing_rules_defaults.py` ensure:

- `research`, `competitor` → **Gemini Pro Search** (Google grounding)
- `bulk` → **Gemini Flash-Lite** (cheapest)
- `security`, `architecture`, `planning` → **Claude** (quality-critical)
- `docs`, `tests` → **DeepSeek Pro** (cost-efficient)
- `review` → **Claude** (security + architecture depth)

## Environment

```bash
# Required for delegation scripts (in ~/.zshrc)
export DEEPSEEK_API_KEY="sk-..."
export GEMINI_API_KEY="..."       # For gemini delegator
export OPENAI_API_KEY="sk-..."    # For codex CLI

# Ollama must be running locally for qwen3
ollama serve  # or launch at startup
```

## Observability

- **Routing log**: `~/.claude/routing-log.jsonl` — every classification with tier, classifier used, tokens saved
- **Routing cache**: `~/.claude/routing-cache.json` — last tier for post-compact recovery
- **Research eval**: `~/.claude/research-eval.jsonl` — per-query backend scoring
- **Maggy routing heatmap**: Dashboard → Models tab → per-model reward scores
