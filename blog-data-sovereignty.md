# Your Code Is the New Factory Floor — Don't Outsource It to China

*A technical and cultural case for AI data sovereignty in the era of LLM-powered development*

---

There is a sentence that every American software engineer should read slowly before running their next AI coding assistant:

**"Your source code, your business logic, your API keys, your architecture decisions — where do they go when you hit Enter?"**

If you are using DeepSeek as your coding AI, the answer is: **China.**

Not metaphorically. Not as hyperbole. Literally — to servers in Hangzhou, operated by a company called High-Flyer, a Chinese quantitative hedge fund, under Chinese law, which includes the National Intelligence Law of 2017. That law requires Chinese organizations to "support, assist, and cooperate with state intelligence work" when asked.

We are not here to demonize DeepSeek. Their engineering is genuinely world-class. The V3 model is one of the most impressive open-weights releases in AI history. The team is brilliant, the benchmarks are real, and the price point is extraordinary.

But brilliant engineering from a Chinese company does not change the legal architecture it operates under.

And we have been here before.

---

## We Watched the Factory Leave. Are We About to Watch the Data Leave Too?

In the 1970s and 1980s, American politicians and business leaders made a generational bet: manufacturing was a commodity. Ship it to China. Keep the "high value" work — design, brand, finance — at home.

For a generation it looked like genius. Cheap goods. Fat margins. Globalization as inevitability.

We now know what that bet actually cost. Entire industrial regions hollowed out. Supply chains weaponized during a pandemic. Semiconductor dependencies exposed. A geopolitical rival with industrial capacity that took sixty years and trillions of dollars to build — handed to them in the name of quarterly earnings.

The AI era is offering us the exact same trade, dressed in new clothes.

The offer this time is not "let us make your widgets cheaply." It is "let us process your intelligence cheaply." Your code. Your business logic. Your unreleased product architecture. Your security models. Your customer data patterns. Every prompt you send to a Chinese AI API is a packet of intelligence leaving your country.

The politicians of the 70s and 80s were not stupid. They were optimistic. They believed economic interdependence would moderate behavior. They were wrong.

We should not repeat the same mistake in software.

---

## Enter Maggy — An Autonomous AI Engineering Command Center

Before we talk about what we built, credit where it is due.

