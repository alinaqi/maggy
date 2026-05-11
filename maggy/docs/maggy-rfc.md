# Maggy: An Autonomous AI Engineering Platform

**RFC — Request for Comments**
**Author:** Ali Shaheen, Protaige
**Date:** May 2026
**Version:** 5.0

---

## 1. Executive Summary

Maggy is a local-first, self-improving AI engineering platform that transforms how development teams build software. Unlike code assistants that wait for prompts, Maggy is an autonomous agent that observes, learns, and optimizes — continuously improving its own effectiveness across models, workflows, and team knowledge.

**What makes Maggy different:**

- **Multi-model orchestration** — Maggy routes tasks to the best model (Claude, GPT-4o, Gemini, Kimi, DeepSeek, local Qwen) based on learned performance data, not static rules. When one model hits quota, work continues seamlessly on the next.
- **Self-improving closed-loop control** — Every task Maggy completes generates reward signals that improve its future decisions. Model routing, inbox ordering, workflow steps, and fatigue management all optimize automatically.
- **Process intelligence** — Maggy doesn't just write code. It learns from CI results, PR reviews, CodeRabbit findings, and merge patterns to preemptively fix issues before they reach reviewers.
- **Maggy Mesh** — A peer-to-peer network connecting Maggy instances across a team. One developer's hard-won CI fix becomes the entire team's knowledge. Autonomously. Instantly.
- **Local-first, no vendor lock-in** — All data stays on developer machines. No cloud dependency. No vendor seeing your code. Works offline with local models.

**The value proposition:** A team of 5 developers running Maggy Mesh for 6 months accumulates 4x the learning of a solo developer. New team members inherit collective intelligence on day one. CI pass rates go up, review rounds go down, and the system gets smarter every week — without anyone configuring it.

---

## 2. Vision: Autonomous Engineering, Not Code Generation

The current generation of AI coding tools — Copilot, Cursor, Devin — are fundamentally reactive. They complete code when prompted, suggest edits when asked, and run tasks when instructed. They're sophisticated typeaheads, not engineers.

An engineer doesn't just write code. An engineer:

- **Prioritizes** — Which ticket matters most right now?
- **Plans** — What's the blast radius? What could break?
- **Validates** — Does this feature align with the market? Do competitors have it?
- **Executes** — Write the code, with the right model for the task
- **Verifies** — Did CI pass? Did reviewers approve? Did it deploy cleanly?
- **Learns** — What worked? What didn't? How do I do it better next time?

Maggy does all of this. It's the first AI platform designed around the full software development lifecycle, not just the "write code" step.

### The Autonomy Spectrum

```
Level 0: Autocomplete (Copilot, TabNine)
  → Completes the current line
  → No context beyond the file
  → No learning

Level 1: Chat Assistant (ChatGPT, Claude)
  → Answers questions about code
  → No project context
  → No memory between sessions

Level 2: Project-Aware Assistant (Cursor, Continue)
  → Understands the codebase
  → Can edit multiple files
  → Limited memory (rules, preferences)

Level 3: Task Agent (Devin, Claude Code Agent)
  → Executes multi-step tasks
  → Uses tools (terminal, browser)
  → Single-model, single-project

Level 4: Autonomous Engineering Platform (Maggy) ← WE ARE HERE
  → Multi-model, multi-project orchestration
  → Self-improving from every task
  → Process intelligence (learns from CI, reviews, deploys)
  → Team intelligence via P2P mesh
  → Market validation before engineering
```

---

## 3. Architecture Overview

### The Component Map

```
┌─────────────────────────────────────────────────────────────┐
│                    MAGGY WEB DASHBOARD                        │
│  ┌──────────┐ ┌─────────┐ ┌────────┐ ┌───────┐ ┌────────┐ │
│  │  Inbox   │ │ Budget  │ │ Agents │ │  CIKG │ │Process │ │
│  │ (ranked) │ │ (live)  │ │(status)│ │ (gaps)│ │(health)│ │
│  └──────────┘ └─────────┘ └────────┘ └───────┘ └────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │    ORCHESTRATOR LAYER    │
              │                         │
              │  Pi Agent (universal    │
              │  harness, RPC mode)     │
              │                         │
              │  Token Budget Manager   │
              │  Model Router (learned) │
              │  Dual-Model Planner     │
              └────────┬────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
   │Container│   │Container│   │Container│
   │  1      │   │  2      │   │  3      │
   │ Claude  │   │ GPT-4o  │   │  Qwen   │
   │ (auth)  │   │ (front) │   │ (docs)  │
   └─────────┘   └─────────┘   └─────────┘
        │              │              │
   ┌────┴──────────────┴──────────────┴────┐
   │         INTELLIGENCE LAYER             │
   │                                        │
   │  iCPG — blast radius, drift, intent    │
   │  Mnemos — memory, fatigue, checkpoints │
   │  codebase-memory-mcp — code graph      │
   │  CIKG — competitive intelligence       │
   │  Process Intelligence — CI/PR/deploy   │
   │  MCP Forge — capability expansion      │
   │  Maggy Mesh — P2P team learning        │
   └────────────────────────────────────────┘
```

### Pi: The Universal Agent Harness

Pi replaces per-CLI adapters with a single interface to every model. It runs inside Polyphony containers in RPC mode over stdin/stdout. The same PiAdapter code controls Claude, GPT-4o, Gemini, Kimi, DeepSeek, or a local Qwen — with identical tool interfaces.

**Model fallback chain:**

```
Claude → GPT-4o → Gemini → Kimi → DeepSeek → Qwen (local, unlimited)
```

When a model hits quota or rate limits:
1. Mnemos writes a structured checkpoint (goal, constraints, progress, state)
2. Pi switches to the next model
3. The checkpoint is injected as context
4. The new model verifies it understands the task before continuing
5. If verification fails, escalate to the next tier — don't retry on a weaker model

**The user never notices the switch.** Work continues. That's the wow.

### Token Budget Manager

```yaml
providers:
  anthropic:
    daily_limit_usd: 50.00
    used_today_usd: 32.15
    model_preference: claude-sonnet-4
  openai:
    daily_limit_usd: 30.00
    used_today_usd: 5.20
    model_preference: gpt-4o
  local:
    daily_limit_usd: 0  # free
    model_preference: qwen2.5-coder:32b
```

