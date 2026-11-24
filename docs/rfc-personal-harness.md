# RFC: Personal Harness + Software Factory for Maggy (v2)

Status: draft v2 · 2026-11-23 · Inputs: "How to build your own software factory" (Palgu), full code review of `maggy/`,
AWG spec v1.2 (`~/Documents/AWG/docs`).

## Decisions (2026-11-23)

| # | Decision |
|---|---|
| D1 | **AWG is the controller.** Work state, dependencies, leases/fencing, attempts, evidence, completion contracts and human waits live in AWG. Maggy keeps no run database of its own. |
| D2 | **Solo developers only.** AWG Local (SQLite, `awg init`, no account), worktree isolation, one machine. No Postgres, teams or multi-tenant concerns. Cloud migration remains AWG's existing `awg cloud migrate`, not Maggy's problem. |
| D3 | **Must-have agents: Claude Code, Codex, OpenCode, pi, T3 Code.** |
| D4 | **Duplicate paths are removed at the end**, once the new paths are in place and tested (Phase 6). Until then legacy code is left alone except for safety fixes. |

## 0. TL;DR

Maggy becomes three things on top of AWG:

1. **Harness Profile:** one layered YAML that declares *your* harness (agents, models, rules, skills, hooks,
   permissions, gates, budget, tracker). Personal (`~/.maggy/harness.yaml`) → repo (`.maggy/harness.yaml`, policy keys lockable).
2. **Harness Compiler:** per-agent emitters that render the profile into native config for Claude Code, Codex,
   OpenCode and pi, **including AWG wiring** (MCP/extension + skill + `AGENTS.md` section), so every agent you use
   interactively follows the same rules and the same task ledger. T3 Code drives those agents, so it inherits their
   config (to be verified in a spike, see §2.2).
3. **Runner:** a headless worker loop. It claims work from AWG, runs a stage through a uniform worker interface on any
   of the four CLIs, computes results and evidence itself, attaches them to AWG as trusted tool output, and submits.

Design rule: **agent hooks are a convenience; AWG + the runner are the enforcement.** AWG already treats hooks as
advisory (AGENT_INTEGRATIONS.md: "critical task state must remain server-driven"). Gates that matter (tests, lint,
per-criterion evidence, budget) are re-run by the runner against the candidate commit, so behaviour is identical
whichever agent wrote the code.

---

## 1. Review of the current codebase (summary)

Full findings with file:line references are in Appendix A. Headlines:

- **Execution is fragmented and unsafe by default.** Six separate code paths launch agent CLIs, each with its own argv
  and output parsing. There is no common input/output contract. `cli_discovery.py:125-128` adds
  `--dangerously-skip-permissions` / `--dangerously-bypass-approvals-and-sandbox` / `--yolo` to host runs. "Container"
  isolation is a worktree. Budgets are recorded, never enforced.
- **No durable state.** Runs live in dicts. About 15 SQLite files share no run key. There are four orchestrators,
  three intake paths, three Mnemos copies and two intent stores. **AWG replaces this whole layer (D1).**
- **Work-losing bugs in live code:**
  - parallel mode deletes the workspace while the team is still running (`executor.py:101-110,263-272`);
  - subtask workspaces are deleted without merging (`services/orchestrator.py:166-172`);
  - `merge.py` uses `HEAD@{1}..HEAD`, so uncommitted edits are dropped.
- **The harness is Claude-centric.**
  - `install.sh` replaces `~/.claude/skills` and `~/.claude/rules` with `rm -rf`, and writes `.bootstrap-dir`
    before the `mkdir` that creates its directory.
  - Codex and Kimi get unwired templates; nothing exists for OpenCode, pi or T3.
  - The repo `CLAUDE.md` ships one user's personal tier table as a product default.
- **Stubs:** `planning.py`, `deploy.py`, `contracts/generator.py`, `council/` (dead).
  - Nothing stores acceptance criteria; nothing posts per-criterion evidence.
- **Security:**
  - Telos and e2e-testkit routes are unauthenticated, and `/api/telos/status` runs pytest in any directory passed to it.
  - `review/pipeline.py:262-306` hardcodes one client's repository paths.
- **Strong, keep:**
  - PR review council (`review/`), `DualPlanner`, worktree isolation, path sandbox, learned routing.
  - `process/` PR/CI signals and `history/` session-log parsers (Claude/Codex/Kimi).
  - `maggy diff/backup/restore`, the dashboard and the plugin system.
