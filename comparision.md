# Maggy — Conversation Log

## What does this folder do?

**Maggy** is an autonomous AI engineering command center. Here's the gist:

**What it does:**
- Routes tasks across 10+ AI models (Claude, DeepSeek, Gemini, Qwen, Grok, etc.) based on complexity and cost
- Exposes a **FastAPI backend** with 30+ route modules — chat, plugins, budget tracking, competitor intel, deployment, testing
- Has a **memory system** (`mnemos/`) for fatigue tracking and checkpoint serialization
- Provides a **plugin manager** with a HookBus for extensibility
- Ships a **vanilla JS dashboard** (`static/`) for monitoring and control
- Includes 62+ pre-built **skills** and delegation binaries in `bin/`

**Tech stack:** Python 3.11+, FastAPI, Anthropic SDK, Pydantic, Tailwind CSS (frontend)

**In one sentence:** It's a meta-AI orchestration platform that wraps and routes between multiple LLMs for different task tiers, with memory, plugins, and a web dashboard.

---

## How could anyone use it?

There are two main ways to use it:

### As a Bootstrap for Any Project
Installs skills, hooks, rules, and memory into any existing or new codebase:
```bash
git clone https://github.com/alinaqi/maggy.git
cd maggy && ./install.sh

# In your project
claude
> /initialize-project
```
This gives your Claude Code sessions: TDD enforcement, 62 skills, quality gates, agent teams (spec → test → implement → review → PR), and persistent memory.

### As a Running AI Command Center
Run the Maggy server to get a full dashboard + CLI:
```bash
cd maggy && pip install -e .
maggy serve     # dashboard at localhost:8080
maggy           # interactive CLI REPL
```
From there you get:
- **Chat** with model routing (tasks auto-routed to cheapest capable model)
- **Task inbox** from GitHub Issues or Asana, AI-prioritized
- **Competitor tracking** with daily briefings
- **Build-in-public plugin** — auto-writes LinkedIn/X posts when you ship

### Who it's for
Primarily for **solo AI-heavy developers** or small teams who want to orchestrate multiple LLMs cost-efficiently without manually picking models for every task. DeepSeek handles ~80% of work cheaply; Claude only gets called for architecture/security decisions.

---

## Do we need API keys for DeepSeek?

Yes — each model needs its own API key set as an environment variable:

| Model | Env Var | Where to get it |
|-------|---------|-----------------|
| DeepSeek | `DEEPSEEK_API_KEY` | platform.deepseek.com |
| Gemini | `GEMINI_API_KEY` | aistudio.google.com |
| Grok | `GROK_API_KEY` | console.x.ai |
| Kimi | `KIMI_API_KEY` | platform.moonshot.cn |
| Anthropic/Claude | `ANTHROPIC_API_KEY` | console.anthropic.com |
| Qwen3 (local) | none — runs locally via Ollama | free |

You'd set these in your shell profile (`~/.zshrc`) or a `.env` file:
```bash
export DEEPSEEK_API_KEY="sk-..."
export GEMINI_API_KEY="AIza..."
```

You don't need all of them — just the models you actually want to use. DeepSeek alone covers ~80% of coding tasks per the routing design.

---

## DeepSeek is from China, right?

Yes, DeepSeek is a Chinese AI company (based in Hangzhou, founded by High-Flyer, a Chinese hedge fund).

Key concerns people raise:
- **Data privacy** — API calls go to servers in China, subject to Chinese law
- **Model weights** — open-source, so you can run locally and avoid the API entirely
- **Export controls** — some orgs have policies against using Chinese AI services

If that's a concern, the routing tiers in Maggy can be adjusted to skip DeepSeek and use alternatives like Gemini Pro or Claude Sonnet instead — the routing config is all in `maggy/maggy/process/model_router.py`.

---

## How can we build on top of what is in Maggy?

Four clean extension points, from easiest to most involved:

### 1. Write a Skill (easiest)
A skill is just a Markdown + YAML file. Drop it in `skills/your-skill/` and reference it in `CLAUDE.md` via `@include`. No code needed — it's a prompt template that activates for specific tasks.

Good for: adding domain knowledge, coding patterns, or workflows Claude should follow.

### 2. Write a Plugin
The most powerful extension point. Drop a folder with `plugin.yaml` + `plugin.py` into `maggy/maggy/plugins/` — auto-discovered on startup.

```yaml
id: my-plugin
version: 1
entrypoint: plugin.py
hooks:
  - event: on_task_fetch
    handler: handle_tasks
  - event: on_feature_shipped
    handler: post_update
heartbeat:
  - name: my_poll
    interval_seconds: 300
    fn: poll_something
```

Good for: integrating new data sources (Linear, Jira, Notion), new output channels (Slack, Discord), or custom automation triggers.

Existing plugin examples to copy: `provider-github`, `provider-asana`, `provider-monday`.

### 3. Add a Model Tier / Swap DeepSeek
Edit `maggy/maggy/process/model_router.py` and add/replace a tier. Also add a corresponding delegation script in `bin/`. The contract is simple: script accepts a prompt, writes response to stdout.

Good for: replacing DeepSeek with a non-Chinese alternative (e.g. Mistral, Llama via Groq), or adding a new specialized model.

### 4. Add a REST API Route
Add a `routes_*.py` file in `maggy/maggy/api/` and register it in `maggy/maggy/main.py`. The FastAPI structure is already in place.

Good for: exposing Maggy capabilities to other tools, building a frontend on top, or integrating with webhooks.

---

## What is the effort for #3 and #4?

### #3 — Add/Swap a Model Tier
**Effort: 1-2 hours**

Two files to touch:

**`maggy/maggy/process/model_router.py`** — add a new `ModelTier` to `DEFAULT_TIERS`:
```python
ModelTier(
    name="mistral",
    provider="mistral",
    model="mistral-large-2",
    cost_rank=4,          # sits between deepseek-flash and deepseek-pro
    complexity_min=2,
    complexity_max=7,
    strengths=["code_generation", "debugging", "european_hosting"],
),
```

**`bin/mistral`** — new delegation script (copy `bin/deepseek`, swap the API base URL and key env var). Contract is just: accept prompt → print response to stdout.

To remove DeepSeek entirely: delete its two `ModelTier` entries from `DEFAULT_TIERS` and remove `bin/deepseek`.

### #4 — Add a REST API Route
**Effort: 30 minutes**

1. Create `maggy/maggy/api/routes_yourfeature.py`:
```python
from fastapi import APIRouter, Request
from .auth import check_auth

router = APIRouter(prefix="/api/yourfeature", tags=["yourfeature"])

@router.get("/something")
async def get_something(request: Request) -> dict:
    check_auth(request, None)
    return {"result": "..."}
```

2. Register in `maggy/maggy/main.py` — find the block where all `routes_*.py` routers are imported and add yours alongside them.

3. Write the test first (`tests/test_routes_yourfeature.py`) per the TDD policy.

---

## Can DeepSeek do what Claude can do?

Not quite. Here's the honest comparison:

**DeepSeek is good at:**
- Code generation, refactoring, debugging
- Writing tests, CRUD, boilerplate
- Following instructions precisely
- ~80% of day-to-day engineering tasks

**DeepSeek falls short vs Claude on:**
- **Security-critical reasoning** — Claude is more careful about subtle vulnerabilities
- **Architecture decisions** — Claude reasons better about long-term trade-offs
- **Ambiguous requirements** — Claude handles underspecified problems more gracefully
- **Long multi-file refactors** — Claude maintains coherence better across large contexts
- **Nuanced code review** — catches more subtle logic bugs

That's exactly why Maggy's routing keeps Claude at Tier 11 (the top) — it's the model you call when correctness and judgment matter, not just code output. DeepSeek is the workhorse for volume; Claude is the senior engineer you pull in for the hard stuff.