The budget manager prevents runaway costs. When anthropic hits $50, Maggy doesn't stop — it routes to OpenAI. When OpenAI hits $30, it routes to local Qwen. Work never stops.

---

## 4. Self-Improvement: Multi-Level Closed-Loop Control

This is Maggy's core differentiator. Every task teaches Maggy something. Every CI failure, every review comment, every deploy result feeds back into the system. Maggy gets smarter every day — without anyone configuring it.

### The Objective Function

```
efficiency = (value_delivered / time_spent) x quality_multiplier

where:
  value_delivered   = tickets landed + features shipped + bugs fixed
  time_spent        = wall clock from ticket selection to merge
  quality_multiplier = 1.0 - (bug_escape_rate + revert_rate + incident_rate)
```

### Five Control Levels

| Level | Frequency | What It Does |
|-------|-----------|-------------|
| **L0 — Real-time** | Seconds | Catches tool failures, test failures, fatigue spikes, scope drift *as they happen*. Switches models mid-task when quality degrades. |
| **L1 — Task** | Minutes | Computes task reward score. Updates model performance table. Logs process signals. |
| **L2 — Daily** | Hours | Catches operational degradation: CI pass rate drops, model failure spikes, budget burn rate anomalies. Disables failing models. |
| **L3 — Weekly** | Days | Strategic optimization: evolves skill files, adjusts workflow steps, triggers MCP Forge for capability gaps, patches prompts. |
| **L4 — Monthly** | Weeks | Meta-optimization: recalibrates reward signals, adjusts tier boundaries, tunes exploration rate, changes the improvement process itself. |

**Key principle:** Inner loops provide stability. Outer loops provide optimization. L0 catches a failing model in seconds — the user barely notices. L3 makes routing smarter over weeks — the system quietly improves. L4 makes the improvement process itself better over months.

### What Gets Optimized

**Model routing** — Maggy tracks reward per `(model x task_type x blast_tier)` triple. After 50+ tasks, routing outperforms random assignment by 20%+.

```
(claude, auth, high):       +0.92  ← claude excels at auth
(qwen, docs, low):          +0.85  ← qwen is fast and free for docs
(gpt-4o, frontend, medium): +0.78  ← gpt-4o is strong on frontend
```

**Inbox ordering** — Learns which tickets the user actually picks first. Adjusts urgency weights to match user behavior.

**Workflow steps** — Drops steps that never catch issues (e.g., Codex counter-check on blast < 3). Re-enables them when they become valuable again.

**Fatigue management** — Learns each user's optimal session length and pre-checkpoints at the right moment. Not at a generic threshold — at *your* threshold.

---

## 5. Process Intelligence: Learning from the Full SDLC

Most AI tools optimize code generation. Maggy optimizes the **entire development process**.

### Environment Discovery

On first run per project, Maggy auto-discovers the developer's workflow — no configuration:

- **Ticketing:** GitHub Issues, Asana, Linear, Jira
- **CI/CD:** GitHub Actions, Jenkins, CircleCI
- **Code quality:** ESLint, ruff, mypy, pre-commit, coverage
- **Review process:** Required reviewers, CODEOWNERS, branch protection
- **Integrations:** CodeRabbit, Dependabot, Renovate, Vercel

### Signal Collection

Maggy continuously collects signals from the SDLC:

| Signal Source | What Maggy Learns |
|--------------|-------------------|
| CI results | Which code patterns cause test failures |
| PR review comments | What reviewers consistently flag |
| CodeRabbit findings | Security and quality issues by pattern |
| Merge patterns | How many rounds of review, time to merge |
| Deploy results | Which changes cause deploy failures |

### Preemptive Fixes

The pattern engine correlates `(code_pattern, review_feedback)` pairs:

> "Your reviewer always flags missing error handling in API routes. Maggy added it before the PR was created. Review rounds dropped from 2.8 to 1.1."

This is not prompt engineering. This is autonomous process optimization — Maggy observed a pattern, validated it statistically, and changed its behavior to prevent the issue. No human told it to.

---

## 6. Engram: Cross-Session Memory

### The Amnesia Problem

Every AI coding tool today is an amnesiac. When a session ends, everything the agent learned — project conventions, reviewer preferences, codebase idioms, tool configurations — evaporates. The next session starts from scratch. This isn't a minor inconvenience; it's the fundamental bottleneck preventing AI agents from becoming genuinely useful over time.

Engram identifies seven distinct amnesia pathologies:

| Amnesia Type | What Gets Lost | Impact |
|-------------|---------------|--------|
| **Anterograde** | New memories fail to form across sessions | Every session restarts from zero |
| **Retrograde** | Existing memories degrade over time | Learned patterns fade |
| **Temporal** | When something happened is lost | Can't track how things changed |
| **Source** | Where a fact came from is lost | Can't trust or audit memories |
| **Interference** | Memories from one context contaminate another | Project A's patterns leak into Project B |
| **Context-binding** | Right memory, wrong retrieval context | Conventions exist but aren't surfaced when needed |
| **Confabulation** | Inferred patterns presented as confirmed facts | Agent "remembers" things it actually guessed |

### The Memory Lifecycle

Engram completes Maggy's memory stack:

```
Mnemos (within-task)     → What the agent remembers during a single task
     ↓ promote (confidence > 0.8, evidence >= 3)
Engram (cross-session)   → What survives between sessions, per machine
     ↓ distill to typed memory
Mesh (cross-machine)     → What's shared across the team, P2P
```

Without Engram, Maggy has a 10-minute memory. With Engram, knowledge compounds across every session. After 100 sessions, Maggy knows your project's conventions, your reviewers' preferences, your CI failure patterns — and applies them automatically.

### Three-Tier Namespace Model

Memory is organized into three tiers to prevent both cross-project contamination and useful-pattern siloing:

1. **Local** — project-specific memories (strict isolation). A Python FastAPI project's conventions never contaminate a React project's patterns.
2. **Portfolio** — abstracted cross-project patterns. When a local pattern proves useful across 3+ projects, it's promoted — but only after de-contextualization (stripping project-specific names and paths).
3. **Mesh** — peer-derived memories (quarantined on arrival). Must be locally validated before promotion to portfolio.

This three-tier model means Engram gets smarter across projects without cross-contamination.

### Engram as Improvement Substrate