- **Tests:** 2202 pass / 52 fail. CI does not run the Maggy suite.

---

## 2. Target architecture

```
        ~/.maggy/harness.yaml  +  <repo>/.maggy/harness.yaml  (locked policy keys)
                                  │
                ┌─────────────────┴──────────────────┐
                ▼                                    ▼
      Harness Compiler                         Runner (maggy run)
      emitters → native config                 claim → stage → evidence → submit
                │                                    │            ▲
   ┌──────┬─────┴───┬────────┐            Worker interface        │
   ▼      ▼         ▼        ▼            (YAML adapters)          │
 Claude  Codex  OpenCode    pi    ◀── same CLIs, headless ──┘      │
   ▲      ▲         ▲        ▲                                     │
   └──────┴── T3 Code drives these interactively                   │
                                                                   │
            every agent ──(MCP / pi extension)──▶  AWG Local  ◀────┘
                                                  (~/.awg/awg.db)
                                                   ▲
                                        awg sync ◀─┘ GitHub Issues
```

### 2.1 Harness Profile

Pydantic schema with layering. Precedence: repo-locked > personal > repo-unlocked > shipped defaults.
`harness show` prints the resolved profile with the source of each key.

```yaml
# ~/.maggy/harness.yaml
version: 1
agents:
  installed: [claude, codex, opencode, pi]      # detected by `harness init`
  default: claude
  prefer: { review: codex, bulk: opencode }
surfaces: [t3]                                   # interactive front-ends that drive the agents above
models:
  strategy: cost                                 # cost | quality | speed | custom
  tiers: { cheap: deepseek-flash, main: deepseek-pro, premium: claude-opus }
instructions:                                    # rendered into AGENTS.md / CLAUDE.md managed block
  include: [rules/tdd.md, rules/quality-gates.md, rules/security.md]
skills: [python, typescript, react-web]
hooks:                                           # abstract events → native hooks where supported
  after_edit: [lint-changed]
  before_stop: [run-focused-tests]
  session_start: [load-memory]
permissions:
  profiles:
    read_only: { write: false, network: false }
    workspace: { write: workspace, network: registries, shell: allowlist }
gates: { tdd: required, coverage_min: 0.8, quality: { max_function_lines: 20, max_file_lines: 200 } }
work: { provider: awg, project: auto }           # awg project bound per repo
budget: { per_run_usd: 3, per_day_usd: 25 }
```

```yaml
# <repo>/.maggy/harness.yaml  (checked in)
commands: { install: npm ci, test: npm test, lint: npm run lint, e2e: npx playwright test }
intake: { source: github, label: factory, status: open }
worker: { adapter: codex, permission: workspace, timeout_minutes: 30 }
risk:
  high: { paths: [db/migrations/**, src/auth/**, src/payments/**], require: plan_approval }
  low:  { paths: [src/ui/**], autonomy: draft_pr }
validation: { required: [lint, test], visual_for: [ui] }
locked: [validation, risk]
```

CLI: `maggy harness init` (detect CLIs, short interview, write profile, `awg init` if missing) · `show` · `doctor`
(per-agent capability report: what is native, what falls back to runner enforcement) · `diff` · `apply [--agent X]`.

### 2.2 Harness Compiler: emitters

```python
class Emitter(Protocol):
    agent: str
    def capabilities(self) -> Capabilities: ...                       # hooks, skills, mcp, permission model
    def plan(self, profile: Profile, scope: Scope) -> list[FileChange]: ...   # pure, unit-testable, diffable
```

`apply` runs `plan`, shows the diff, backs up via the existing `maggy backup`, then writes. Text files get
**managed blocks** (`<!-- maggy:begin -->…<!-- maggy:end -->`); JSON and TOML get **managed keys**, merged without touching
user keys. This replaces `install.sh`'s `rm -rf` copying.
**Conflicts:**
- `~/.maggy/harness.lock` stores the hash of every managed block and key that Maggy last wrote.
- If the file on disk differs (the user edited inside a managed region), `apply` skips that file and shows a three-way
  diff (last written, on disk, profile). The user resolves it with `--take-mine` or `--take-profile`.
- Content outside managed regions is never touched.

`AGENTS.md` is the single shared instruction source. Claude gets `CLAUDE.md` containing `@AGENTS.md`.