In practice: if you removed DeepSeek and routed everything to Claude, you'd get better quality but 10-20x higher cost. The routing system exists precisely to avoid that.

---

## Instead of DeepSeek, can we use a US/local alternative?

Yes, several good options depending on whether you want **local** or **US cloud**:

### Local (free, private, no API keys)
Already have Ollama running for Qwen3 — just pull more models:

| Replaces | Model | Notes |
|----------|-------|-------|
| DeepSeek Flash | `ollama pull codellama:34b` or `llama3.3:70b` | fast, good at code |
| DeepSeek Pro | `ollama pull qwen2.5-coder:72b` | best local coding model right now |

Zero cost, nothing leaves your machine.

### US Cloud (API, cheap)
| Replaces | Provider | Model | Cost |
|----------|----------|-------|------|
| DeepSeek Flash | **Groq** | `llama-3.3-70b` | ~$0.06/M — extremely fast |
| DeepSeek Pro | **Together AI** | `llama-3.1-405b` | ~$0.35/M |
| Both | **Fireworks AI** | various Llama/Qwen | similar pricing |

Groq is the standout — US company, insanely fast inference, Llama models, very cheap.

### Recommendation
**Best swap:**
- Flash tier → **Groq + Llama 3.3 70B** (faster than DeepSeek, US-based, cheap)
- Pro tier → **Qwen2.5-Coder 72B via Ollama** (free, local, strong at code)

The `bin/deepseek` script would need two replacements — `bin/groq-flash` and the Ollama call is already handled by the existing `bin/qwen3` pattern.

---

## How does it work once installed in Claude Code?

```
You type a prompt in Claude Code
        ↓
route-task-hook fires BEFORE Claude sees it
        ↓
qwen3 (local, free) classifies the task
        ↓
Hook injects routing instructions into Claude's context
        ↓
Claude reads the instruction and delegates:
  "write this CRUD endpoint" → calls ~/bin/groq-flash
  "refactor this module"     → calls ~/bin/ollama-pro
  "design this auth system"  → handles it directly (CLAUDE tier)
```

**So Claude Code stays as the orchestrator** — it reads your prompt, sees the routing decision, then calls the cheaper model via the `bin/` script and returns the result. You still type in Claude Code as normal, but most of the actual generation happens in Ollama or Groq.

**What we'd need to implement for your setup:**
1. Replace `bin/deepseek` with `bin/groq` (US cloud, cheap)
2. Add `bin/ollama-coder` pointing at `qwen2.5-coder:72b` locally
3. Update `DEFAULT_TIERS` in `model_router.py` — swap DeepSeek entries for Groq/Ollama
4. Update the tier names in `route-task-hook` classifier prompt

**Realistic effort: 2-3 hours.**

---

## What is the cost difference?

Based on published pricing (approximate):

| Task | Current (DeepSeek) | Groq (Llama 3.3 70B) | Ollama (local) |
|------|--------------------|----------------------|----------------|
| Flash tier | $0.14/$0.28 per M tokens | ~$0.05/$0.08 per M | $0 |
| Pro tier | $0.44/$0.87 per M tokens | ~$0.59/$0.79 per M | $0 |

**So:**
- **Flash tier** — Groq is actually **cheaper** than DeepSeek (~3x less)
- **Pro tier** — Groq is roughly **similar** to DeepSeek, maybe slightly more
- **Ollama** — free for both, just your hardware running it

**Real-world estimate** for a typical dev day (~1M tokens):

| Setup | Daily cost |
|-------|-----------|
| All Claude | ~$5-15 |
| Current Maggy (with DeepSeek) | ~$0.50-1.50 |
| Maggy with Groq + Ollama | ~$0.10-0.50 |
| Maggy with pure Ollama | ~$0 |

The biggest saving is already baked into the routing design (not using Claude for everything). Swapping DeepSeek for Groq/Ollama is a smaller delta — but removes the China data concern entirely.