Engram absorbs the improvement ledger. The ledger is the mutation log (what changed), Engram is the memory substrate (persists it across sessions), and the reward registry tracks whether it worked. Every self-modification becomes a persistent, queryable memory — Maggy remembers not just what it learned, but what it tried and what failed.

### Amnesia Score

Each project gets a 7-dimension diagnostic score (0.0 = perfect retention, 1.0 = total amnesia). The L3 weekly loop analyzes Amnesia Scores and adjusts encoding rules: if anterograde score is high, lower the promotion threshold; if interference is high, tighten namespace isolation.

### Research Basis

Engram builds on validated research: Mem0 (186M API calls, memory-as-object model), Zep/Graphiti (temporal validity windows), Hindsight (91.4% on LongMemEval, fact vs opinion separation), MAGMA (multi-graph retrieval with 45.5% higher reasoning accuracy), and A-MEM (Zettelkasten-style associative encoding). What none of these systems address is the combination of namespace isolation, origin tracking, temporal validity, and amnesia diagnosis in a single architecture designed for multi-project AI agents.

---

## 7. Maggy Mesh: Peer-to-Peer Team Intelligence

### The Problem

A solo developer's Maggy learns from their tasks. But teams have 5, 10, 50 developers — each independently discovering the same CI fixes, the same reviewer preferences, the same model performance patterns. That's wasted learning.

### The Solution

Maggy Mesh connects instances across a team into a peer-to-peer network. Each Maggy autonomously shares learned intelligence with other Maggys in the same organization.

```
┌──────────────────────────────────────────────────────────┐
│                    ORGANIZATION                            │
│                                                           │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐              │
│  │ Maggy-A │◄──►│ Maggy-B │◄──►│ Maggy-C │              │
│  │ (Ali)   │    │ (Sarah) │    │ (John)  │              │
│  │ Python  │    │ React   │    │ DevOps  │              │
│  └─────────┘    └─────────┘    └─────────┘              │
│       ▲              ▲              ▲                    │
│       └──────────────┴──────────────┘                    │
│            Full mesh — everyone sees                      │
│            everyone's learnings                           │
└──────────────────────────────────────────────────────────┘
```

### What Gets Shared

Not everything. Maggy Mesh shares **typed memory classes** with different merge rules:

| Type | Example | Merge Rule |
|------|---------|-----------|
| **Scores** | "Claude scores 0.92 on auth tasks" | Weighted average by sample count |
| **Patterns** | "Add error handling before PR" | Union-merge with frequency tracking |
| **Policies** | "Route blast 7+ to premium only" | Backtest-gated — must pass on local data |
| **Gaps** | "No Linear integration" | Additive accumulation |

### Provenance

Every shared memory carries full provenance:

- **Who:** peer_id, peer_name
- **Where:** project_key, language, toolchain
- **When:** created_at, last_verified
- **How much:** evidence_count, confidence (decays with age)

This enables intelligent filtering: "Only accept Python patterns from peers working on Python projects."

### Quarantine System

Incoming peer data doesn't go live immediately. It enters quarantine:

1. **Self-confirmed:** Local data validates the pattern within 30 days
2. **Crowd-confirmed:** 3+ peers independently report the same pattern
3. **Human override:** Developer manually promotes or rejects

This prevents poisoning, stale data propagation, and context collapse. A bad pattern from one node can't silently corrupt the entire team.

### Cold Start

A new team member installs Maggy, discovers peers via mDNS, and receives the entire team's collective intelligence — quarantined until locally validated. Day one, they have the benefit of months of team learning.

### The Compound Effect

```
Individual Maggy:    knowledge = learning_rate x time
Team Mesh (n peers): knowledge = n x learning_rate x time x sharing_factor

5 developers, 6 months:
  Solo:  1 x 1.0 x 180 = 180 learning units
  Mesh:  5 x 1.0 x 180 x 0.8 = 720 learning units (4x multiplier)
```

The sharing_factor (0.8) accounts for context mismatch and quarantine filtering. The effect is superlinear because peers validate each other's patterns through crowd confirmation.

---

## 8. Lexon: Semantic Tool Binding

### The Tool Overload Problem

As Maggy's capabilities grow — MCP Forge auto-generates servers, Process Intelligence adds signal collectors, each project adds environment-specific tools — the tool count will cross 50, then 100. Research shows tool selection accuracy collapses at this scale: RAG-MCP demonstrated accuracy dropping from 87% to 13% as tools grew from 10 to 100.

A second failure mode persists even with retrieval: the **vocabulary gap**. Tool descriptions are written by engineers. Users speak in their own vocabulary. "I want to blast my leads" doesn't match `create_campaign` by any lexical metric. Maggy needs to learn that for *this user*, "blast" means bulk email send.

### Two-Tier Routing

Lexon solves this with a two-tier pipeline that runs in parallel:

1. **Tier A — Fast LLM Router** (<300ms): A compact tool manifest (name + 1-line description, ~400 tokens for 80 tools) fed to a fast model. Returns 5-7 candidates with rationale. JSON schema constrained to valid tool names — no hallucinated tools.

2. **Tier B — Multilingual Semantic Retriever**: Vector search over the full tool registry, indexed by description, example queries, and learned synonyms. Multilingual embedding model ensures queries in any language match correctly.

Candidates from both tiers are unioned and deduplicated. Each tier compensates for the other's failure mode: the LLM captures intent-level reasoning; the retriever captures lexical variants and multilingual matches.

### Terminology Map

A three-level vocabulary store that learns over time:

- **System level**: Built-in tool descriptions (baseline)
- **Org level**: Team-shared vocabulary, propagated via Mesh (e.g., "follow up" = specific CRM workflow)
- **User level**: Personal shortcuts and preferences (e.g., "morning sequence" = campaign with time=09:00)

Resolution: user overrides org overrides system. **NOT bindings** encode negative matches — "blast" is explicitly NOT "delete_all" — preventing recurring mis-selections.

### Dual-Mode Disambiguation

When confidence is ambiguous, Lexon has two resolution modes:

**Self-clarify (default, autonomous):** Lexon resolves ambiguity without asking the user by consulting iCPG's structured intent, Mnemos context, Engram's past bindings, process history, and Mesh consensus. If any source resolves confidence above threshold, proceed silently. The goal: 95%+ resolutions via self-clarify after 50+ interactions.

**User-clarify (irreversible actions only):** Triggered only for destructive, expensive, or irreversible actions (delete, deploy, billing changes). Presents 2-3 concrete options. The user's selection becomes a permanent binding.