| | Claude Code | Codex | OpenCode | pi | T3 Code |
|---|---|---|---|---|---|
| Instructions | `CLAUDE.md` → `@AGENTS.md` | `AGENTS.md` | `AGENTS.md` + `instructions` in `opencode.json` | `AGENTS.md` (also discovers `CLAUDE.md`) | inherits from driven agent |
| Skills | `.claude/skills/` | `~/.codex/skills/` | `.opencode/skills/` or `skills` key | `.agents/skills`, or via extension `resources_discover`; `/skill:name` | inherits |
| Hooks | `settings.json` hooks (full) | none, so runner enforces | plugins (`plugins` key) | TS extensions in `~/.pi/agent/extensions/`, `.pi/extensions/`: `tool_call` (can block), `tool_result`, `session_start`, `agent_end`, `session_before_compact`… | inherits |
| Permissions | `settings.json` allow/deny | `--sandbox read-only / workspace-write` | `permissions` rules in `opencode.json` | `--tools` / `--exclude-tools` allowlist + `tool_call` blocking | inherits |
| AWG wiring | existing AWG Claude plugin (`/plugin install awg`) | existing AWG Codex package: `awg mcp` in `config.toml` + skill + `AGENTS.md` section | **new:** `mcp.servers.awg = {type: local, command: [awg, mcp]}` + skill + plugin for heartbeat/todo mirroring | **new:** pi extension, using `pi.registerMcpServer` for `awg mcp` or tools wrapping the `awg` CLI; heartbeat on `turn_end` | via driven agent's MCP |
| Headless worker | `claude -p --output-format json` | `codex exec --json --sandbox …` | `opencode run --format json` | `pi -p --mode json` (or `--mode rpc`) | no; surface only (see spike) |

Notes:
- The OpenCode and pi details come from their current docs (opencode.ai/docs/config, pi-mono `docs/cli.md` and
  `docs/extensions.md`). Each emitter pins a tested CLI version and `harness doctor` warns on drift.
  OpenCode's permission format in particular should be re-checked against an installed binary.
- The new AWG integrations for OpenCode and pi belong **in the AWG repo** (`plugins/opencode`, `plugins/pi`), next to
  the existing `plugins/claude-code` and `plugins/codex`. The Maggy emitters install them.
- **T3 Code spike: done 2026-11-23, outcome A (T3 inherits native config).** From the T3 source:
  - Codex runs via `app-server`; thread metadata lists `instructionSources: [~/.codex/AGENTS.md, <repo>/AGENTS.md]`.
  - Claude runs via the Agent SDK with `settingSources: ["user","project","local"]`, or only `["project","local"]`
    when a T3 profile uses a custom home (`ClaudeAdapterV2.ts:5989`).
  - pi runs as `pi --mode rpc` with normal context files and extensions, and T3 adds its own extension. Extensions
    are turned off only for T3's short text-generation calls (`provider-pi/src/server/mcpInjection.ts`).
  - OpenCode runs as `opencode serve`, which loads `opencode.json`.
  - So Maggy emits nothing T3-specific. `harness doctor` advises project-scope emission for T3 Claude profiles with a
    custom home, and notes that T3 injects its own MCP server per thread.
- pi and OpenCode have real hook systems, so they can match the Claude plugin's automatic AWG heartbeat and todo
  mirroring. Codex cannot, which is already documented in AWG.

### 2.3 Worker interface

```python
class WorkerSpec(BaseModel):
    awg_ref: str; attempt_id: str; fencing_token: str     # from AWG claim
    stage: Stage; repo: Path; base_commit: str; spec_version: int
    workspace: Path; permission: str; deadline_s: int; budget_usd: float
    prompt: str                       # assembled by runner from the AWG context bundle; ticket text is data

class WorkerResult(BaseModel):
    outcome: Literal['succeeded', 'failed', 'blocked', 'timeout', 'budget_exceeded']
    candidate_commit: str | None; changed_files: list[str]     # computed by the runner from git
    checks: list[CheckResult]                                  # runner runs repo commands itself
    artifacts: list[str]; blocker: Blocker | None              # {question, options}
    cost_usd: float; elapsed_s: float; agent: str; model: str; adapter_version: str
```

Adapters are data in `maggy/adapters/*.yaml`, and users can override them in `~/.maggy/adapters/`:

```yaml
name: pi
detect: pi --version
argv: [pi, -p, --mode, json, --no-session, '{model_flags}', '{permission_flags}', '{prompt}']
cwd: '{workspace}'
permissions:
  read_only: [--tools, 'read,grep,find,ls']
  workspace: []                     # defaults; blocking enforced by the maggy pi extension
output: pi-jsonl                    # parsers: claude-json | codex-jsonl | opencode-json | pi-jsonl | text
instruction_file: AGENTS.md
quota_patterns: ['rate limit', '429']
```

Every exact flag in the shipped adapters gets a contract test against a recorded fixture of that CLI's output.

Isolation for solo developers:
- Default is one git worktree per attempt, on a stable branch `maggy/<awg-id>`.
- Agent env is scrubbed to an allowlist; the runner keeps the full environment.
- Permission profiles map to native flags. `--dangerously-skip-permissions` and `--yolo` are only allowed when the user
  opts in with `isolation: container`, and container isolation is deferred.

### 2.4 Runner on AWG

AWG primitives map onto the factory stages:

| Factory concept | AWG primitive |
|---|---|
| Ticket | `awg sync` pulls GitHub issues into an INTENT plus a parent WORK item |
| Acceptance criteria | `acceptance_criteria` on the WORK item, plus REQUIREMENT nodes (one per criterion) |
| Spec version | WORK `version`; approval recorded as a DECISION node (`SUPERSEDES` for later versions) |
| Spec review | CHECK work item, claimed by a fresh session; needs-clarification → `WAITING_HUMAN` + comment with the question |
| Plan | child TASKs with `DEPENDS_ON`; `awg lanes` for parallel-safe ordering |
| Test plan | VALIDATION nodes per criterion, linked by `REQUIRES_VALIDATION`, created *before* the build task is READY |
| Run / attempt / lease | AWG claim (attempt id + fencing token + lease) with runner heartbeats |
| Evidence | `evidence.attach` with `commit_sha`, kind and verdict; AWG marks it STALE when the commit changes |
| Gate | AWG completion contract: DONE only when required validations PASS |
| Needs input / blocked | `WAITING_HUMAN` / `BLOCKED` |
| PR | annotation on the WORK item; idempotent through the stable branch name plus a lookup of the existing PR |
| Metrics | AWG attempts and events (Ready→Done time, attempts per item, cost per item, first-pass pass rate) |

Runner loop (`maggy run [--once] [--project KEY]`):

```
awg next --claim (filtered to stages Maggy can run)
→ re-check item version and repo policy
→ create worktree at base_commit
→ build WorkerSpec from the context bundle → adapter → WorkerResult
→ runner runs required checks itself → attach evidence (commit-bound)
→ advance: create the next-stage items or submit; on blocker → WAITING_HUMAN with the question
→ heartbeat throughout; verify the fencing token before every side effect (merge, push, PR, comment)
```

**Trust (resolved from AWG code):**
- AWG tokens have kinds with fixed trust (`awg/service/tokens.py:21-26`): `agent` → AGENT_ARTIFACT (1), `reviewer` →
  TOOL_OUTPUT (2), `ci` → CI (3), `owner`/`human` → HUMAN_APPROVAL (4). The claimed trust is capped at the credential's
  (`evidence.py:49`). Default validations require TOOL_OUTPUT for acceptance criteria and CI for tests
  (`policy.py:59`, `workspaces.py:14`).
- **Gap:** AWG Local mints one `owner` token at `awg init` (`cli/local.py:28`), and `awg mcp` uses it for every agent.
  So an interactive agent can attach evidence at human-approval trust today.
- **AWG prerequisite (Phase 0):** `awg mcp` and the CLI accept a scoped token (`AWG_TOKEN` env or
  `--token-file`).
- Emitters mint one `agent`-kind token per agent CLI for interactive use.
- The runner holds an `agent` token (claim, heartbeat, submit) and a separate `ci` token (evidence only).
- Worker sessions get **no** AWG credential.

**Stage routing:** AWG already filters by capability. `execution_policy.capabilities` on the item, plus
`next --capabilities` (`scheduler.py:38`). Runner-executable items carry `[maggy-runner, stage:<name>]`; DECISION
items carry `[human]`, so the runner never claims them.

