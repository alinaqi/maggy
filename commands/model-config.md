# /model-config — Choose the model you follow

View or change the **primary model** that handles your coding work across
srooter (the gateway), the route-task hooks, and Maggy. One setting, read
everywhere. Stored in `~/.claude/model-config.json`.

---

## Usage

`/model-config` — show current primary + what's available
`/model-config <model>` — set the primary (e.g. `minimax`, `claude`, `deepseek`)

### Switch Claude Code to a pre-configured backend

The primary is the model Claude Code's real coding work runs on (through
srooter). To move it to one of the pre-configured backends:

| Say | Backend | srooter alias |
|-----|---------|---------------|
| `/model-config deepseek` | DeepSeek Pro | `deepseek-pro` |
| `/model-config kimi` | Kimi K3 (Moonshot) | `kimi-k3` |
| `/model-config glm` | GLM 5.3 (Z.ai) | `glm-5.3` |
| `/model-config codex` | Codex | `codex` |

The switch takes effect for new sessions (srooter reads `ANTHROPIC_BASE_URL`
and its routes at startup — restart srooter, then start a fresh Claude Code
session). Each backend needs its provider key set in srooter's env
(`DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`, `GLM_API_KEY`, `OPENAI_API_KEY`);
srooter skips any backend whose key is unset and falls back down its chain.

### Direct provider — bypass srooter entirely (`--direct`)

DeepSeek Pro, GLM 5.3, and Kimi K3 each publish a native
**Anthropic-compatible** endpoint, so Claude Code can talk to them *directly*
with no srooter hop. `/model-config <backend> --direct` writes a launcher into
`~/bin`:

| Say | Launcher | Endpoint · model |
|-----|----------|------------------|
| `/model-config deepseek --direct` | `claude-deepseek` | `api.deepseek.com/anthropic` · `deepseek-v4-pro` |
| `/model-config glm --direct` | `claude-glm` | `api.z.ai/api/anthropic` · `glm-5.3` |
| `/model-config kimi --direct` | `claude-kimi` | `api.moonshot.ai/anthropic` · `kimi-k3` |

```bash
MR="$(cat ~/.claude/.bootstrap-dir)/scripts/model_routing.py"
python3 "$MR" write-launcher deepseek   # one backend
python3 "$MR" write-launchers           # all three at once
```

Then just run `claude-deepseek` (or `claude-glm` / `claude-kimi`) instead of
`claude` — that session runs directly on the provider, reading its key from
your env (`DEEPSEEK_API_KEY`, `GLM_API_KEY`/`ZHIPUAI_API_KEY`,
`MOONSHOT_API_KEY`/`KIMI_API_KEY`). Plain `claude` and the srooter path above
are untouched, so you pick per terminal.

**Codex is not direct-capable** — OpenAI has no Anthropic Messages API, so
Codex can only be reached through srooter's `/anthropic → /v1/responses`
translation (`/model-config codex`, above). There is no `claude-codex` launcher.

---

## Steps

The brain is `scripts/model_routing.py` in claude-bootstrap. Resolve it via
`~/.claude/.bootstrap-dir`:

```bash
MR="$(cat ~/.claude/.bootstrap-dir)/scripts/model_routing.py"
```

### 1. Show current state (no argument)

```bash
echo "Available on this machine:"
python3 "$MR" detect | python3 -c "import sys,json;print(', '.join(k for k,v in json.load(sys.stdin).items() if v))"
echo "Current config:"
python3 "$MR" show
```

Report: which model is `primary`, the `classifier`, the `mode` (smart/hard),
and the available models. If `auto_detected` is true, mention it was inferred
from the machine and can be overridden.

### 2. Set a new primary (argument given)

```bash
python3 "$MR" set-primary "<model>"     # validates against the detected set
python3 "$MR" apply                     # sync into srooter.yaml (long_context + substantive)
```

Then tell the user it takes effect for new sessions. If srooter is running,
it must be restarted to pick up the routing change:

```bash
cd "$(cat ~/.claude/.bootstrap-dir)/../srooter" 2>/dev/null && \
  echo "Restart srooter to apply: kill \$(cat .srooter.pid); and relaunch"
```

---

## Notes

- **Smart mode** (default): the primary handles real coding; trivial/cheap
  asks still route to the local classifier (qwen) and explicit per-prompt
  overrides ("use claude") always win.
- No hardcoding — if the config is missing it is auto-created from what's
  installed/keyed on the machine.

### Pre-analysis (MiniMax on every prompt)

When `"analyze": true` (default), the route-task hook sends each prompt to
MiniMax first for a terse INTENT / SCOPE / RISKS / APPROACH brief and injects
it into context, so Claude executes with that read of the task. Adds ~3-5s per
prompt. Toggle:

```bash
python3 "$MR" set-analyze false   # turn off (prompts go straight through)
python3 "$MR" set-analyze true    # turn back on
```

The hook fails open — if MiniMax is slow/unreachable, routing proceeds without
the analysis (capped at MINIMAX_TIMEOUT=20s).

## Related

- `scripts/onboard.sh` — sets this during onboarding
- `/maggy-init` — Maggy setup