Autonomous agents should almost never trigger user-clarify. This is what separates Maggy from tools that interrupt you constantly.

### Personalization

Five implicit learning signals update the Terminology Map without user effort:
1. **Correction** → add NOT binding + positive binding
2. **Affirmation** → increment confidence
3. **Repetition** (5+) → promote to high-confidence synonym
4. **Disambiguation selection** → capture as user-level binding
5. **Clarification repetition** (3+) → escalate to explicit preference prompt

High-confidence bindings persist via Engram across sessions and propagate to the org via Mesh.

### Tool Contract Binding

Lexon doesn't just bind phrases to tool names — it binds to tool contracts. Each LexonRecord records the tool version and schema hash at bind time. When a tool's API changes, Lexon detects the schema drift and re-evaluates bindings rather than silently calling a tool with a different interface. This matters because MCP Forge auto-generates tools from API docs that evolve.

### Outcome-Bearing Records

Every LexonRecord carries an outcome reward (-1.0 to 1.0): did the binding produce good results? Corrections are tracked with their source (user explicit, CI failure, review comment). This transforms Lexon from a static lookup table into a reward-bearing learning system that gets measurably better at tool selection over time.

### Research Basis

Lexon builds on: RAG-MCP (Anthropic, 2025 — retrieval-based tool selection), Tool2Vec (2024 — example queries as embedding targets), ToolTree (ICLR 2026 — MCTS-style tool planning), Tool-MVR (2025 — self-correction loops), and Gorilla (Berkeley, 2023 — fine-tuned tool LLMs). Lexon's contribution is the unified architecture combining retrieval, disambiguation, multilingual support, and adaptive personalization — no prior system addresses all four.

---

## 9. Event Spine: The Nervous System

### Why an Event Spine

Maggy's components — iCPG, Mnemos, Lexon, Engram, Process Intelligence, Mesh — each generate events in their own formats. Without a canonical event spine, correlating "user said X → Lexon bound tool Y → execution failed → memory Z was created → mutation W was proposed" requires stitching together six different log formats.

The Event Spine defines a single ordered event stream that every component writes to:

```
IntentEvent → BindingEvent → ExecutionEvent → MemoryEvent
                                                   ↓
MeshEvent ← MutationEvent ← OutcomeEvent ← PersistenceEvent
```

Eight typed events, each carrying a common header (event_id, task_id, project_id, agent_id, model_id, confidence, namespace, policy_version, reward_delta). This enables:

- **End-to-end tracing**: follow a task_id across all 8 event types
- **Reward attribution**: OutcomeEvent.reward propagates back to BindingEvent (was tool selection good?) and MutationEvent (was self-modification good?)
- **Replay debugging**: reproduce failures from the event stream without re-executing
- **Amnesia diagnosis**: compare MemoryEvent → PersistenceEvent conversion rate per project
- **Self-improvement validation**: MutationEvent + OutcomeEvent = evidence for whether L3/L4 changes helped

### The Positioning Statement

> Maggy understands intent through iCPG. Maggy survives task execution through Mnemos. Maggy chooses the right capability through Lexon. Maggy remembers consequences through Engram. Maggy evolves behavior through rewards. Maggy spreads successful mutations through Mesh.
>
> The Event Spine connects all six into a single typed, correlated, reward-bearing event stream. This is the nervous system of an autonomous engineering agent.

---

## 10. Competitive Landscape

The AI coding tool market has exploded into distinct categories. Understanding where Maggy fits — and where it doesn't compete — is critical for positioning.

### 10.1 Market Taxonomy

The landscape breaks into five categories, each with different value propositions:

```
┌─────────────────────────────────────────────────────────────────┐
│                   AI CODING TOOL TAXONOMY (2026)                  │
│                                                                  │
│  1. CLOUD AGENT PLATFORMS (autonomous, cloud-hosted)             │
│     Codex (OpenAI), Devin (Cognition), Copilot Cloud Agent      │
│     Claude Managed Agents                                        │
│                                                                  │
│  2. AI-NATIVE IDEs (editor-first, multi-model)                   │
│     Cursor, Windsurf (Codeium/Cognition)                         │
│                                                                  │
│  3. CLI AGENTS (terminal-first, model-agnostic)                  │
│     Claude Code, Codex CLI, Aider, OpenCode, Cline              │
│                                                                  │
│  4. APP BUILDERS (prompt-to-app, no-code/low-code)               │
│     Lovable, Bolt.new, Replit Agent, v0 (Vercel)                 │
│                                                                  │
│  5. AUTONOMOUS ENGINEERING PLATFORMS                             │
│     Maggy ← ONLY ENTRY                                           │
│     (self-improving + process intelligence + team mesh)          │
└─────────────────────────────────────────────────────────────────┘
```

Maggy is not competing with Lovable (app builders) or Cursor (IDE experience). Maggy competes on a different axis: **autonomous improvement over time**. The question isn't "which tool writes better code today?" — it's "which tool writes better code *next month* than it did *this month*?"

### 10.2 Cloud Agent Platforms

#### OpenAI Codex (Cloud)

Codex is OpenAI's cloud-hosted autonomous coding agent, launched May 2025. Each task runs in its own sandboxed cloud environment preloaded with your GitHub repository. It can write features, fix bugs, run tests, and submit PRs — all in parallel.

| Capability | Codex Cloud | Maggy |
|-----------|-------------|-------|
| Execution model | Cloud sandbox (internet disabled) | Local containers (full network) |
| Model | codex-1 (o3 variant), GPT-5.3-Codex | 6+ models, learned routing |
| Parallel tasks | Yes (multiple cloud sandboxes) | Yes (Polyphony containers) |
| Self-improvement | No | 5-level closed-loop control |
| Process intelligence | No | Full SDLC learning |
| Team learning | No cross-instance learning | Mesh (P2P, autonomous) |
| SWE-bench Verified | 85% (GPT-5.3-Codex) | Model-dependent (routes to best) |
| Cost | ChatGPT Pro/Enterprise subscription | Self-hosted, pay-per-model-use |
| Data privacy | Code sent to OpenAI cloud | Local-first, code stays on machine |
| Trigger automation | Codex Jobs (on GitHub push) | Process Intelligence (on any signal) |