**Spec versioning (decided):**
- The spec is the WORK item's `acceptance_criteria` plus REQUIREMENT nodes, and its version is the WORK `version`.
  `awg update` on the criteria bumps it.
- Evidence metadata records `spec_version`. The runner treats a mismatch as STALE and sends the item back to spec review.

**Crash recovery and side effects:**
- Before any external action (push, PR, comment), the runner records an intent annotation on the item with an
  idempotency key, then performs the action, then records the result.
- On startup it reconciles held or expired items: it finds the branch and PR by their stable name and either
  completes or rolls forward.
- A failed or interrupted attempt keeps its worktree and branch and writes an AWG handoff, so the next attempt resumes
  from the branch instead of starting over.

### 2.5 Stages (solo scope)

| Stage | Implementation (reuse) | Gate |
|---|---|---|
| Spec | planner prompt with read-only permission + criteria template; reviewer in a fresh session (`council/deliberation` logic) | verdict `ready` / `needs_clarification` / `blocked` |
| Plan + test plan | `DualPlanner`, rewritten to structured output: tasks, deps, per-criterion fixture/action/expected/evidence | every criterion has a VALIDATION; DAG valid; high-risk paths → `WAITING_HUMAN` for plan approval |
| Build | any adapter; AC-aware TDD | named regression test fails on `base_commit` for the expected reason and passes on the candidate |
| Verify | clean worktree; repo `commands`; Playwright visual with a separate baseline-approval step; `services/vision` per criterion for UI | required validations PASS on the candidate commit |
| PR | `review/` council, now fed the spec and criteria; PR body gets a per-criterion evidence table (passed/failed/blocked/n.a.) | review has no blocking findings |
| Deploy (optional, later) | preview deploy + smoke test for Vercel/Render | smoke passes; production stays manual |

### 2.6 Safety invariants for unattended runs

1. **Agents cannot write trusted evidence.**
   - Worker sessions start with no AWG or GitHub credential: the adapter disables the AWG MCP server or extension and
     scrubs `AWG_*`/`GITHUB_*` env.
   - The agent's own model credential is the only secret it gets: its auth file mounted read-only, or the single
     provider API key its adapter declares. Check processes get no credentials at all.
   - Network egress: the worker may reach only its declared provider host(s) and package registries. Checks get
     localhost only, unless repo policy lists hosts. LLM or vision review of evidence runs in the trusted runner,
     never inside the sandbox.
   - Interactive agents use `agent`-kind tokens, capped at AGENT_ARTIFACT, which cannot satisfy TOOL_OUTPUT or CI
     validations.
   - Only the runner's `ci` token attaches check evidence.
7. **Fail closed on sandboxing.**
   - Unattended runs execute candidate code twice: in the agent, and in the checks. Both need an OS-level boundary.
   - Each adapter declares what it enforces natively. Claude Code has its sandbox settings; Codex has
     `--sandbox workspace-write`. OpenCode and pi have no OS sandbox.
   - If the permission profile needs a boundary the adapter can't enforce, the run must use `isolation: container`
     (Docker), or the runner refuses to start.
   - Checks always run with a scrubbed env (no AWG, GitHub or provider tokens), inside the same boundary.
   - Running on the host needs an explicit `allow_host_execution: true` in the personal profile, which
     `harness doctor` flags as a warning.
2. **Checks run on the candidate, not the agent's workspace.**
   - The runner commits the agent's changes itself and records the SHA.
   - It runs required checks in a *fresh* worktree checked out at that SHA, and binds evidence to that SHA.
   - Any later push or amend makes the evidence STALE (AWG).
3. **Lease loss means stopping, not finishing.**
   - On a heartbeat failure or a fencing mismatch, the runner kills the worker's process group and skips every side
     effect (no push, PR or comment). It keeps the worktree for inspection and reports the attempt as `INTERRUPTED`.
   - A reclaim gets a new attempt.
   - Pushes use `--force-with-lease=<branch>:<expected-sha>`.
4. **Budgets are reserved, not just recorded.**
   - The estimated per-run cost is reserved against the daily budget in one SQLite transaction before launch, then
     settled from the cost the adapter parses.
   - Adapters that stream cost are killed when they exceed `per_run_usd`.
   - Adapters that can't report cost run only with a deadline, are capped at a conservative fixed reservation, and are
     flagged in `doctor`.
   - Every adapter is killed at `deadline_s`.
