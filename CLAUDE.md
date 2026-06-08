# Global Claude Code Settings

## General Preferences

- Concise responses preferred
- Use TypeScript over JavaScript when possible
- Prefer functional programming patterns
- Write tests for new functionality

## Code Style

- 2 spaces for indentation (JS/TS)
- 4 spaces for Python
- Single quotes for strings (JS/TS)
- No trailing commas
- Meaningful variable names

## Git Workflow

- Write clear, concise commit messages
- One logical change per commit
- Run tests before committing

## Tools & Frameworks

- Package manager: npm (Node.js), pip (Python)
- Testing: Jest/Vitest (JS), pytest (Python)
- Linting: ESLint (JS), ruff/black (Python)

---

# Engineering Policy

## TDD — Non-Negotiable

ALWAYS write tests before implementation. No exceptions.

1. Read the requirement
2. Write failing tests that describe the expected behaviour
3. Run tests — confirm they fail for the right reason
4. Write the minimum implementation to pass
5. Refactor, keep tests green
6. Never write a function, class, or API endpoint without a corresponding test

If asked to add a feature without tests, write the tests first then ask to proceed.
If a PR diff shows untested code paths, flag them before continuing.

## Model Routing — Token Economy (13-Tier)

| Tier | Model | Cost (in/out per M) | Role |
|------|-------|---------------------|------|
| 0 | Qwen3 (local) | $0 | File reads, quick edits, boilerplate, offline |
| 1 | Gemini 2.5 Flash-Lite | $0.10 / $0.40 | Bulk extraction, classification, CIG pipelines |
| 2 | DeepSeek V4 Flash | $0.14 / $0.28 | Sub-agents, cheap internal calls |
| 3 | Gemini 2.5 Flash | $0.15 / $0.60 | Multimodal, video analysis, brand assets |
| 4 | DeepSeek V4 Pro | $0.435 / $0.87 | Main coding workhorse — ~80% of work |
| 5 | Gemini CLI (coding agent) | ~$0.25-1.25 / M | Agentic coding, multi-file impl, Google tier |
| 6 | AGY / Antigravity (Google) | Google tier | Terminal coding agent, end-to-end impl |
| 7 | Kimi K2.6 | $0.60 / $2.50 | Long agentic loops, routing alt |
| 8 | Gemini 3.1 Pro + Search | $1.25 / $10 | Deep research, Google grounding, 2M context |
| 9 | Grok 4.3 (xAI) | $5 / $15 | Competitor intel, CKG, deep reasoning |
| 10 | Codex | varies | Code review, bulk generation |
| 11 | Claude Sonnet/Opus | $3-5 / $15-25 | Quality-critical, security, architecture |

### Use qwen3 (local) for:
- grep, find, awk, sed, jq questions
- Shell one-liners and regex
- Quick syntax lookups, log reading, file search

Invoke: qwen3 ""

### Use Gemini Flash-Lite (Tier 1) for:
- Bulk extraction and classification pipelines
- Cheap summarization, CIG data processing
- Non-code batch tasks (cheapest model at $0.10/M)

Invoke: gemini --flash-lite ""

### Use DeepSeek Flash (Tier 2) for:
- Simple code tasks, boilerplate, CRUD, config changes
- Single-file additions, small bug fixes

Invoke: deepseek --flash ""

### Use DeepSeek Pro (Tier 4) for:
- Multi-file features and refactors
- Debugging, API endpoints, test suites
- Documentation writing — main coding workhorse

Invoke: deepseek --pro ""

### Use Gemini Flash (Tier 5) for:
- Multimodal tasks (image screenshots, brand assets)
- Video content processing and analysis
- Audio transcription review

Invoke: gemini --flash ""

### Use Gemini CLI (Tier 5) for:
- Agentic coding tasks with file read/write
- Multi-file implementation within Google ecosystem
- Alternative coding agent for medium-complexity work

Invoke: gemini-cli --pro ""