**Codex's strength:** Cloud-native parallel execution with strong sandboxing. The upcoming Codex Jobs feature (automated triggers on git events) is compelling for CI/CD workflows.

**Maggy's edge:** Codex treats each task as independent — it doesn't learn from past tasks, doesn't track reviewer patterns, and doesn't share knowledge across team members. Maggy's L1-L4 control loops mean task #100 is handled significantly better than task #1.

#### Devin (Cognition)

Devin is an autonomous cloud-based AI software engineer. It reached $73M ARR by early 2026, with 67% of PRs merged autonomously. Cognition also acquired Windsurf for ~$250M.

| Capability | Devin | Maggy |
|-----------|-------|-------|
| Execution model | Cloud VM with browser | Local containers |
| Knowledge system | Playbooks + Knowledge docs (manual) | Dynamic typed memory (automatic) |
| Cross-instance learning | No — knowledge is per-org, manually curated | Yes — Mesh shares automatically |
| Multi-model | Limited | 6+ models with auto-routing |
| Self-improvement | Playbooks improve via manual updates | 5-level automatic control loops |
| Process intelligence | No | CI, reviews, deploys, merge patterns |
| Managed Devins | Yes (parallel orchestration) | Yes (Polyphony containers) |
| SWE-bench Verified | 45.8% (Devin 2.0, unassisted) | Model-dependent |
| Cost | $500/mo Teams, custom Enterprise | Self-hosted |
| Scheduling | Recurring/one-time scheduled sessions | Continuous background operation |

**Devin's strength:** Enterprise organization structure, admin controls, playbook management. The acquisition of Windsurf gives them an IDE play too.

**Maggy's edge:** Devin's knowledge system is manually curated — someone writes playbooks and knowledge docs. Maggy's intelligence is learned automatically from task outcomes. Devin doesn't share learnings across team members' instances; Maggy Mesh does this autonomously.

#### Claude Managed Agents

Anthropic's cloud agent platform, updated May 2026 with three significant features: dreaming, outcomes, and multi-agent orchestration.

| Capability | Claude Managed Agents | Maggy |
|-----------|----------------------|-------|
| Execution model | Secure cloud containers | Local containers |
| Dreaming | Yes — reviews past sessions, extracts patterns | Similar to L3/L4 loops |
| Memory | Per-agent + cross-agent via dreaming | Typed memory (scores, patterns, policies, gaps) |
| Multi-agent | Orchestration + webhooks | Polyphony containers + cross-agent delegation |
| Self-improvement | Dreaming (research preview) | 5-level closed-loop control (designed in) |
| Process intelligence | No | Full SDLC learning |
| Team learning | Cross-agent dreaming (same org) | Mesh (P2P, cross-machine) |
| Local execution | No (cloud only) | Yes (local-first) |

**Claude Managed Agents' strength:** Dreaming is the closest any competitor comes to Maggy's self-improvement concept. Harvey (legal AI) saw 6x task completion improvement after implementing dreaming. The cross-agent pattern extraction is genuinely novel.

**Maggy's edge:** Dreaming is cloud-only and Anthropic-locked. Maggy's control loops work locally, across any model, and share learnings across developer machines — not just across agent sessions in the cloud.

#### GitHub Copilot (Cloud Agent + Agent Mode)

Copilot evolved from autocomplete to a multi-layered platform: inline suggestions, chat, agent mode (IDE), and cloud agent (autonomous).

| Capability | Copilot | Maggy |
|-----------|---------|-------|
| Code completion | Best-in-class inline suggestions | Via Pi (any model) |
| Cloud agent | Yes — autonomous PRs from issues | Yes — local containers |
| Agent mode | IDE-integrated (VS Code, Visual Studio) | CLI + web dashboard |
| Custom agents | User-level + repo-level definitions | Skills + iCPG + Mnemos |
| Multi-model | Yes (GPT-4o, Claude, Gemini via settings) | Yes (6+ models, learned routing) |
| Security tools | Security Reviewer agent (beta) | iCPG drift detection |
| Self-improvement | No | 5-level closed-loop control |
| Process intelligence | No | Full SDLC learning |
| Team learning | Spaces (cloud-mediated, admin-controlled) | Mesh (P2P, autonomous) |
| Debugger agent | Yes (Visual Studio, runtime validation) | L0 real-time control |
| Ecosystem | GitHub-native (Issues, PRs, Actions) | GitHub API + any ticketing system |

**Copilot's strength:** Deepest IDE integration. The debugger agent validating fixes against runtime behavior is unique. GitHub ecosystem integration is unmatched. Custom agents with workspace awareness, MCP connections, and model selection are powerful.

**Maggy's edge:** Copilot doesn't learn from its mistakes. It doesn't track which model does best on which task type. It doesn't observe CI results to preemptively fix reviewer complaints. And Spaces is admin-curated knowledge — not automatically learned intelligence.

### 10.3 AI-Native IDEs

#### Cursor

Cursor is the leading AI-native IDE (~$100M+ ARR), a fork of VS Code with deep AI integration.

| Capability | Cursor | Maggy |
|-----------|--------|-------|
| IDE experience | Native (fork of VS Code) | CLI + web dashboard |
| Background agents | 8 parallel cloud agents | Polyphony local containers |
| Memories | Project-scoped, persisted across sessions | Typed memory with provenance |
| Rules | `.cursorrules`, project rules | Skills (`.md`), iCPG, Mnemos |
| Security review | Always-on PR security agents (beta) | iCPG constraints + drift |
| Team features | Centralized billing, usage analytics | Mesh (P2P intelligence sharing) |
| Model routing | Manual selection | Learned from reward data |
| Self-improvement | Memories (passive) | 5-level active control loops |
| Process intelligence | No | Full SDLC learning |
| Context management | Rules, skills, MCPs, subagents | Skills, iCPG, Mnemos, code graph |

**Cursor's strength:** UX polish, background agents at scale (8 parallel), and the always-on security review agents. The context usage breakdown (rules, skills, MCPs) shows mature observability.

**Maggy's edge:** Cursor's memories are passive ("remember this fact"). Maggy's memory is active — it observes outcomes and adjusts behavior. Cursor doesn't learn from CI failures, doesn't track reviewer patterns, and doesn't share intelligence P2P.

#### Windsurf (Codeium → Cognition)

Windsurf's Cascade agent plans and executes multi-file edits with a dedicated planning agent running in the background. Acquired by Cognition (Devin) for ~$250M in December 2025.