5. **Privileged actions are never unattended.**
   - The runner only pushes `maggy/*` branches and opens *draft* PRs.
   - It never merges, never pushes to the default branch, and never deploys to production.
   - Worker env carries no deploy or production secrets.
   - A candidate that touches locked policy, CI config, protected test files or high-risk paths goes to
     `WAITING_HUMAN` instead of advancing.
8. **Kill switch.**
   - `maggy run stop` halts the runner, kills all worker process groups and releases leases.
   - A `~/.maggy/STOP` file is checked before every claim and side effect.
   - `maggy run pause --project KEY` pauses intake.
9. **Evidence privacy.**
   - Screenshots, traces and logs stay local: AWG Local plus the repo's own PR.
   - Sending them to an external model is off by default (`evidence.external_review: false`). Vision review uses
     local Qwen-VL unless the user opts in per provider.
   - Artifacts pass a secret scan before being attached to a PR.
6. **Ticket text is data.**
   - Issue and comment text goes inside delimited data sections of the prompt.
   - It is passed as a single argv element (no shell) and never used to build flags, paths or policy.

---

## 3. Roadmap (TDD throughout; each phase shippable)

**Phase 0a (blocking, before everything else): AWG scoped tokens.**
- Separate PR in the AWG repo, reviewed and merged by you.
- AWG prerequisite: `awg mcp`/CLI accept a scoped token (`AWG_TOKEN` / `--token-file`), with a contract test showing
  that an `agent` token can't satisfy a TOOL_OUTPUT validation.

**Phase 0b: Maggy safety and baseline (1–2 days).** Only fixes to code that survives, or that can lose work today:
- Disable executor parallel mode, which loses work.
- Fix the `install.sh` ordering bug.
- Add auth to the telos and e2e-testkit routes.
- Move the hardcoded client paths in `review/pipeline.py` behind a per-repo config.
- Make the suite green as a strict gate for Phase 1+. Fix each of the 52 failing tests; a test may only be deleted together with the dead code it covers, listed in the PR, and add the Maggy suite to CI.

**Phase 1: Personal Harness.**
- Profile schema, layering and locked keys.
- `harness init/show/doctor/diff/apply`.
- Emitters for Claude Code, Codex, OpenCode and pi, each with AWG wiring.
- Managed blocks and keys, plus backup.
- T3 spike.
- Move the personal tier table out of the repo `CLAUDE.md` into a profile preset.
- AWG repo: `plugins/opencode` and `plugins/pi`.
- *Exit:* on a clean HOME, `maggy harness apply` gives all four agents the same rules, skills and AWG tools;
  `doctor` reports each capability gap honestly.

**Phase 2: Worker interface.**
- `WorkerSpec`/`WorkerResult`.
- YAML adapters and parsers for Claude, Codex, OpenCode and pi, with recorded-fixture contract tests.
- Permission profiles, environment scrubbing, runner-computed diffs and checks, enforced budget and deadline.
- A replay set of 5 sample tasks to compare adapters.
- *Exit:* the same task runs headless on all four CLIs and returns comparable results.

**Phase 3: Runner on AWG.**
- `maggy run` loop: claim, heartbeat, fencing checks, commit-bound evidence, submit.
- GitHub intake via `awg sync`, with the opt-in label.
- Stable branch per item and idempotent PR creation.
- *Exit:* a labelled GitHub issue reaches a draft PR with evidence, and survives a runner kill partway through.

**Phase 4: Spec and plan stages.**
- Criteria and REQUIREMENT nodes, spec review, the question round-trip through `WAITING_HUMAN`.
- Structured plan and test plan as VALIDATION nodes.
- *Exit:* an ambiguous issue stops with one precise question, and resumes after it is answered.

**Phase 5: Verify and PR evidence.**
- AC-aware RED/GREEN.
- Visual checks with baseline approval, and a vision reviewer.
- Per-criterion evidence table on the PR; review council fed the spec.
- *Exit:* the coupon-style scenario from the factory doc runs end to end.

**Phase 6: Remove duplicates (D4).** Delete the legacy paths that the new layers replace:

| Replaced by | Delete |
|---|---|
| Worker adapters | `PiAdapter` model table and legacy manifest, both `_PI_MODELS`, `chat_stream` hardcoded argv (chat moves onto an adapter), `ai_client`/`model_escalation` argv, `orchestrator/adapters/*` |
| AWG + runner | `ExecutorService` session dict, `OrchestratorService`, Polyphony `orchestrator/` store/state machine, `scripts/polyphony`, `checkpoint.py`, `coordination/lock_manager.py`, approvals log, `escalation/` (→ `WAITING_HUMAN`), event_spine run use |
| `awg sync` | `plugins/provider-*`, `orchestrator/sources/*`; `maggy/providers` stays only if the inbox still needs it, otherwise the inbox reads AWG |
| Harness compiler | `install.sh` copy logic, `convert-hooks-to-toml.sh`, unwired templates |
| One router | `orchestrator/router.py`, `project_routing.decide_model` |
| Cleanup | `planning.py`, `models/plan.py`, `contracts/generator.py`, the Cortex `reasons` duplicate, one of the two Mnemos packages |

Each deletion lands as its own commit with the test suite green. Optional Phase 7: preview deploy stage, and
dashboard views over AWG metrics.

**Human gates on the plan itself:** every phase lands as PRs you review and merge, with no auto-merge. The AWG auth
change (0a) and every Phase 6 deletion need your explicit approval.

## 4. Open questions

Resolved: trust identity (§2.4: AWG token kinds, plus the Phase 0 AWG change), stage filtering (AWG capabilities),
spec versioning (WORK version).

1. **T3 Code:** confirm config inheritance (spike in §2.2).
2. **Mnemos:** which of `scripts/mnemos` and `maggy/maggy/mnemos` survives as AWG's context provider?

---

## Appendix A: detailed findings

### A.1 Agent execution paths

| Path | Where | State |
|---|---|---|
| PiAdapter | `adapters/pi.py:57-81` (13 hardcoded entries; manifest duplicated `:213-229`) | working, main path |
| Chat stream | `services/chat_stream.py:50-63`, hardcoded `claude -p … --dangerously-skip-permissions` | working, Claude only |
| orchestrator adapters | `orchestrator/adapters/*`; `get_adapter` has no callers | dead, best-shaped |
| Local team run | `services/orchestrator.py:205-231` hardcoded `claude -p` | partial |
| ai_client | `services/ai_client.py:83-109` | working |
| model_escalation | `services/model_escalation.py:87,108` | working |

Also:
- `ClaudeBackend.handles` claims every unknown model and ignores `model` (`pipeline/backend_claude.py:27,38`).
- `ExecutorBackend.handles()` always returns False.
- The `agy` and `gemini-cli` manifests are dead.
- Docker runtime: `docker create` gets no command, there is no agent CLI in the image, no timeout, and logs are discarded.
- `orchestrator/identity.py` (credential scoping) is never called.
- `scripts/polyphony` is an older fork; `orchestrator/__main__.py:37,56` called `load_config()` without its required argument (`__main__.py` was removed in Phase 6).

### A.2 State and intake

- Executor sessions are a dict (`executor.py:32`), and `checkpoint.read()` is never called.
- Locks have a fixed 30-minute TTL with no renewal (`lock_manager.py:11`).
- Approvals are logged after the action (`tool_executor.py:128-146`).
- Escalation resolve stores guidance that nothing reads.
- `register_extra_jobs` (the inbox poller) is never called.
- GitHub source uses `-q label:…`, which is the jq flag (`orchestrator/sources/github.py:28-31`).
- Monday is missing from the provider factory; Linear is `NotImplementedError`; no Jira.
- No PR creation anywhere.

### A.3 Spec, verification, review, deploy

- `planning.py` stub is still routed.
- `DualPlanner` produces free text and only runs at blast ≥7.
- `council/` is dead; `blast_analyzer` hardcodes `test_coverage=0.0`.
- `review/` is mature, but has hardcoded client paths and never sees the spec.
- TDD RED only checks that the suite fails, it is Python-only, and lint/coverage don't block.
- `visual_check.py` uses threshold 0 and overwrites the baseline in the same run.
- `services/vision.py` is not tied to criteria.
- Telos anti-criteria are always `[]`.
- e2e-testkit's drift parse always fails.
- `deploy.py` is a stub.
- iCPG `ReasonNode` is good but unversioned; Cortex duplicates it.
- Mnemos exists three times with incompatible schemas on the same `.mnemos/mnemo.db`.
- `executor_helpers.py:124-137` queries iCPG against Maggy's own path.
