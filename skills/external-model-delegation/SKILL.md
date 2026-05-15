# External Model Delegation Pattern

A `UserPromptSubmit` hook classifies every user prompt into one of six cost/performance tiers. The hook injects `additionalContext` instructing Claude to run a specific delegation script and return the output.

## Tier routing table

| Tier | Delegation command | Cost |
|------|-------------------|------|
| QWEN | `qwen3 "prompt"` | $0 (local Ollama) |
| DEEPSEEK_FLASH | `deepseek --flash "prompt"` | $0.14 / $0.28 per M tokens |
| DEEPSEEK_PRO | `deepseek --pro "prompt"` | $0.44 / $0.87 per M tokens |
| KIMI | `kimi --quiet -p "prompt"` | $0.60 / $2.50 per M tokens |
| CODEX | `codex exec` | varies |
| CLAUDE | handle natively | $3-5 / $15-25 per M tokens |

## Delegation script pattern

Each script is a self-contained executable in `~/bin/` that accepts a prompt and writes the response to stdout:

```
~/bin/
├── qwen3      # Shell: curl to local Ollama API
├── kimi       # Shell: execs Kimi CLI binary
├── deepseek   # Python: httpx to DeepSeek Anthropic-compat API
└── route-task # Shell + qwen3: classifies prompt into tier
```

### Script contract

1. Accept prompt as first argument: `qwen3 "what is 2+2"`
2. Support `--flash` / `--pro` model flags (deepseek)
3. Support `--quiet` mode flag (kimi)
4. Write response to stdout, errors to stderr
5. Exit 0 on success, non-zero on error

### Writing a new delegation script

```bash
#!/bin/bash
# Minimal delegator template
PROMPT="$1"
API_KEY="${EXTERNAL_API_KEY:-}"
# Call external API, write result to stdout
curl -s https://api.example.com/chat \
  -H "Authorization: Bearer $API_KEY" \
  -d "$(jq -n --arg p "$PROMPT" '{prompt: $p}')" \
  | jq -r '.response'
```

## Routing hook flow

```
User types prompt
    ↓
UserPromptSubmit hook fires
    ↓
qwen3 classifies into tier (QWEN|DEEPSEEK_FLASH|DEEPSEEK_PRO|KIMI|CODEX|CLAUDE)
    ↓
Hook injects additionalContext: "Run: <delegation-command>"
    ↓
Claude reads context, spawns delegation script, returns output
    ↓
User sees response from the delegated model
```

## Classification tiers

| Tier | Task types |
|------|-----------|
| QWEN | grep, find, regex, shell, syntax lookups, log reading, short summaries |
| DEEPSEEK_FLASH | Simple code, boilerplate, CRUD, test writing, small fixes, config |
| DEEPSEEK_PRO | Multi-file features, refactors, debugging, medium coding, docs |
| KIMI | Single-file review, medium reasoning, commit messages, diff summaries |
| CODEX | Bulk generation, mechanical changes across many files |
| CLAUDE | Architecture, security, complex debugging, system design, quality-critical |

## Environment

```bash
# Required env vars (set in ~/.zshrc)
export DEEPSEEK_API_KEY="sk-..."      # For deepseek delegator
export OPENAI_API_KEY="sk-..."         # For codex CLI
# Ollama must be running locally for qwen3 classification + delegation
```