| Capability | Windsurf | Maggy |
|-----------|----------|-------|
| Agent | Cascade (plan + execute) | Multi-level control loops |
| Codemaps | AI-annotated visual code maps | codebase-memory-mcp graph |
| Built-in browser | Yes (web context for Cascade) | Process Intelligence API hooks |
| Self-improvement | No | 5-level closed-loop control |
| Cost | $15/mo Pro | Self-hosted |

### 10.4 CLI Agents

#### Claude Code

Anthropic's terminal-first coding agent. Runs locally, supports multi-agent orchestration via Task tool with teams.

| Capability | Claude Code | Maggy |
|-----------|-------------|-------|
| Multi-agent | Task tool, teams, SendMessage | Polyphony containers + Pi |
| Model | Claude only | 6+ models with auto-routing |
| IDE integration | VS Code, JetBrains, desktop app | CLI + web dashboard |
| Hooks | PreToolUse, PostToolUse, Stop | Skills + hooks + L0 real-time |
| Self-improvement | No | 5-level closed-loop control |
| MCP support | Native | Native + MCP Forge (auto-generate) |

**Note:** Maggy is *built on* Claude Code's infrastructure (skills, hooks, MCP). It extends Claude Code with self-improvement, multi-model routing, process intelligence, and team mesh.

#### Codex CLI (OpenAI)

Open-source (Apache-2.0), Rust-based terminal agent. 81K+ GitHub stars. Runs locally, authenticates via ChatGPT account or API key.

| Capability | Codex CLI | Maggy |
|-----------|-----------|-------|
| Open source | Yes (Apache-2.0, 81K stars) | Yes |
| Language | Rust (96.3%) | Python |
| Model | OpenAI models only | 6+ providers |
| Self-improvement | No | 5-level closed-loop control |
| Team learning | No | Mesh (P2P) |

#### Aider

Open-source CLI pair programmer. 39K+ GitHub stars, 4.1M+ installations. Model-agnostic with an architect/editor dual-model approach.

| Capability | Aider | Maggy |
|-----------|-------|-------|
| Open source | Yes (39K stars) | Yes |
| Multi-model | Yes (75+ providers) | Yes (6+ with auto-routing) |
| Architect mode | Dual-model: strong planner + cheap editor | Dual-model planning (Phase 6) |
| Git integration | Every edit = reviewable commit | iCPG + Polyphony branches |
| Auto-lint/test | Yes (on every change) | L0 real-time control |
| Self-improvement | No | 5-level closed-loop control |
| Team learning | No | Mesh (P2P) |

**Aider's strength:** The architect/editor mode is clever cost optimization — expensive model plans, cheap model executes. Maggy's Phase 6 dual-model planning is similar but adds conflict resolution and outcome tracking.

#### OpenCode

Was a Go-based CLI with TUI (Bubble Tea), 12K+ stars. **Archived September 2025**, now continued as "Crush" by the original author (Charm team). Supported 75+ LLM providers, SQLite session storage, LSP integration.

### 10.5 App Builders

These tools target a different audience (non-developers, designers, rapid prototyping) but are worth understanding as they represent the "opposite end" of the autonomy spectrum.

#### Lovable

Prompt-to-full-stack-app builder. 2.3M users, $100M ARR, $6.6B valuation (Series B, Dec 2025, backed by Nvidia/Salesforce).

| Capability | Lovable | Maggy |
|-----------|---------|-------|
| Target user | Non-developers, designers | Professional developers |
| Output | Full-stack app from prompt | Code changes to existing codebase |
| Stack | React + TypeScript + Supabase | Any stack |
| Agent mode | Autonomous development mode | Multi-level control loops |
| GitHub sync | Yes | Native (git-first) |
| Self-improvement | No | 5-level closed-loop control |

#### Bolt.new, Replit Agent, v0

- **Bolt.new** — Browser-based JS app generator. 1M+ websites generated in 5 months.
- **Replit Agent 4** (March 2026) — Handles auth, databases, parallel task execution, Design Mode, checkpoint rollback. Richest ecosystem (50+ languages).
- **v0** (Vercel) — Specializes in React components with Tailwind/shadcn/ui. Precision frontend generation.

These are complementary to Maggy, not competitive. A developer might use Lovable to prototype, then bring the codebase into Maggy for professional development with CI integration, code quality tracking, and team collaboration.

### 10.6 Summary Comparison Matrix

| Capability | Codex Cloud | Devin | Claude Managed | Copilot | Cursor | Claude Code | Aider | Maggy |
|-----------|------------|-------|---------------|---------|--------|-------------|-------|-------|
| **Self-improvement** | - | - | Dreaming (preview) | - | - | - | - | 5-level control |
| **Process intelligence** | - | - | - | - | - | - | - | Full SDLC |
| **Team learning** | - | - | Cross-agent dreaming | Spaces | Org memories | - | - | P2P Mesh |
| **Multi-model routing** | - | Limited | - | Manual | Manual | - | Manual | Learned |
| **Local-first** | - | - | - | - | Partial | Yes | Yes | Yes |
| **Cloud agents** | Yes | Yes | Yes | Yes | Yes | - | - | - |
| **IDE integration** | VS Code | Browser | - | Native | Native | VS Code | Terminal | Dashboard |
| **Open source** | CLI only | - | - | - | - | - | Yes | Yes |
| **Vendor lock-in** | OpenAI | Cognition | Anthropic | GitHub | Cursor | Anthropic | None | None |

### 10.7 Where Maggy Wins

1. **Self-improvement is the product** — No other tool has a formal multi-level control system. Claude's dreaming is the closest, but it's cloud-only and single-vendor.
2. **Process intelligence is unique** — Nobody else learns from CI results, reviewer comments, and merge patterns to preemptively fix code.
3. **Autonomous team learning** — Mesh shares typed, provenanced intelligence P2P without a central server. Everyone else's "team features" are admin-curated knowledge or cloud-mediated memory.
4. **Model-agnostic by design** — Not locked to any provider. Learns which model is best for which task type automatically.
5. **Local-first with no compromises** — Code never leaves developer machines. Works offline with local models. No vendor sees your proprietary codebase.

### 10.8 Where Competitors Win Today