### Use AGY / Antigravity (Tier 6) for:
- End-to-end implementation (git operations, file edits, testing)
- Terminal coding agent tasks (Google's coding agent)
- Multi-step implementation with autonomous execution

Invoke: agy-delegate --print ""
Invoke (headless): agy-delegate --headless ""

### Use kimi (Tier 7) for:
- Commit messages, changelogs, diff summaries
- Research questions needing reasoning
- Quick single-model analysis

Invoke: kimi ""

### Multi-Model Review
For architecture/code reviews, run DeepSeek + Kimi + Codex in parallel instead of single-model:
```bash
~/bin/review --all "review this implementation"
~/bin/review --deepseek --kimi "architecture review of auth module"
```
- Agree/disagree analysis across all three reviewers
- Estimated cost: ~$0.02 per review (vs $3-5 for Claude solo)
- Review log: `~/.claude/review-log.jsonl`

### Use Gemini Pro Search (Tier 7) for:
- Deep research with native Google Search grounding
- Competitor intelligence and market research
- 2M context document analysis

Invoke: gemini --pro-search ""

### Use Grok (Tier 9) for:
- Competitor intelligence and CKG building
- Deep reasoning and market analysis
- Truthful, insightful research

Invoke: grok ""

### Use Codex (Tier 10) for:
- Large-scale boilerplate or test generation
- Mechanical changes across many files
- Code review (codex-review)

### Use Claude (Tier 11) for:
- Architecture and system design
- Security-critical code
- Complex debugging, multi-service refactors
- Customer-facing quality-critical code

## Autonomous Plan → Validate → Execute

When a task requires planning (CLAUDE tier), the full cycle is automated:

```
Goal detected → Enter plan mode → Write plan to ~/.claude/plans/
    ↓
~/bin/validate-plan --threshold 2 <plan-file>
    ↓ (DeepSeek Pro + Codex + Gemini Pro vote in parallel)
2+ APPROVED → Auto-approve → Execute immediately
1 APPROVED → Surface to user with reviewer feedback
0 APPROVED → Revise plan, re-validate
```

**Goal detection:** The route-task-hook classifies tasks. CLAUDE tier (architecture, security, complex system design) → PLAN FIRST. DEEPSEEK_PRO/GEMINI_CLI (features, refactors) → EXECUTE DIRECTLY.

**Multi-model validation:** After writing a plan, run `~/bin/validate-plan` which sends the plan to DeepSeek Pro, Codex, and Gemini Pro in parallel. Each evaluates approach completeness, edge cases, scope, and safety. Need 2+ approvals to auto-execute.

**Approval thresholds:**
- 3/3 approved → execute silently
- 2/3 approved → execute with minority feedback noted
- 1/3 approved → surface to user, show reviewer critiques
- 0/3 approved → revise plan, re-validate

## PR Workflow — Required Steps

Before any PR is considered done:
1. All tests pass locally
2. Run: pr-review [base-branch]
3. Fix all issues flagged by CodeRabbit and Codex review
4. Confirm test coverage includes the new code paths
5. Write a clear PR description: what, why, how

## Routing heuristic:
- Lookup / one-liner → qwen3
- Bulk extraction / classification → Gemini Flash-Lite
- Simple code / boilerplate → DeepSeek Flash
- Multimodal / video / images → Gemini Flash
- Features / refactors / debugging → DeepSeek Pro
- Agentic coding / multi-file impl → Gemini CLI
- End-to-end impl / git+code+test → AGY (Antigravity)
- Review / reasoning → kimi
- Deep research / Google grounding → Gemini Pro Search
- Competitor intel / deep reasoning → Grok
- Bulk generation → Codex
- Architecture / security / quality-critical → Claude
- Before PR → pr-review script

DeepSeek handles ~80% of coding work. Gemini CLI and AGY handle agentic implementation. Gemini fills multimodal, research, and bulk extraction gaps. Reserve Claude for quality-critical tasks.

## Tool Fallback Protocol

When built-in tools (WebSearch, WebFetch) return errors or empty results, retry with external backends:

| Failed Tool | Fallback 1 | Fallback 2 |
|-------------|------------|------------|
| WebSearch / WebFetch | `~/bin/research "query"` | `~/bin/deepseek --pro "query"` |
| Read / file access | `cat` via Bash | — |
| Grep | `grep -r` via Bash | — |

### Research Tool (`~/bin/research`)
Multi-backend research with auto-evaluation:
- Tries deepseek-flash → deepseek-pro in sequence
- Scores results on 0-10 scale (content quality, structure, length)
- Auto-adjusts preferred backend based on evaluation scores
- When WebSearch fails: run `~/bin/research "your search query"`
- Evaluation stats: `~/bin/research --eval`
- Score log: `~/.claude/research-eval.jsonl`

## Followed Model & Pre-Analysis (hook signals)

The route-task hook injects two signals into every prompt — act on them:
- **`FOLLOWED MODEL: <name>`** — the user's chosen primary model (`/model-config`). For substantial coding, prefer delegating to it.
- **`MINIMAX PRE-ANALYSIS: ...`** — a terse INTENT / SCOPE / RISKS / APPROACH brief. Use it to execute directly instead of re-deriving the task.

The choice lives in `~/.claude/model-config.json` (`primary`, `classifier`, `mode`, `analyze`) and is shared by the hooks, Maggy, and srooter. See [GETTING_STARTED.md](GETTING_STARTED.md) for setup.