**[Maggy](https://github.com/alinaqi/maggy)** — built by Ali Naqi — is one of the most thoughtful open-source AI engineering systems available today. It is not a wrapper around a single model. It is a full orchestration layer: a 10-tier intelligent routing system that classifies every task by complexity and cost, then delegates to the cheapest model capable of handling it.

The architecture is genuinely sophisticated:

- A **FastAPI backend** with 30+ route modules covering chat, memory, competitor intelligence, deployment, and more
- **Mnemos** — a typed memory graph that survives context compaction, with a 4-dimension fatigue model that detects agent struggle before it becomes a death spiral
- **62 pre-built skills** covering TDD enforcement, security review, agent teams, multi-database patterns, and more
- A **plugin system** where new capabilities drop in as folders — no core changes needed
- A **hook system** that intercepts every Claude Code prompt before Claude sees it and routes it to the right model

The routing logic alone is worth studying. Rather than a single point of failure, it cascades:

```
Your prompt
    ↓
qwen3 (local, free) classifies complexity
    ↓ fails? →
kimi fallback
    ↓ fails? →
flash model fallback
    ↓ always available →
Claude handles it directly
```

The result: **~80% of coding tasks never reach Claude.** Simple code, boilerplate, CRUD, tests — handled by cheaper models. Claude is reserved for architecture, security, and quality-critical work. A developer paying $5-15/day on Claude alone can get to $0.50-1.50 with intelligent routing.

This is not a toy. This is a production-grade engineering system.

And it shipped with DeepSeek as the workhorse for that 80%.

---

## The Problem We Had to Fix

The default configuration of Maggy routes the bulk of coding tasks — everything from "write this CRUD endpoint" to "refactor this module" — through DeepSeek's API.

That means your code goes to China.

Not your final built artifact. Not a compiled binary. Your **source code**. The raw, readable, proprietary logic of what you are building. The architecture of systems that have not shipped yet. The names of your internal services. The patterns in your data models. The security assumptions baked into your auth layer.

For a hobbyist building a weekend project, maybe that is an acceptable trade. For a company building software that matters — healthcare, fintech, defense-adjacent, any regulated industry — it is not.

And for engineers who simply believe that the AI era should not repeat the manufacturing outsourcing mistake, it is a principle worth acting on.

So we forked Maggy, studied the architecture, appreciated the elegance of what was built, and added **data sovereignty as a first-class feature**.

The PR is here: **[sseshachala:feat/flex-provider-routing-sovereignty → alinaqi/maggy #26](https://github.com/alinaqi/maggy/pull/26)**

---

## What We Built: Flex Provider Routing With Sovereignty Enforcement

The core idea is simple: **the routing logic is brilliant and should be preserved. Only the destination needs to change.**

DeepSeek's tier position in Maggy — cheap flash tier, capable pro tier — can be filled by US-based or local models with comparable performance. The orchestration, the hook system, the memory layer, the skills — all of that stays intact. We just swap who gets the prompt.

### The Config Layer

A single file — `~/.maggy/routing.yaml` — controls everything:

```yaml
# Data sovereignty mode
sovereignty: us       # us | local | any

# Provider per tier
tiers:
  flash: groq         # simple code, boilerplate, tests
  pro: together       # multi-file features, refactors, debugging
```

Three sovereignty modes:

| Mode | What it means |
|------|--------------|
| `us` | US-based providers only. Blocks DeepSeek, Kimi, Moonshot. Uses Groq + Together AI. |
| `local` | Nothing leaves your machine. Ollama only. Air-gapped. |
| `any` | No restrictions. User's choice. DeepSeek remains available. |

The enforcement happens at **two layers** — both the Python config module and the bash hook that intercepts Claude Code prompts. You cannot accidentally route to a blocked provider. It falls back automatically.

### The US Stack

**Flash tier → [Groq](https://groq.com)**
- US company. Llama 3.3 70B.
- ~$0.05/M tokens — actually *cheaper* than DeepSeek Flash ($0.14/M).
- Fastest inference available anywhere. US data centers.

**Pro tier → [Together AI](https://together.ai)**
- US company. Llama 3.1 405B.
- ~$3.50/M tokens. Near Claude Sonnet quality for most coding tasks.
- US data centers.

**Local tier → [Ollama](https://ollama.com)**
- No API. Runs on your machine.
- `qwen2.5-coder:72b` — excellent coding model, ironically from Alibaba but run locally means zero data egress.
- Free. Private. Air-gapped.

### The European and Asian Option

For teams in Europe (GDPR constraints) or Asia (local compliance requirements), the `local` sovereignty mode with Ollama is the clean answer — no data leaves the machine, period. Alternatively, the config accepts any OpenAI-compatible endpoint, so teams can point the flash and pro tiers at:

- **EU:** Mistral API (French company, EU data residency), OVHcloud-hosted models
- **Asia:** Any regional provider running OpenAI-compatible endpoints — NIM on local infrastructure, private Together AI deployments, or simply Ollama with models pulled locally

The routing logic and hook system are provider-agnostic. The bin scripts (`bin/groq`, `bin/together`, `bin/ollama-coder`) follow a simple contract: accept a prompt, write a response to stdout. Adding a new regional provider is 30 lines of Python and one entry in `routing.yaml`.

### What Did Not Change

Everything that makes Maggy powerful:

- The 10-tier routing intelligence
- Mnemos memory system
- TDD enforcement via Stop hooks
- The 62 skills
- The plugin system
- The dashboard
- The competitor intelligence
- Claude at Tier 11 for architecture and security

The routing *destination* changed. The routing *intelligence* did not.

---

## The Cost Picture

Here is what the swap looks like financially:

| Setup | Daily cost (est. ~1M tokens) |
|-------|------------------------------|
| All Claude | $5–15 |
| Maggy with DeepSeek (original) | $0.50–1.50 |
| Maggy with Groq + Together AI (this PR) | $0.50–2.00 |
| Maggy with Ollama only | $0 |

The US-stack costs roughly the same as DeepSeek at the flash tier (Groq is actually cheaper) and modestly more at the pro tier (Together AI 405B vs DeepSeek Pro). The quality at the pro tier is comparable — Llama 3.1 405B is a serious model.

The delta is small. The principle is not.

---

## A Note on Appreciating What DeepSeek Built

Let us be direct: DeepSeek built something extraordinary. The V3 model punches above its weight class on almost every benchmark. The team released weights openly when they could have kept them proprietary. The price-performance ratio disrupted the market in ways that benefited everyone — it forced every major API provider to cut prices.

Americans are good at this: recognizing excellence wherever it comes from. We imported German engineering talent after World War II. We built the internet on protocols designed collaboratively across borders. We hired the best minds from every country and built great things together.

That tradition is worth preserving.

But appreciating technical excellence is not the same as being naive about the geopolitical context it operates in. Chinese engineers built DeepSeek. The Chinese state operates the legal environment DeepSeek must comply with. Those are two separate facts, and conflating them — either to dismiss the engineering or to ignore the legal reality — does a disservice to both.

The manufacturing outsourcing of the 1970s and 1980s was not driven by malice. It was driven by optimism, short-termism, and a failure to think in generational terms about what was actually being traded away.

We are in the early days of a technology that will restructure how intelligence is produced, distributed, and controlled. The data patterns of how software is built — what gets built, by whom, for what purpose, with what security assumptions — are themselves strategically valuable. Routing that data through infrastructure subject to Chinese state intelligence requirements is a choice. A choice that compounds quietly, at scale, over years.

We would rather not make that choice.

---

## How to Use This

**If you are already using Maggy:**

```bash
# 1. Pull the branch or wait for the PR to merge
git clone https://github.com/alinaqi/maggy.git

# 2. Copy the config template
cp templates/routing.yaml ~/.maggy/routing.yaml

# 3. Set your API keys
export GROQ_API_KEY="gsk_..."         # from console.groq.com
export TOGETHER_API_KEY="..."          # from api.together.xyz

# 4. For fully local (no keys needed):
#    Set sovereignty: local in routing.yaml
#    ollama pull qwen2.5-coder:72b

# 5. Run Maggy as normal
cd maggy && maggy serve
```

**Sovereignty presets in `~/.maggy/routing.yaml`:**

```yaml
# Full US stack
sovereignty: us
tiers: { flash: groq, pro: together }

# Fully local / air-gapped
sovereignty: local
tiers: { flash: ollama, pro: ollama }

# No restrictions (DeepSeek available)
sovereignty: any
tiers: { flash: groq, pro: deepseek }
```

The dashboard at `localhost:8080` exposes `GET/POST /api/routing/provider-config` so you can inspect and update your sovereignty settings without editing YAML.

---

## The PR

Everything described here is open and reviewable:

- **Original project:** https://github.com/alinaqi/maggy
- **Our fork:** https://github.com/sseshachala/maggy
- **Pull request:** https://github.com/alinaqi/maggy/pull/26

The implementation is 51 tests, 11 files, one clean commit. The routing intelligence is untouched. The sovereignty enforcement is additive.

If you are building software that matters, route it accordingly.

---

*Built with [Maggy](https://github.com/alinaqi/maggy) — we appreciate what Ali Naqi and the team built. This is a contribution in that spirit.*

*Questions, improvements, or regional provider additions welcome via PR.*