- **Copilot:** Deepest IDE integration, GitHub ecosystem, largest user base
- **Cursor:** Best editor UX, background agents at scale, security review agents
- **Devin:** Enterprise controls, playbooks, $73M ARR proves market demand
- **Claude Managed Agents:** Dreaming is genuinely novel, cloud scalability
- **Codex Cloud:** Parallel cloud sandboxes, upcoming Codex Jobs automation
- **Lovable:** Prompt-to-app for non-developers, $6.6B validates the broader market
- **Aider:** Open-source community (39K stars), architect/editor cost optimization

---

## 11. Migration Roadmap

### Phase Dependencies

```
Phase 1: PiAdapter + Token Budget ──────────────────┐
    │                                                 │
    ├── Phase 2: Model Routing (blast→model)          │
    ├── Phase 3: Mnemos Multi-Model Fatigue           │
    ├── Phase 6: Dual-Model Planning                  │
    │                                                 │
Phase 4: CIKG Extract ────────────────┐               │
    │                                  │              │
    └───────────┬──────────────────────┘              │
                │                                     │
Phase 5: Maggy v2 Dashboard ◄─────────────────────────┘
    │
    ├── Phase 7: Vercel Deploy Containers (Docker)
    ├── Phase 8: Process Intelligence ──────┐
    ├── Phase 9: MCP Forge                  │
    │                                       │
    └── Phase 11: Maggy Mesh ◄──────────────┘
                                            │
Phase 10: Integration Testing ◄─────────────┘
                                            │
Phase 3 + Phase 5 ──► Phase 12: Engram ─────┘
                                    │
Phase 9 + Phase 12 ─► Phase 13: Lexon
                                    │
Phase 12 + Phase 13 ─► Phase 14: Event Spine
```

### Phase Summary

| Phase | What | Priority | Effort | Dependencies |
|-------|------|----------|--------|-------------|
| 1 | PiAdapter + token budget | P0 | Large | Pi installed |
| 2 | Model routing (blast→model) | P0 | Medium | Phase 1 + iCPG |
| 3 | Mnemos multi-model fatigue | P1 | Medium | Phase 1 |
| 4 | CIKG extraction | P1 | Medium | Supabase |
| 5 | Maggy v2 dashboard | P0 | Large | Phases 1-4 |
| 6 | Dual-model planning | P2 | Medium | Phase 1 |
| 7 | Vercel deploy containers | P2 | Medium | Docker |
| 8 | Process intelligence | P1 | Large | Phase 5 + GitHub API |
| 9 | MCP Forge | P2 | Large | Phase 5 |
| 10 | Integration testing + docs | P1 | Large | All phases |
| 11 | Maggy Mesh (P2P) | P2 | XL | Phase 5 + Phase 8 |
| 12 | Engram (cross-session memory) | P1 | Large | Phase 3 + Phase 5 |
| 13 | Lexon (semantic tool binding) | P2 | Large | Phase 9 + Phase 12 |
| 14 | Event Spine (canonical event flow) | P2 | Medium | Phase 12 + Phase 13 |

---

## 12. Research Foundations & Prior Art

Maggy's architecture draws from five distinct research streams. This isn't a tool assembled from hype — each component maps to validated research with production evidence.

### 12.1 Self-Evolving Agent Systems

The field of self-improving AI agents has exploded in 2025-2026. Papers mentioning "AI Agent" or "Agentic AI" in 2025 exceeded the total from 2020-2024 combined by more than twofold.

**Key papers and systems:**

- **SICA — Self-Improving Coding Agent (ICLR 2025 Workshop)** — An agent that autonomously edits its own codebase, climbing from 17% to 53% on SWE-bench Verified through self-modification. This validates Maggy's core thesis: agents that modify their own behavior based on outcomes dramatically outperform static agents. ([Paper](https://openreview.net/pdf?id=rShJCyLsOr))

- **Godel Agent (ACL 2025)** — Uses runtime monkey-patching with safety verification. The agent modifies both its task-solving policy and its own learning algorithm, guided by high-level objectives while formal invariant checking prevents unsafe changes. Maggy's L3/L4 control loops use a similar principle: change the improvement process itself, but with rollback safeguards.

- **SAGE — Skill Augmented GRPO (December 2025)** — Agents accumulate reusable function libraries across task chains, achieving 8.9% goal completion gains while reducing output tokens by 59%. This directly parallels Maggy's skill evolution in L3, where successful patterns get codified into reusable skills.

- **HyperAgents (2026)** — Makes the meta-level itself editable. Agents improve *how they improve*, discovering domain-general skills (memory management, prompt engineering, exploration strategies) that transfer across coding, mathematics, and scientific domains. Maggy's L4 monthly evolution loop is designed for exactly this: improving the improvement process.

- **SWE-RL (Meta, 2025)** — Uses self-play where agents alternate between bug injection and fixing roles, gaining +10.4 points on SWE-bench Verified without human-labeled data. This reinforcement-based approach validates Maggy's reward registry concept.

- **AlphaEvolve (Google DeepMind)** — Recovered 0.7% of Google's worldwide compute through automated algorithm optimization. This is the first evidence of hyperscale ROI from self-improving agents — validating that autonomous optimization can deliver measurable economic value.

**Maggy's position:** Maggy applies self-evolution at the *operational* level (routing, workflows, process patterns) rather than at the model-weight level. This is more practical for a local-first system — you don't need GPU clusters to improve model routing decisions based on task rewards.

### 12.2 Agent Memory Systems

Memory has emerged as the central bottleneck for autonomous agents. A comprehensive 2025-2026 survey ("Memory in the Age of AI Agents") offers a structured taxonomy of how memory is designed, implemented, and evaluated in modern LLM-based agents.

**Key developments:**

- **Mem0 (2025-2026)** — Dominates commercially with 186 million API calls quarterly. The graph-enhanced variant (Mem0g) builds a directed, labeled knowledge graph alongside the vector store. Maggy's typed memory system (scores, patterns, policies, gaps) is similarly structured but uses domain-specific merge rules rather than a general-purpose graph.

- **Collaborative Memory (2025)** — A framework for multi-user, multi-agent environments with asymmetric, time-evolving access controls. Maintains private memory (per-user) and shared memory (selectively shared). This directly validates Maggy Mesh's approach of personal memory + team memory with provenance-based filtering.

- **MAGMA: Multi-Graph Agentic Memory Architecture (2026)** — Uses multiple graph structures for different memory types. Parallels Maggy's typed memory classes where scores, patterns, and policies each have different storage and merge semantics.