> **Note:** Groq pricing changes frequently. Verify at groq.com/pricing before implementing.

---

## Is US-based cheaper AND better than DeepSeek?

For the **flash tier** (simple code, boilerplate) — yes, Groq is cheaper AND faster than DeepSeek Flash. No quality trade-off.

For the **pro tier** (features, refactors, debugging):

| | DeepSeek Pro | Groq Llama 3.3 70B | Ollama local |
|---|---|---|---|
| Cost | $0.44/$0.87/M | ~$0.59/$0.79/M | $0 |
| Code quality | Very strong | Good, not quite as sharp | Depends on hardware |
| Speed | Fast | Fastest inference available | Depends on GPU/CPU |
| Privacy | China servers | US servers | Your machine |

- Flash tier → Groq (cheaper + faster, no quality loss)
- Pro tier → Ollama locally if you have a good GPU (free + private), or Together AI 405B for quality
- The real win is **data sovereignty** — code never leaves US infrastructure or your machine

---

## Flex config — let users choose their provider per tier

Design: a config file (`~/.maggy/routing.yaml`) where each tier maps to the user's preferred provider:

```yaml
# ~/.maggy/routing.yaml
tiers:
  flash: groq           # groq | deepseek | ollama
  pro: ollama-coder     # ollama-coder | deepseek | together | groq
  multimodal: gemini    # stays as-is
```

**What needs to be built:**
1. `bin/groq` — Groq API script (Llama 3.3 70B)
2. `bin/ollama-coder` — Ollama script (qwen2.5-coder:72b)
3. `bin/together` — Together AI script (Llama 3.1 405B)
4. `~/.maggy/routing.yaml` — user config with defaults
5. `model_router.py` — reads config, swaps provider at startup
6. `route-task-hook` — reads config, picks the right `bin/` script per tier
7. REST endpoint `GET/POST /api/routing/config` — dashboard can read/update without editing YAML

**Result:** US-only users set `flash: groq, pro: together`. Fully local users set both to `ollama`. DeepSeek stays available as an option, just not the default.

**Effort: ~4-5 hours.**

**Recommended defaults:** Groq for flash, Together AI for pro.

---

## Is Ollama quality the same as Claude?

No. Honest quality ladder for coding:

```
Claude Opus
    ↓ (small gap)
Claude Sonnet
    ↓ (small-medium gap)
Together AI 405B / DeepSeek Pro
    ↓ (medium gap)
Groq Llama 3.3 70B
    ↓ (medium gap)
Ollama qwen2.5-coder:72b (good hardware)
    ↓ (big gap)
Ollama on CPU / smaller models
```

**Ollama local (qwen2.5-coder:72b):**
- Strong at straightforward tasks — CRUD, tests, boilerplate, single-file changes
- Struggles with complex multi-file refactors, subtle bugs, ambiguous requirements
- Quality depends heavily on your GPU RAM
- 72B on CPU is slow and noticeably weaker than API models

**Together AI (Llama 3.1 405B):**
- Much closer to Claude Sonnet for coding — 405B parameters makes a real difference
- Good at multi-file work, debugging, documentation
- Still behind Claude on architecture reasoning and security analysis

**Conclusion:** Ollama is great for flash-tier tasks. For pro-tier work, Together AI 405B is the better US-based choice. Free does not mean equivalent.

---

## Claude vs Together AI pricing

| Model | Input/M | Output/M |
|-------|---------|---------|
| Together AI Llama 3.1 405B | ~$3.50 | ~$3.50 |
| Claude Sonnet | ~$3.00 | ~$15.00 |
| Claude Opus | ~$15.00 | ~$75.00 |

Output tokens are where Claude gets expensive — code generation produces a lot of output, that's where the bill hits. Together AI 405B is cheaper than Claude Sonnet on output (~$3.50 vs ~$15.00) and comparable quality for most coding tasks.

Claude stays at Tier 11 for architecture, security, and quality-critical work where the premium is justified.