- **SimpleMem (2025)** — Achieved 26.4% average F1 improvement over baselines with 30x token reduction. Demonstrates that structured memory management produces dramatically better results than naive context stuffing.

**Maggy's position:** Most memory systems are passive stores. Maggy's memory is active — the L1-L4 control loops continuously update, prune, and evolve stored knowledge based on outcomes. The Mesh adds a distributed dimension that no other agent memory system currently implements.

### 12.3 Federated & Distributed AI

- **Federated AI Agents** — Intelligent software systems that learn collaboratively across multiple devices while keeping data localized. This is the theoretical foundation for Maggy Mesh: share learned intelligence, not raw data.

- **Agentic Federated Learning (ICML 2025)** — Autonomous agents collaborate on distributed learning tasks, each contributing local expertise to a shared model. Maggy adapts this from model training to operational intelligence: instead of sharing gradients, Maggy shares typed memory (scores, patterns, policies) with provenance.

- **Multi-Agent Collaboration Surveys (ACM DEAI 2025)** — A unified taxonomy decomposing AI agents into Perception, Brain, Planning, Action, Tool Use, and Collaboration subsystems. Surveys show collaborative architectures outperform isolated agents by 30-60% on complex tasks. Gartner reported a 1,445% surge in multi-agent system inquiries from Q1 2024 to Q2 2025.

- **CRDT-inspired merge** — Conflict-free replicated data types allow distributed systems to merge state without coordination. Maggy uses type-specific merge rules (weighted average for scores, union for patterns, backtest-gated for policies) inspired by CRDT semantics.

### 12.4 Self-Improving Coding in Production

The research isn't just theoretical. Production deployments validate that self-improving agents deliver measurable value:

| System | Result | Relevance to Maggy |
|--------|--------|-------------------|
| **Meta's REA** | Doubled model accuracy; 3 engineers improved 8 models simultaneously | Multi-model optimization works at scale |
| **Cognition (Devin)** | $73M ARR, 67% of PRs merged autonomously | Market demand for autonomous engineering is real |
| **Harvey + Claude Dreaming** | 6x task completion improvement | Cross-session pattern extraction works |
| **Karpathy's autoresearch** | 630-line script, 700 experiments in 2 days, 20 optimizations, 11% efficiency gain | Automated experimentation finds real improvements |
| **AlphaEvolve** | 0.7% of Google's worldwide compute recovered | Self-improvement produces hyperscale ROI |

**Claude Managed Agents — Dreaming (May 2026):** Anthropic's most relevant competitive move. Dreaming is a scheduled process that reviews past agent sessions, extracts patterns, and curates memories so agents improve over time. It surfaces insights no single session could see: recurring mistakes, workflows that multiple agents converge on, and team-shared preferences. This is the closest any competitor comes to Maggy's L3/L4 control loops — but it's cloud-only, Anthropic-locked, and doesn't include process intelligence (CI/review/deploy learning).

### 12.5 Control Theory Foundations

- **Inner-outer loop control** — Industrial control systems use fast inner loops for stability and slow outer loops for optimization. Maggy's L0 (seconds) through L4 (months) hierarchy mirrors this established engineering pattern. The key insight: outer loops NEVER override inner loop stability. L3 can change routing policy, but L0 still catches in-task failures regardless.

- **Reinforcement learning from task outcomes** — Maggy's reward registry applies RLHF principles at the system level, using task outcomes (CI pass, review rounds, deploy success) and user behavior (overrides, re-dos, reverts) as reward signals. Unlike RLHF for model training, this operates at the operational level without any model fine-tuning.

### 12.6 Local-First Software

- **Local-first principles (Ink & Switch, 2019)** — Software that works offline, keeps data on user devices, and syncs peer-to-peer. Maggy's architecture is explicitly local-first: SQLite databases, local filesystem storage, optional P2P sync.

- **Privacy-first trend (2026)** — Multiple tools now emphasize data privacy. OpenCode stores no code or context data. Aider runs entirely locally. The market is moving toward local execution as enterprises grow wary of sending proprietary code to cloud services. Maggy was designed local-first from day one — this isn't a retrofit.

### 12.7 Market Context

The AI coding tool market is at an inflection point:

- **Gartner predicts 40% of enterprise apps will include task-specific AI agents by 2026**, up from less than 5% in 2025.
- **57% of organizations** report measurable impact from AI agents in software development (2025 industry survey).
- The explosion of coding CLIs (30+ tools in 2026) reflects a shift from IDE-native AI to terminal-first agents that understand codebases, git history, and development workflows.
- **SWE-bench scores** continue to climb: Claude Mythos Preview hits 93.9% on Verified, 77.8% on Pro. But raw coding ability is becoming commoditized. The differentiation is moving to *what surrounds the model*: memory, learning, process integration, and team collaboration.

**The implication for Maggy:** Raw code generation quality is converging across models. The next competitive frontier is *what happens around the generation*: learning from outcomes, optimizing processes, sharing intelligence across teams. This is exactly where Maggy's architecture is positioned.

---

## 13. How to Get Started

### Installation

```bash
git clone https://github.com/alinaqi/maggy.git
cd maggy
./install.sh
```

### Current State (v4.0)

Today, Maggy includes:
- **Skills system** — Markdown-based instructions for AI agents (TDD, security, iCPG, Mnemos, etc.)
- **Polyphony** — Container-isolated multi-agent orchestration (173 tests, 14 modules)
- **iCPG** — Intent-augmented code property graph with blast radius scoring
- **Mnemos** — Task-scoped memory lifecycle with typed MnemoGraph
- **Cross-agent delegation** — Complexity-based task routing to Codex, Kimi, etc.
- **Skill-lint** — Quality gates for skill files
- **Behavioral evals** — Test framework for skill effectiveness

### Roadmap to v5.0

The 14-phase migration path takes Maggy from a single-project, single-model toolkit to the multi-project, multi-model, self-improving, team-learning platform described in this RFC.

---

## Contact

**Ali Shaheen** — ali@protaige.com
**Protaige** — Building the future of autonomous AI engineering

---

*This document describes the Maggy v5 architecture as designed. Implementation follows the 11-phase migration path. For technical details, see `docs/architecture-v5.md`. For phase-level task specs, see `_project_specs/phases/`.*
