# Changelog

All notable changes to Claude Bootstrap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Maggy: Personal Harness (Phase 5)

#### Added
- **AC-aware RED/GREEN regression proof** (RFC §2.5 Verify, §2.6.2). For a build child
  whose `task-plan` names regression tests, conclude now proves each one itself before
  publishing: in a fresh worktree at the base commit with ONLY the candidate's added/changed
  test files overlaid (from candidate blobs; source stays at base) the named test must FAIL
  by an assertion, then in a fresh worktree at the candidate it must PASS. Runs are
  classified from junit reports + exit codes into `passed` / `assertion` / `error`
  (collection, import, fixture/setup error or crash) / `missing`, giving outcomes `proven`,
  `not_red`, `setup_error` (distinct failure kind) and `not_green`. Each criterion gets
  ci evidence (kind `test`, PASS/FAIL, `commit_sha` = candidate, meta spec_version,
  criterion_id, check=regression, base_commit, regression_test, result_kind) bound to the
  plan's `[AC] test:` validation; any unproven test fails the attempt back to build with
  the trace in the handoff (bounded by the existing retry cap). New repo profile key
  `validation.regression` (`runner: pytest | node-test | playwright | command`, `command`,
  `junit`) declares how one named test runs (argv only, check env, check timeout).

- **Verify stage with functional, visual and vision checks** (RFC §2.5 Verify, §2.6.2,
  §2.6.9; factory doc §5). `stage:verify` is the PARENT item's step (not an extra child):
  once every build child in its `plan-<sha>` record is DONE/VERIFYING, the runner builds
  the integrated candidate (maggy/<ref> with each maggy/<child> merged, plus intact
  human-approved baselines, committed as Maggy in a fresh worktree and moved by
  compare-and-swap `update-ref`), then in fresh worktrees at that SHA with the check env
  runs the repo commands, each criterion's functional test, and each `evidence: visual`
  criterion: a Maggy Python-Playwright check from the test plan's new `visual` spec
  (route in the checkout, viewports, actions, layout assertions; file:// inside the
  checkout only, no network) compared against `.maggy/baselines/<AC>-<viewport>.png`, or
  the repo's own Playwright test with `--update-snapshots=none`. Layout failure or pixel
  diff -> FAIL with expected/actual/diff artifacts; missing baseline -> PENDING with a
  proposed image in the attempt dir and WAITING_HUMAN naming the
  `baseline-approved:<AC>:<viewport>` DECISION (sha256-bound). Matching captures go to a
  vision reviewer (backend interface; local Ollama Qwen-VL by default, external providers
  only when the personal-only `evidence.external_review` lists them); uncertain, refused
  or no backend is PENDING (a human may record `vision-reviewed:<AC>:<viewport>` at the
  SHA), never PASS. PASS/FAIL results are attached as ci evidence (commit_sha, meta
  spec_version, criterion_id, check, viewport); a `verify-<sha>:<attempt>` annotation
  records per-criterion verdicts and only the artifacts that pass a secret scan (token
  formats, entropy, known secret env values) for the PR. Installed the existing
  `maggy[visual]` extra (playwright 1.65.2, pillow, numpy) into the dev venv; browser
  tests use the cached chromium and skip with a reason where it cannot launch.

#### Changed
- `worker.stages` and the runner's held capabilities now include `verify` by default; new
  profile section `evidence` (`external_review: false | [providers]`, personal profile
  only); test-plan entries accept an optional `visual` spec.
- `runner.evidence` exposes `attach_once` (idempotent intent/result-annotated evidence) and
  `worker.checks._exec` is now the public `run_logged`, both reused by the regression proof.
  The Phase 3/4 exit rigs' fake build agent now writes the planned regression tests.

### Maggy: Personal Harness (Phase 4)

#### Added
- **Stage dispatch and the Phase 4 exit test** (RFC §2.4/§2.5). The runner claims with
  `[maggy-runner, stage:spec, stage:plan, stage:build, project:*]`; the new profile key
  `worker.stages` (default all three) restricts which stages a runner holds. `maggy run
  intake` now tags new issues `stage:spec` (was `stage:build`), so tickets start at the spec
  stage; `intake.capabilities` still overrides. `tests/test_runner_phase4_exit.py` drives an
  ambiguous ticket against the real awg CLI: exactly one question and WAITING_HUMAN, a human
  answer, spec approval (criteria, REQUIREMENT nodes, `spec-approved` DECISION), the plan
  graph with VALIDATIONs, and the first child built to a draft PR with CI-trust evidence.
  `docs/runner.md` describes the stage flow.

- **Plan stage: structured plan, task DAG, per-criterion VALIDATIONs, high-risk approval**
  (`maggy/runner/stages/plan*.py`, RFC §2.4/§2.5). The runner now holds `stage:plan`. The
  stage first checks the `spec-approved` DECISION still matches the item's criteria (it now
  records `criteria_sha` and the spec's `risk_paths`; AWG bumps the WORK version on every
  claim, so the fingerprint stands in for the version) and otherwise re-tags the item
  `stage:spec` (`spec_stale`). A read-only planner returns one fenced json `Plan` (tasks with
  key/title/files/depends_on; a test plan entry per criterion naming its task, fixture,
  action, expected, evidence and `regression_test_name`), checked as an acyclic DAG with
  known deps, full criterion coverage and repo-relative files (one retry with the problems,
  then fail before any mutation). Children are created in BACKLOG with
  `[maggy-runner, stage:build, project:*]` and a `task-plan` annotation, linked DEPENDS_ON,
  then given one VALIDATION per entry (automated evidence: kind test, min trust 3; manual:
  kind acceptance, min trust 2) linked to the criterion's REQUIREMENT node; only then are
  they made READY and the parent parked as `stage:planned` (`planned`). A failure mid-build
  cancels the children made so far. Plans touching `risk.high`/always-protected paths or
  the spec's risk paths wait in WAITING_HUMAN with a summary until a human `plan-approved`
  DECISION names the plan; re-claims never re-plan (`plan-<sha>` annotation). The build
  prompt now carries the task's test plan and regression test names. `AwgClient` gains
  `decisions`, `requirements`, `create_child`, `link`, `add_validation` and `set_state`
  (FakeAwg in memory with dependency-gated claims and cycle errors; CLI via `awg create
  --parent`, `state`, `link --lease`, `validation add`, `decisions`, `show` context).
  Legacy `DualPlanner` is not reused (free-text output, no DAG); it stays for Phase 6
  deletion.
- **Spec stage: author + independent reviewer, one-question round-trip**
  (`maggy/runner/stages/`, RFC §2.4/§2.5). Items claimed with `stage:spec` (the runner now
  holds it) get a read-only author run (`agents.default`) that must return one fenced json
  `SpecDraft` (criteria with id/text/kind/testable, open questions, assumptions, risk paths),
  then a fresh read-only reviewer run (`agents.prefer.review`, else default) returning
  `SpecReview` (`ready` / `needs_clarification` with exactly one question / `blocked`).
  Invalid output gets one retry with the validation error, then the attempt fails with no
  graph mutation. `needs_clarification`/`blocked` annotate the draft and move the item to
  WAITING_HUMAN with the single question (or reason); the human's answer comment is in the
  next round's context. `ready` replaces the WORK criteria (spec version bump), creates one
  REQUIREMENT node per criterion, records a `spec-approved` DECISION with `spec_version`,
  re-tags the item `stage:plan` and releases it. Ticket, comments, drafts and repo context
  (AGENTS.md, file list) stay inside one delimited untrusted-data block. `AwgClient` gains
  `update`, `create_node` and `decision` (FakeAwg in memory; CLI via `awg update`,
  `awg node create`, `awg decision`). Legacy spec/planner code is untouched (Phase 6 deletion).

#### Fixed
- **Plan records and task plans are now found in real `awg annotations` rows.** Those rows
  carry `idempotency_key`, not `key`, so the plan stage never found its `plan-<sha>` record and
  re-planned on every re-claim (a second set of children, and a `plan-approved` DECISION taken
  as covering a plan the human never saw), and build prompts lost the task's test plan.
  `annotation_key`/`annotation_data` now live in `awg_types` and read both; FakeAwg returns
  the real row shape, and the Phase 4 exit test checks the build prompt against the real awg.
- **Plan children are held under `stage:pending` until the plan gate releases them.** `awg
  create` makes items READY, so a child created with `stage:build` could be claimed by a
  build-only runner before its links, validations or plan approval existed, or stay claimable
  if the runner died. Children are now created with `stage:pending` (no runner holds it) and
  `finish` retags each to `stage:build` (new unfenced `set_capabilities` → `awg update
  --capability`) before moving it READY.
- **A plan child left READY by a partial `create_child` failure is now cancelled.** `awg
  create` makes the child READY; if the BACKLOG move or the `task-plan` annotation then failed,
  `CliAwgClient.create_child` raised before `build_graph` learned the child's ref, so the
  rollback skipped it and a claimable `stage:build` task with no plan escaped the high-risk
  plan-approval gate. The client now cancels that child (best effort) and re-raises the
  original error. The brief READY window between `create` and the BACKLOG move remains until
  AWG can create items in BACKLOG directly.
- **Runner CLI calls now match the real awg** (`maggy/runner/awg_cli.py`,
  `awg_cli_graph.py`), found by the Phase 4 exit test. `awg block` takes no fence flags
  (the runner fences it with `session.verify()` just before) and now passes `--question`,
  so the spec question lands as the item's one comment. `awg node create` takes `--title`
  and `--parent-work` (criterion data rides in `--description`), and `awg decision` needs
  `--title`; both are now fenced by the item's lease.

### Maggy: Personal Harness (Phase 3)

#### Added
- **`maggy run intake`, runner tokens and the Phase 3 exit test against the real AWG**
  (`maggy/runner/intake.py`, `evidence.py`, `harness/cli/awg_tokens.py`, `doctor_checks.py`,
  `docs/runner.md`). `maggy run intake --repo OWNER/REPO [--label]` wraps `awg sync github
  --label --capability maggy-runner --capability stage:build --json`. The label and
  capabilities come from the repo profile's `intake.*` (new `intake.capabilities`), and
  intake refuses to run without a label. `maggy harness init` mints
  `~/.maggy/tokens/runner-agent.token` (kind agent) and `runner-ci.token` (kind ci), both
  0600. `harness doctor` checks that both exist, are private and reach AWG. `maggy run` now
  reads these files. An integration test runs the real awg CLI with a temp HOME/AWG_HOME,
  `awg init` and minted tokens. It covers intake through a fake `gh`, `maggy run --once` (CI
  evidence bound to the candidate SHA, agent evidence ignored, one draft PR, one submit) and
  a SIGKILL after the push followed by a restart that converges. It skips, with the reason,
  when no awg with the runner flags is present.

#### Fixed
- **Runner claims are bound to the repo's project; pause covers intake** (`maggy/runner/config.py`,
  `loop.py`, `intake.py`, `docs/runner.md`). A runner bound to repo A could claim any
  `maggy-runner` item in the workspace, including project B's, and build, push and open a PR
  for it in repo A; `maggy run pause --project B` did not stop that, and `maggy run intake`
  ignored the pause flag. Intake now tags items `project:KEY` (KEY: `--project`, else the
  checkout's repo name), the runner requires and holds `project:<its project>` when claiming,
  and intake refuses while KEY is paused (new `--state-dir`). `awg next` has no `--project`
  filter, so the binding rides on the required capability. Items created before this change
  need a `project:KEY` capability to be claimed again.
- **Runner review findings (Phase 3)** (`maggy/runner/loop.py`, `lock.py`, `retry.py`,
  `recovery.py`, `control.py`, `awg_cli.py`, `publish_gh.py`, `worker/pidfile.py`,
  `harness/cli/doctor_checks.py`, `docs/runner.md`). The runner claimed items that never
  opted in: it now passes `--require-capabilities=maggy-runner`, so untagged items are left
  alone. A second `maggy run` on the same state dir released the live runner's lease as if it
  had crashed: an exclusive `runner/runner.lock` (flock) now makes it report `locked`. A
  failing item was re-run in a hot loop: the loop now backs off after every pass without
  progress, and after three consecutive failed attempts the item is blocked for a human.
  Crash recovery left the dead runner's worker group running in the worktree: reconcile now
  kills it and removes its pid entry, and pid entries record the leader's start time so
  `maggy run stop` never kills a process that reused the pid. The PR lookup by head branch
  could adopt a fork's PR named `maggy/<ref>`: only same-repository PRs are used now. CI
  trust is not enforceable under host execution (agent-written code runs as the same user as
  the ci token): `docs/runner.md` states the limit, and `harness doctor` and `maggy run`
  warn about it.
- **Runner against the real AWG CLI:** these mismatches with the real CLI turned up in the
  exit test.
  - `next` now gets comma-separated `--capabilities`. Repeated flags kept only the last one,
    so the runner never claimed anything.
  - Evidence is now bound to the item's CI `test` validation through `--validation`. Without
    it, AWG ignored the evidence for the completion contract.
  - `CliAwgClient.show` now merges `awg proof` validations and the `awg comments` thread, so
    the runner can find the validation and the previous attempt's handoff.
  - Evidence is attached once per attempt, check and SHA, using keyed intent/result
    annotations instead of evidence fields that `awg show` does not return.
- **Crash recovery and startup reconciliation for `maggy run`** (`maggy/runner/state.py`,
  `recovery.py`, `publish_settle.py`; RFC personal-harness §2.4, §2.6.3). The runner records
  each held lease (claim, then the WorkerResult once checks ran) in
  `<state_dir>/runner/state.json` (path injectable, atomic writes). On start and before every
  claim (never while STOP is set) it reconciles each held item: dangling publish intents get a
  `reconciled` result looked up by stable name (remote `maggy/<ref>`, open PR by head); if the
  lease is still live and the worker had finished it rolls forward (evidence attached once per
  check/SHA/spec version, idempotent push and PR, submit), otherwise it rolls back (release with
  a handoff naming what was done, the branch's last SHA and the next step). Worktree and branch
  are kept; the re-claim resumes from the branch and the latest handoff is passed to the worker
  prompt as delimited data. Crash-injection tests (kill -9 after worker exit before commit,
  after commit before evidence, after push before PR, after PR before its result, after PR
  before submit) converge to one draft PR, evidence bound to the final SHA and a single submit.
- **Stable-branch push and idempotent draft PR with intent records** (`maggy/runner/publish.py`,
  `publish_git.py`, `publish_gh.py`, `publish_body.py`; RFC personal-harness §2.4, §2.6.3,
  §2.6.5). `maggy run` now uses `Publisher` as its PR step. For each external action the
  fence (STOP + live lease) is verified, an intent annotation keyed
  `<ref>:<attempt>:<action>:<sha>` is written, the action runs, and a `<key>:result`
  annotation records the outcome.
  - Push: only `refs/heads/maggy/<ref>` (anything else is refused), argv-only through the
    hardened `run_git`, `git push --force-with-lease=refs/heads/maggy/<ref>:<expected>
    origin <sha>:refs/heads/maggy/<ref>`. The expected SHA is the remote's when absent or one
    we recorded, else our last recorded push, so a remote that moved unexpectedly rejects the
    push. A remote already at the candidate is not re-pushed. Maggy injects no credentials;
    the user's git config (and `SSH_AUTH_SOCK`) authenticate.
  - PR: `gh pr list --head maggy/<ref> --state open --json number,url,isDraft,state`; none
    -> `gh pr create --draft --head --base <origin default branch> --title --body-file`,
    otherwise `gh pr edit N --body-file`, so re-runs and new attempts never duplicate. The gh
    wrapper refuses anything but `pr list/create/edit` (no merge, no ready) and gets the
    scrubbed env plus the user's own `GH_*` settings, never AWG tokens. The body carries a
    summary, AWG ref, candidate SHA, attempt and a checks table (name, result, SHA).
  - Crash recovery: a crash between intent and result reconciles from external state (remote
    SHA, PR lookup by stable head) without a second push or PR.
  - `session.verify_live()` factored out of `Session.verify` so the publisher fences the same
    way.
- **Runner loop `maggy run [--once] [--project KEY] [--adapter X]`** (`maggy/runner/loop.py`,
  `drive.py`, `conclude.py`; RFC personal-harness §2.4, §2.6.1/3/5/8). Per item: STOP and
  per-project pause checked before every claim; claim with `[maggy-runner, stage:build]`
  (spec/plan stages are released as "not supported yet"); stable worktree on `maggy/<ref>`,
  resumed from an existing branch; WorkerSpec from the context bundle (ticket text delimited
  as data, permission/deadline/budget from the repo profile) run through Phase 2's
  `run_attempt`. A heartbeat thread at lease/3 touches a per-attempt interrupt file on any
  failure so the supervisor kills the worker's process group; lease loss or a stale fence
  then skips every side effect, keeps the worktree and gives the item back as interrupted
  with a handoff. After the worker the fence and spec version are re-checked (a changed
  version returns the item for spec review), one evidence per check is attached via the ci
  credential bound to the candidate SHA with `spec_version`/`check` meta, blockers and
  protected-path edits go to `WAITING_HUMAN` with the question, and only then the PR step
  (task 3.3 hook) and `submit` run. Every decision is appended to
  `<state>/attempts/<attempt>/runner.jsonl`.
- **Kill switch and pause** (`maggy/runner/control.py`): `maggy run stop` creates `STOP` and
  SIGKILLs the worker process groups registered in `<state>/runner/pids/*.pid` (written by
  the worker launcher, removed after the run); `maggy run pause|resume --project K`.
  Worker `Job`/`Attempt` gain `interrupt_file` and `pid_file`.
- **`AwgClient` protocol, CLI-backed client and in-memory fake** (`maggy/runner/`, RFC
  personal-harness §2.4, §2.6.1, §2.6.3). The runner's one interface to AWG: `next_claim`
  (capability-filtered), `heartbeat`, `submit`, `release`, `block`, `handoff`, keyed
  idempotent `annotate`/`annotations`, commit-bound `evidence`, `show`.
  - `CliAwgClient` runs the awg CLI argv-only with `--token-file` and `--json`: the `agent`
    token for every lifecycle call, a separate `ci` token for `evidence` alone (one file for
    both is refused). Token secrets never enter argv or logs, and `AWG_TOKEN` is dropped from
    the child env so an ambient credential cannot stand in. Lifecycle calls carry
    `--attempt`/`--fencing-token`; refs follow `--` and free text uses `--opt=value`, so ticket
    text can never parse as an option.
  - awg failures map to typed errors: `FenceStale` (a `LeaseLost`), `Unauthorized`,
    `NotFound`, `AwgUnavailable` (missing binary, timeout, retry-later codes), else `AwgError`.
  - `FakeAwg` mirrors AWG Local in memory (leases that expire, fencing tokens and versions
    bumped per claim, idempotent annotations, evidence trust from the credential: agent=1,
    ci=3) to drive runner unit tests.
  - `handoff` is written as an `awg comment` tagged with the attempt id, since the awg CLI has
    no `handoff` command yet.

### Maggy: Personal Harness (Phase 2)

#### Security
- **Phase 2 review fixes, round 2: no settings-file plugins/hooks, no prompt-as-option**
  (RFC personal-harness §2.6.1 invariant 1, §2.6.7).
  - The Claude worker now runs with `--setting-sources ''`: no user/project/local settings
    file is read, so no enabled plugins (the awg plugin's lease heartbeat and
    TodoWrite/Task* mirroring hooks, which wrote to AWG with the user's credential;
    clawalkietalkie) and no settings hooks run in a worker. `--strict-mcp-config` and
    `--disallowedTools mcp__awg` stay as a second line. Verified from the stream-json
    init event (also against a repo `.claude/settings.json` enabling awg) and one live
    read_only run confirming subscription auth still works.
  - A prompt starting with `-` can no longer reach a CLI as an option: the claude, codex
    and opencode adapters put `--` before `{prompt}` (each CLI verified to treat
    `-- --version` as a prompt); `render_argv` raises and `LaunchPlan.argv` refuses such a
    prompt for adapters without `--` before `{prompt}` (pi, whose parser ignores `--`).
- **Phase 2 review fixes: fail-closed worker boundaries** (RFC personal-harness §2.3,
  §2.6.1, §2.6.4, §2.6.7, §2.6.8).
  - Bypass check now covers adapter `budget_flags`, so `--dangerously-skip-permissions`
    hidden there is refused like anywhere else in an adapter.
  - `run_attempt` re-checks the STOP kill switch after the worker ends and before the
    checks: once STOP is pulled there is no runner commit and no check run, and the
    attempt is `failed`.
  - Claude's own budget stop (`subtype: error_max_budget_usd`, new
    `ParsedRun.budget_hit`) is reported as `budget_exceeded`, not `failed`. Result
    assembly moved to `maggy/worker/outcome.py`.
  - The host-execution decision uses what the adapter mapping really grants (new adapter
    `grants: {<permission>: {write, shell}}`; undeclared mappings grant both). A repo
    profile can no longer redefine or lock `permissions.profiles.workspace` as read-only
    to launch opencode/pi on the host with edit and bash.
  - Runner git runs with the scrubbed allowlist env (plus `GIT_CONFIG_NOSYSTEM`, no
    inherited `GIT_*`). `commit_candidate` pins `--git-dir`/`--work-tree` to the admin dir
    recorded in the main repo, refuses a worktree whose `.git` file was rewritten, and
    diffs with `--no-ext-diff --no-textconv`. This stops agent-defined filters from
    running with runner credentials.
  - Required checks run candidate code and have no sandbox yet, so they need the personal
    `worker.allow_host_execution: true`. Without it the runner refuses before launch
    (even for natively sandboxed claude/codex) and `run_checks` refuses on its own.
  - Each adapter declares at most one provider key (schema-enforced). claude:
    `ANTHROPIC_API_KEY`, codex: `OPENAI_API_KEY`, opencode/pi: `ANTHROPIC_API_KEY`.
    Other providers use the auth file or a `~/.maggy/adapters/` override.

#### Added
- **Replay set and `maggy worker replay` (Phase 2 exit)** (RFC personal-harness §2.3,
  §3 Phase 2). `maggy/worker/replay/`: five self-contained tasks (`implement`,
  `off_by_one`, `cli_flag`, `refactor`, `ambiguous`), each a YAML with fixture repo files
  (git-initialised in a temp dir at runtime), a prompt, hidden acceptance tests kept
  outside the repo and a reference solution. Each task x agent runs through the full
  pipeline with required checks `test` (repo suite) and `e2e` (hidden acceptance); the
  report (table + `--json`) gives verdict, outcome, checks passed, changed files, cost,
  elapsed and model per row. Offline (default) puts fake `claude`/`codex`/`opencode`/`pi`
  CLIs first on the worker PATH (new `Attempt.path_prefix`, `env.with_path_prefix`) that
  replay recorded output (`replay/recordings/`, packaged) via the shipped adapter argv;
  `--live` runs the real CLIs under the personal launch policy and budget. Live results
  for claude and codex are in `docs/worker-replay.md`.
- **Agent-raised blockers** (RFC personal-harness §2.3). `maggy/worker/blocker.py`: a
  line starting with `QUESTION:` in the agent's final text (markdown emphasis tolerated)
  becomes the result's `Blocker` and turns a succeeded run into `outcome: blocked`;
  protected-path blockers still take precedence. `BLOCKER_INSTRUCTIONS` tells agents the
  convention (used by the replay prompts; Phase 3 adds it to runner-assembled prompts).
- **Adapter `budget_flags`: CLIs that can cap their own spend get `per_run_usd`**
  (RFC personal-harness §2.6.4). Adapters may declare `budget_flags` (only the
  `{budget_usd}` placeholder is allowed) and splat them with `{budget_flags}`; the
  pipeline renders them with the attempt's per-run budget (4 decimals) and drops them
  when no budget is set. The shipped Claude adapter now passes
  `--max-budget-usd <per_run_usd>` (flag checked against the recorded `claude --help`),
  so a non-streaming Claude run stops itself at the per-run budget.
- **Runner-side commit, diff and checks, plus `maggy worker run`** (RFC personal-harness
  §2.3, §2.6.2, §2.6.5, §2.6.7). `maggy/worker/worktree.py` creates each attempt's
  worktree on branch `maggy/<awg-ref>` from `base_commit` (an existing branch is refused,
  never reset; the legacy `orchestrator/isolation.py` helpers are not reused).
  `maggy/worker/commit.py`: after the worker exits, the runner stages everything
  (`git add -A`, untracked non-ignored files included) and commits as `Maggy
  <maggy@localhost>` (author and committer forced via env) with a message naming the
  awg_ref and attempt_id; `candidate_commit` and `changed_files` come from
  `git diff base..candidate`, and no change gives `candidate_commit: null`. All runner
  git calls disable repo hooks, fsmonitor and signing, so nothing the agent planted runs
  with the runner's environment. `maggy/worker/checks.py` runs `validation.required`
  (mapped to `commands.*`) in a fresh detached worktree at the candidate SHA, each as
  `shlex.split` argv (no shell) with `build_check_env` (no credentials, throwaway HOME)
  and the new `validation.check_timeout_s` (default 600); a missing command or timeout
  fails the check; the check worktree is removed afterwards and logs stay in the attempt
  dir. `maggy/worker/protected.py` flags edits to `risk.high` paths, `.github/**` and
  `.maggy/**`: the result gets a blocker asking to move the item to `WAITING_HUMAN` and
  a successful run becomes outcome `blocked`. Nothing is pushed. `maggy/worker/pipeline.py`
  chains launch policy, budget reservation, supervisor, parser, commit, checks and the
  protected-path flag into one `WorkerResult`. New CLI `maggy worker run --adapter X
  --repo R --prompt-file F [--permission P] [--deadline S] [--budget U]` builds a local
  WorkerSpec (dummy `local-*` awg_ref, fencing token `local`; no AWG claim yet), checks
  the launch policy before creating any worktree, and prints the WorkerResult as JSON
  (exit 2 with the reason when refused).
- **Worker process supervisor and daily budget ledger** (RFC personal-harness
  §2.6.3, §2.6.4, §2.6.8). `maggy/worker/supervisor.py`: `supervise(job)` launches
  the adapter argv (no shell) as the leader of a new session, streams stdout/stderr
  to `stdout.log`/`stderr.log` in the attempt dir, and kills the whole process group
  (SIGTERM, then SIGKILL after `grace_s`, leftovers always reaped) on `deadline_s`
  (outcome `timeout`), on a `~/.maggy/STOP` file before launch or while running
  (outcome `failed`, reason `stopped`; path injectable), and, for cost-streaming
  parsers, when parsed cost passes `per_run_usd` (outcome `budget_exceeded`).
  `maggy/worker/ledger.py`: `BudgetLedger` in `~/.maggy/budget.db` (path injectable)
  reserves each run in one `BEGIN IMMEDIATE` transaction, refusing (`BudgetRefused`)
  anything that would pass `per_day_usd`, so concurrent threads or processes never
  overshoot; `settle` and `release` close a reservation. `maggy/worker/budgeted.py`:
  `run_budgeted` reserves before launch (a refusal means nothing starts), releases
  when launch fails, and settles at the parsed cost, or at the reservation when the
  cost is unknown or the supervisor crashed. Reservation is `per_run_usd` for
  cost-streaming adapters and `cost.fixed_reservation_usd` otherwise. The older
  per-provider spend tracker in `maggy/budget.py` is left as is for Phase 6.
- **Worker and check env scrubbing** (RFC personal-harness §2.6.1, §2.6.7).
  `maggy/worker/env.py`: `build_worker_env(adapter, base_env)` keeps only an
  allowlist (`PATH`, `HOME`, `LANG`, `LC_*`, `TERM`, `TMPDIR`, `SHELL`, `USER`) plus
  the adapter's declared provider key(s) when present. Everything else is dropped,
  including `AWG_*`, `GITHUB_*`, `GH_*`, `GITLAB_*`, `AWS_*`, `SSH_*`, `MAGGY_*`,
  `*_TOKEN`/`*_SECRET` and other providers' keys. Secret-looking names are dropped
  even when they match the allowlist (e.g. `LC_*_TOKEN`). The worker keeps the real
  HOME so the CLI can read its own login. `build_check_env(base_env, home)` returns
  the allowlist with no credentials at all and HOME set to a throwaway dir.
  `auth_file_refs` resolves an adapter's auth files as read-only references in
  place; the runner never copies them into the workspace. Adapter schema now
  rejects provider keys with a forbidden prefix (an adapter cannot smuggle
  `GITHUB_TOKEN` or `AWG_TOKEN` in), provider keys that are not valid env names,
  and auth files that are not `~/` or absolute paths, or that contain `..`.
- **Shipped worker adapters and fail-closed launch policy** (RFC personal-harness
  §2.3, §2.6.1, §2.6.7). `maggy/worker/adapters/{claude,codex,opencode,pi}.yaml`
  with headless argv verified against each CLI's recorded `--help` excerpt
  (versions in the fixtures): `claude -p --output-format json` (read_only = plan
  mode + `--tools Read,Grep,Glob`; workspace = acceptEdits + sandbox settings that
  fail if unavailable), `codex exec --json --sandbox read-only|workspace-write`,
  `opencode run --format json` (permissions via `OPENCODE_PERMISSION`), `pi -p
  --mode json --no-session` (read_only = `--tools read,grep,find,ls`). Every
  launch disables AWG for the worker: claude `--strict-mcp-config` plus
  `--disallowedTools mcp__awg` (a live check showed strict MCP config alone keeps
  plugin MCP servers), codex `-c mcp_servers.awg.enabled=false` (with a command
  stub so it is valid when no awg server exists), opencode `--pure` plus
  `OPENCODE_CONFIG_CONTENT` disabling `mcp.awg`, pi `--no-extensions`. New
  `AdapterSpec.permission_env` (per-profile env; may not override the AWG-off env).
  `resolve_launch(adapter, profile, permission)` returns a `LaunchPlan` (argv, env,
  host_execution) or raises `Refused`: write/shell profiles on adapters without a
  native sandbox need `worker.allow_host_execution: true`; permission-bypass flags
  (`--dangerously-*`, `--yolo`, opencode `--auto`, `bypassPermissions`,
  `danger-full-access`) are refused anywhere in an adapter; `isolation: container`
  is refused as not implemented yet. Harness profile gains `worker.isolation`
  (`worktree`|`container`) and `worker.allow_host_execution` (personal profile
  only; a repo profile setting it is a config error); `harness doctor` warns when
  host execution is allowed.
- **`maggy/worker/`** — worker interface models and data-driven adapters (RFC
  personal-harness §2.3, §2.6). Strict Pydantic models `WorkerSpec` (AWG ref,
  attempt id and fencing token carried as plain data), `WorkerResult` (a
  `blocked` outcome requires a `Blocker{question, options}`), `CheckResult` (a
  check cannot pass with a non-zero exit). `AdapterSpec` schema for
  `worker/adapters/*.yaml` (detect argv, argv template, cwd, permission
  profile -> flags, native sandbox, output parser id, instruction file, quota
  patterns, provider keys/auth files, AWG-disable flags/env, cost streaming and
  fixed reservation). `load_adapters` reads shipped adapters, each replaced whole
  by `~/.maggy/adapters/<name>.yaml` (dir injectable); bad files fail with file
  and key path. Safe argv templating: placeholders only as whole elements
  (`{prompt}`, `{model}`, `{workspace}`) or list splats (`{permission_flags}`,
  `{model_flags}`, `{awg_off_flags}`); embedded or unknown placeholders are
  load-time errors; `{prompt}` appears exactly once and values are never
  re-scanned, so prompt text is always one literal argv element.
  `assemble_prompt`/`wrap_untrusted` put ticket text in an
  `<untrusted_ticket>` data section and defuse delimiter copies inside it.
- **`maggy/worker/parsers/`** — output parsers turning a CLI run's stdout/stderr
  into `ParsedRun(final_text, cost_usd, model, usage, error, quota_hit,
  session_ref)`: `claude-json` (result object; model = highest-cost entry of
  `modelUsage`), `codex-jsonl` (thread/turn/item events; nested API error JSON
  unwrapped), `opencode-json` (step/text/error events; cost and tokens summed
  from `step_finish`), `pi-jsonl` (pi 0.73.1 `AgentSessionEvent`s; assistant
  `message_end` usage/cost, `stopReason` error/aborted, failed auto-retries) and
  `text`. Parsers never raise: malformed lines are reported by line number,
  unknown events are ignored, streams without a terminal event are reported as
  truncated, and non-finite numbers are dropped. `parse_run` adds an
  `exit code N: <stderr tail>` error when a non-zero exit left none, and sets
  `quota_hit` from the adapter's quota patterns over stderr and error text only.
  Contract-tested against fixtures in `tests/fixtures/worker/<cli>/` with a
  `meta.yaml` (version, command, date, `synthetic`) and versioned `--help`
  excerpts: claude and codex success/error cases are real scrubbed recordings;
  quota cases and all opencode/pi fixtures are synthetic. A hygiene test rejects
  home paths, emails, token-like strings and non-zero UUIDs in fixtures.

### Maggy: Personal Harness (Phase 1)

#### Added
- **`maggy/harness/`** — harness profile schema and layering (RFC personal-harness
  §2.1). Strict Pydantic v2 models (unknown keys rejected) for agents, surfaces,
  models, instructions, skills, hooks, permissions, gates, work, budget and the
  repo-level commands, intake, worker, risk, validation and `locked`.
  `resolve_profile(repo_root, personal_path)` merges shipped defaults < repo
  (unlocked) < personal (`~/.maggy/harness.yaml`) < repo-locked: keys (or dotted
  paths) listed in the repo's `locked:` cannot be changed by the personal file.
  Dicts deep-merge, lists replace. It returns the profile plus a provenance map
  (`default|repo|personal|repo-locked`) for every top-level and nested key.
  Invalid YAML, unknown keys, bad types and credential-looking keys (token,
  api_key, secret, password, ...) fail with the file and key path; missing or
  empty files fall back to defaults; `locked` is rejected in the personal file.
- **Managed regions engine** (`maggy/harness/regions*.py`, `plan.py`, `apply.py`,
  `lock.py`; RFC §2.2). Pure `render`/`extract` for Markdown
  (`<!-- maggy:begin id -->` blocks), hash-comment text, JSON (managed keys at
  dotted paths, user key order kept) and TOML (via `tomlkit`, comments kept);
  content outside managed regions is preserved byte for byte. Invalid JSON/TOML
  and JSONC with comments are reported and never overwritten. `plan_files`
  returns `FileChange`s (create/update/unchanged; ok/conflict/invalid/refused).
  `~/.maggy/harness.lock` (path injectable) stores the sha256 and text of each
  region last written; a user edit inside a region is a conflict with a 3-way
  diff (last-written / on-disk / profile), resolved with `take_mine` (adopt
  on-disk, update lock) or `take_profile` (overwrite region). `apply_changes`
  backs up each touched file to `~/.maggy/backups/<ts>/` (mirroring paths)
  before an atomic temp+rename write, refuses paths whose symlinks leave the
  target root, skips files changed since plan, and sets 0600 on files that
  reference token files. Adds the `tomlkit` dependency.
- **Claude Code and Codex emitters** (`maggy/harness/emitters/`; RFC §2.2).
  `Emitter` protocol: `agent`, `capabilities()` (instructions, skills, hooks,
  mcp, permissions as native/partial/none + notes) and `plan(profile, scope)`,
  which returns `FileChange`s without writing; `Scope` is user (HOME) or
  project (repo root). Instruction includes are read from the Maggy repo
  (`rules/…`, or `MAGGY_HARNESS_SOURCES`) into an `AGENTS.md` managed block;
  Claude gets a `CLAUDE.md` block with `@AGENTS.md` (user scope: `~/.claude/`).
  Skills are copied to `.claude/skills/` / `~/.codex/skills/` (project:
  `.agents/skills/`) with a `maggy:managed-skill` marker: only marked copies are
  updated or removed when dropped from the profile; same-named user skills and
  edited copies are conflicts. Claude hooks map to `settings.json` hook events
  (commands `$HOME/.maggy/hooks/<name>`, user entries kept); permissions map the
  `worker.permission` profile to `permissions.allow/deny` (added to user rules)
  and to Codex `sandbox_mode` + `approval_policy`. AWG: Claude
  `mcpServers.awg` in `~/.claude.json` / `.mcp.json`, Codex
  `[mcp_servers.awg]` plus the AWG `AGENTS.md` section (vendored from AWG
  `plugins/codex/AGENTS.md`); both use `awg mcp --token-file
  ~/.maggy/tokens/<agent>.token` and never inline a token. Codex reports
  hooks=none (the runner enforces). `apply_changes` now supports `delete`
  changes (backup, remove, forget lock entry).
- **OpenCode and pi emitters** (`emitters/opencode*.py`, `pi*.py`; RFC §2.2),
  checked against opencode 1.19.6 and pi 0.73.1. OpenCode: `AGENTS.md` block in
  `$XDG_CONFIG_HOME/opencode` (default `~/.config/opencode`) or the repo, and
  `opencode.json` managed keys `instructions`, `mcp.awg` (`awg mcp --token-file
  ~/.maggy/tokens/opencode.token`; project files use `{env:HOME}`),
  `permission.edit/webfetch/websearch/bash` from the profile, and in user scope
  AWG's heartbeat plugin (`plugin`) and skill (`skills.paths`) by path into the
  AWG checkout; skills in `<config>/skills` / `.opencode/skills`. User list
  entries and bash patterns are kept. Emitted config is tested against the real
  1.19.6 config schema (`tests/fixtures/harness/`, taken from `opencode serve`
  `/doc`) and resolved by the real binary when available. pi: `AGENTS.md` in
  `~/.pi/agent` or the repo, skills in `~/.pi/agent/skills` / `.pi/skills`, a
  generated `extensions/maggy-hooks.ts` that runs `$HOME/.maggy/hooks/<name>` on
  pi events (hooks=partial: no stdin payload, only before_tool can block), and
  in user scope AWG's pi extension copied into `~/.pi/agent/extensions/awg/`
  (marker `// maggy:managed-extension`), its skill via `settings.json` `skills`
  and the token file via `awg.json` `tokenFile`. The AWG checkout comes from
  `MAGGY_AWG_REPO` (`EmitterSources.awg_repo`); without it the AWG plugin pieces
  are skipped. Managed whole-file copies (skills, extensions) now share
  `emitters/copies.py`. Adds `jsonschema` to the `test` extra.
- **`maggy harness` CLI** (`maggy/harness/cli/`, registered on `maggy.cli:app`):
  `init` detects agent CLIs (`which` + `--version`), asks four short questions
  (`--yes` takes defaults), writes `~/.maggy/harness.yaml` (kept unless
  `--force`), runs `awg init` when `awg status` fails, and mints one `agent`
  token per agent (`awg token mint maggy-<agent> --kind agent --json`) into
  `~/.maggy/tokens/<agent>.token` (0600, never printed). `show` prints every
  resolved key with its source. `doctor` prints a per-agent capability table
  (native/partial/none), warns when a CLI drifts from the tested version
  (claude 2.1.330, codex 0.163.0, opencode 1.19.6, pi 0.73.1), and reports
  missing agents, missing token files and AWG reachability per token
  (`awg --token-file F status`), plus T3 advice when `t3` is a surface. `diff`
  and `apply` (`--agent`, `--scope user|project`, `--repo`) compile one plan
  across agents (`harness/compile.py` merges files several emitters manage,
  such as the repo `AGENTS.md`), show unified diffs, confirm (`--yes`), back up,
  write and update `harness.lock`; a second apply is a no-op. Conflicts are
  listed with `--take-mine` / `--take-profile` (now passed through `Scope`).
  Exit codes: 0 ok, 1 conflicts/errors, 2 usage. Subprocesses use argv lists.
- **`token-economy` preset** (`maggy/harness/presets/`): the personal model-tier
  table, routing heuristic and personal tool invocations (deepseek / kimi /
  gemini / grok, `~/bin/*` scripts, `pr-review`, hook signals) moved out of the
  repo `CLAUDE.md` into `presets/token-economy.md`, with a preset profile layer
  (`token-economy.yaml`: cost tiers, `preset:token-economy.md` include,
  `model-routing` skill). `maggy harness init --preset token-economy` merges it
  under the interview answers; unknown presets fail and list the choices.
  Instruction includes of the form `preset:<file>.md` resolve inside the package.
  `harness doctor` now prints a `GAP <agent> <capability>=<level>: <notes>` line
  for every non-native capability.
- **Phase 1 exit test** (`tests/test_harness_phase1_exit.py`): temp HOME + temp
  repo, `init --yes --preset token-economy` with all four agents and awg faked,
  `apply --yes`: Claude (`CLAUDE.md` -> `@AGENTS.md`), Codex, OpenCode and pi get
  the identical rules block, the same skills and AWG wiring to their own token
  file; second apply is a no-op; doctor exits 0 listing every gap. The emitted
  Codex config is checked with the real `codex mcp list --json` (tomllib
  otherwise) and `opencode.json` against the 1.19.6 schema.

#### Added (docs)
- `docs/rfc-personal-harness.md`: the Personal Harness RFC this phase implements,
  now tracked in the repo.

#### Changed
- `maggy harness` (and the analytics commands) are registered through
  `maggy/cli_extensions.py`, so the already oversized `maggy/cli.py` shrinks
  (302 -> 299 lines) instead of growing.
- Retroactive note for commit ea9f2a2 (test-only): the orchestrator auth test
  in `tests/test_routes_orchestrator_auth.py` was reshaped to stay within the
  3-parameter quality gate; no behaviour change. It landed without a changelog
  line.
- Repo `CLAUDE.md` now holds project-generic engineering policy only (TDD,
  quality gates, changelog, PR workflow); personal routing lives in the preset.

#### Fixed
- `maggy harness init` now always includes the generic engineering rules (TDD, quality gates, security, changelog) in the profile; presets add to them instead of being the only rules source. Previously a no-preset init emitted no instructions to any agent.
- **First apply never loosens existing settings.** A managed key with no
  harness.lock entry whose on-disk value differs from the profile (e.g. Codex
  `sandbox_mode = "read-only"`, OpenCode `permission.bash = "deny"`) is now a
  conflict instead of being overwritten; `--take-profile` writes the profile,
  `--take-mine` keeps (and pins) the user's value. An equal value is adopted
  silently. Codex `sandbox_mode`/`approval_policy` are emitted only when
  `worker.permission` names a permission profile (Claude already emitted none).
- **Claude Code and Codex get AWG's skill.** With `work.provider: awg` and an
  AWG checkout (`MAGGY_AWG_REPO`), user scope now copies
  `plugins/claude-code/skills/awg` to `~/.claude/skills/awg/` and
  `plugins/codex/skills/awg` to `~/.codex/skills/awg/` (managed skill copies),
  matching OpenCode's `skills.paths` and pi's `skills`. The Phase 1 exit test
  now counts skills an agent loads through its config, not only its skills dir.
- **Dropped regions are removed.** harness.lock now records each region's
  format, scope root and owning agents, and keeps (merges) entries for regions
  outside the current run. A region the profile no longer emits (for example AWG
  wiring after `work.provider: none`, in `~/.codex/config.toml`, `AGENTS.md` and
  `~/.claude.json`) is removed from disk once every agent owning it is in the
  run; an edited one is a conflict. `--agent claude` no longer makes the lock
  forget other agents' regions, so edits to them stay conflicts.
- **User list entries are not conflicts.** Claude `permissions.allow/deny` and
  `hooks.<Event>`, OpenCode `instructions`/`plugin`/`skills.paths` and pi
  `skills` are list regions (`<key>[]`) holding only Maggy's entries; the user's
  own entries beside them are kept and never block apply.
- **Tightening permissions takes effect.** Maggy's earlier Claude rules (tracked
  in harness.lock) are replaced, so switching shell/network/write from `true`
  to allowlist/registries/workspace removes `Bash`, `WebFetch`, `WebSearch`.
- **`--take-mine` is durable.** The lock remembers the profile text the user
  chose over (`base`); later plain applies keep the edit until the profile
  changes, which is then a conflict. `--take-profile` ends the pin. Same for
  skill and pi extension copies.
- **Copies are deleted only with a lock entry.** A user's copy of a managed
  skill (marker included, e.g. `skills/my-python`) is never removed.
- **JSON outside managed keys is byte for byte.** JSON regions are edited in
  place (`harness/json_edit.py`) instead of re-serializing the file, so inline
  arrays, escapes and spacing in the user's keys survive.
- **Installed packages find skills and rules.** `setup.py` bundles the repo's
  `skills/` and `rules/` into `maggy/harness/library` (shipped as package data,
  also through the sdist); `default_sources()` uses the checkout when present,
  else the bundled library.

### Maggy: Phase 0 hardening (review leftovers)

#### Fixed
- **`maggy/review/fp_filter.py`** — the det-fp log line was built by calling
  `.format(title)` on a template that contained the reviewed file's stem, so a file
  named e.g. `src/a{0}b.tsx` crashed the whole review (`ValueError`/`KeyError`). The
  message is now assembled with an f-string; file names and titles are never treated
  as format templates. `deterministic_fp_filter` now takes `(findings, FPFilterRun)`
  instead of four positional arguments.
- **`maggy/services/chat_executor_bridge.py`** — `_poll_session` ended silently when
  an executor session finished as `merge_failed`, so chat users saw no error while
  their work sat unmerged. It now yields an error naming the preserved workspace path.
  The dead `parallel_running` status (no longer produced) was dropped from the
  running set.
- **`maggy/services/orchestrator.py`** — `_settle` called `merge_changes` unguarded,
  so an `OSError` (e.g. git missing, disk full) during the apply escaped `_run_one`
  and lost the subtask result. It now uses `workspace_guard.safe_merge` (the
  executor's guard, formerly `_merge`): any exception counts as a failed merge, the
  workspace is kept and the subtask reports `failed`.
- **`maggy/orchestrator/merge_rollback.py`** — the pre-merge snapshot skipped
  symlinks, so when a 3-way apply conflicted on one file but retargeted a tracked
  symlink cleanly, the rollback left the symlink changed. Snapshots now record a
  symlink's target and restore it, so a failed merge leaves the repo untouched.

#### Security
- **`maggy/api/routes_orchestrator.py`** — `/api/orchestrator/*` (spawn a team,
  cancel a team, list/get teams) had no auth, so in `auth_mode: token` anyone who
  could reach the dashboard could spawn agent teams. The router now carries the same
  `require_auth` (X-API-Key) dependency the core API uses.

#### Changed
- **Tests** — `tests/test_install_script.py` checks the real home from the passwd
  entry (`pwd.getpwuid(os.getuid()).pw_dir`) rather than `~`, which conftest points
  at a temp dir, so the "real HOME untouched" guard now checks the real home. Phase 0
  test files over 10 functions were split (`test_merge_rollback.py`,
  `test_orchestrator_workspace_safety.py`, `test_review_fp_i18n.py`,
  `test_review_fp_flag.py`, shared `merge_helpers.py` and `fp_filter_helpers.py`).

### Maggy: failed merges leave the repo clean; FP-filter config trusted only from base

#### Fixed
- **`maggy/orchestrator/merge.py`, new `merge_rollback.py`** — when `git apply --3way`
  hit a content conflict, `merge_changes` returned False but had already written
  conflict markers and unmerged (`UU`) index entries into the user's checkout. This
  happened for example when `OrchestratorService._settle` merged two sibling subtasks
  that edit the same lines. The paths the patch touches and the index are now
  snapshotted before the apply and restored on failure, so False always means the
  repo is untouched. Workspace patches are built with `--no-renames` so every touched
  path (both sides of a rename) is listed and restored.

#### Security
- **`maggy/review/repo_config.py`, `fp_filter.py`** — `.maggy/review.yaml` was read
  from the local checkout, which is the PR head. A PR could add a config pointing
  `router_files` at any file and so silently drop its own blocking findings (e.g. a
  SQL-injection finding mentioning "unconditionally"). The config is now read only
  from the trusted base branch (`git show origin/<base>:.maggy/review.yaml`). With no
  base ref the filter is a no-op. Locale and router paths must be relative and inside
  the repo: absolute, drive-letter and `..` paths make the config invalid.

### Maggy: test suite and ruff run in CI

#### Added
- **`.github/workflows/maggy-tests.yml`** — runs on every push and pull request:
  Python 3.12, `pip install -e "maggy[test]"`, `cd maggy && python -m pytest tests -q`,
  then `ruff check maggy/maggy`. Hermetic: no secrets, read-only token. Nothing ran
  the maggy suite in CI before.
- **`maggy/pyproject.toml`** — new `test` extra (pytest, pytest-asyncio, ruff, plus
  the `review` extra because review-pipeline tests import `pydantic_ai`), and a pinned
  `[tool.ruff.lint]` baseline (`E9`, `F63`, `F7`, `F82`: syntax errors and undefined
  names). Ruff's newer default rule set flags ~490 pre-existing style issues; widen
  the selection as that backlog is cleaned up.
- **`maggy/tests/test_ci_workflow.py`** — parses the workflow YAML and checks
  triggers, Python version, install/pytest/ruff commands and hermeticity.

### Maggy: PR-review false-positive filter is configured per repo

#### Changed
- **`maggy/review/fp_filter.py`** (moved out of `pipeline.py`) — the deterministic
  false-positive filter no longer hardcodes one client's locale and router paths or
  translation-key prefix. It reads `.maggy/review.yaml` from the reviewed repo
  (`translation_locales`, `translation_key_prefix`, `router_files`; parsed with
  Pydantic in the new `maggy/review/repo_config.py`). With no config, or an invalid
  one, findings pass through unchanged. An equivalent config keeps the old drop
  behaviour (all used keys resolve in every locale; unrouted, pre-existing or
  already-gated components). The refuter prompt and a comment no longer name the
  client either.

### Maggy: telos and e2e-testkit routes require auth and a registered project

#### Security
- **`plugins/telos`, `plugins/e2e-testkit`** — every route (`/api/telos/status`,
  `/api/testkit/run|drift|intent|history`) was unauthenticated and ran
  pytest/benchmarks in any `project_dir` passed in. Both routers now use the
  core `X-API-Key` check (new `require_auth` dependency in `maggy/api/auth.py`),
  and `project_dir` must realpath-resolve inside a configured `projects[].path`
  or `codebases[].path` (new `maggy/api/project_guard.py`). Anything else
  (`../` traversal, symlinks out, sibling-prefix dirs, `.`, empty) gets 400/403
  before any subprocess starts. The sandbox applies in `auth_mode=local` too.
  Callers must now pass `project_dir` explicitly; the testkit's old `.` default
  is rejected unless the server's working directory is a registered project.

#### Fixed
- **`plugins/e2e-testkit`** — `ProjectDetector` called an undefined
  `_safe_rglob`, so every testkit route crashed on Python projects. It is now
  defined and returns `[]` for a missing source dir.

### install.sh works on a clean HOME

#### Fixed
- **`install.sh`** — wrote `~/.claude/.bootstrap-dir` before creating
  `~/.claude`, so under `set -e` a fresh install aborted at once. Directory
  creation now runs first; install behaviour is otherwise unchanged.
  Covered by `maggy/tests/test_install_script.py`, which runs the installer
  against an empty temp HOME with a minimal PATH.

### Maggy: isolated workspaces no longer lose agent work

#### Fixed
- **`maggy/orchestrator/merge.py`** — the patch diffed `HEAD@{1}..HEAD`, so
  only the last commit was merged and uncommitted edits were dropped. It now
  diffs everything since the workspace's base commit (merge-base with the
  repo HEAD), including uncommitted and untracked non-ignored files, and
  returns `False` on any git failure instead of claiming success.
- **`maggy/services/executor.py`** — parallel mode backgrounded a team, then
  the `finally` block deleted the workspace and released locks while the
  team still ran. Parallel mode is disabled (logged warning, sequential TDD
  path) until the AWG runner replaces it. The merge result is now checked:
  a workspace is deleted only after a successful merge; otherwise it is kept
  and its path recorded as `preserved_workspace` (status `merge_failed` when
  a completed run could not be merged).
- **`maggy/services/orchestrator.py`** — `_run_one` deleted subtask
  workspaces without merging. Successful subtasks are merged first and
  cleaned only when the merge succeeds; failed or unmerged subtasks keep
  their workspace, reported in `Result.artifacts["workspace"]`.

#### Added
- **`maggy/services/workspace_guard.py`** — merge-or-keep decision for
  executor sessions.
- **`tests/test_merge_capture.py`**, **`tests/test_workspace_safety.py`**.

### Maggy: council default models are no longer routing tiers

#### Fixed
- **`maggy/services/model_registry.py`** — `build_routing_tiers()` promoted
  every council default model whose id is not a router tier name to a
  "custom" tier covering complexity 0-10. `qwen3` (council tier 0) therefore
  won every routing decision, and deepseek/kimi/codex leaked into the ladder
  even under US sovereignty. Only user-added models become extra tiers now;
  `claude-fable-5` (the council chief) joins the built-in model ids.

### Maggy test suite: green, hermetic, no PYTHONPATH

#### Added
- **`maggy/mnemos/__main__.py`** — `python -m maggy.mnemos` runs the Mnemos
  CLI (`maggy.mnemos.cli`). Its CLI tests ran `python -m mnemos`, which only
  ever resolved when a separate `mnemos` package was installed.
- **`tests/test_suite_hermetic.py`** — guards the isolation below.

#### Changed
- **`maggy/pyproject.toml`** — `[tool.pytest.ini_options]` with
  `pythonpath = ["../scripts"]`, `testpaths` and the asyncio loop scope, so
  `cd maggy && .venv/bin/python -m pytest tests` works without PYTHONPATH.
- **`tests/conftest.py`** — before any maggy import, HOME becomes a temp dir
  (no reads of `~/.maggy`, `~/.claude/council.yaml` or `~/bin`), `~/bin` is
  dropped from PATH, and provider API keys are hidden.
- Tests updated to current behaviour: the provider-config tier ladder
  (`local`, `gemini-flash-lite`, `<flash>`, `<pro>`, `claude`); the
  ollama → kimi → deepseek → Claude escalation cascade; REPL input through
  `input()` rather than `Prompt.ask`; `raw["blast_score"]` in chat tasks; the
  autonomous-agent grounding text; and the orchestrator taking blast >= 7 to
  the parallel path. CLI discovery, model registry and Telos conformance
  tests use fake binaries and shims, so they no longer need installed CLIs.
  52 failures → 0. No tests were deleted or skipped.

## [6.67.0] - 2026-10-13

### Routing hook: no more qwen3 tier, missing tools fall back to Claude

#### Changed
- **`hooks/route-task-hook`** — the QWEN delegation tier is gone. Trivial
  lookups now classify as the flash tier or are handled directly; nothing
  routes to `~/bin/qwen3` any more.
- **`hooks/route-task-hook`** — before emitting a delegation instruction the
  hook checks that the tier's wrapper exists (the resolved flash/pro binary,
  `~/bin/gemini-api`, `~/bin/gemini-cli`, `~/bin/kimi`, `~/bin/grok`, `codex`
  on PATH). A missing wrapper yields `ROUTING DECISION: CLAUDE (fallback from
  <tier>)` telling Claude to do the task itself, without the PLAN FIRST
  ceremony or the delegation contract. Previously the hook ordered delegation
  to a binary that was not installed and Claude had to notice the failure.
- A cached tier the current hook no longer knows (for example `QWEN` left in
  `~/.claude/routing-cache.json` by an older version) is discarded instead of
  being replayed.

#### Added
- `tests/test_route_task_hook.py` — runs the real bash hook with a fake HOME
  and dead Ollama endpoint to cover the fallback, the stale cache and the
  installed-wrapper paths.

## [6.66.0] - 2026-09-24

### Verify-cascade — verification-gated model escalation (optional TypeSafe)

#### Added
- **`skills/verify-cascade/`** — makes maggy's routing output-aware: run a cheap model,
  verify its output with a decomposed per-field battery (narrow "bad = true" questions,
  aggregated with `max`), and escalate to a strong model only when a flag fires. The
  cheap rung handles easy items for near-free; only flagged items pay for the strong model.
- **Pluggable verifier** (`verify_cascade.py`): `LocalVerifier` is the **default and runs
  entirely on a cheap local/CLI model — no data leaves the machine**; `TypeSafeVerifier`
  is an **opt-in** adapter for TypeSafe's hosted `jev` model.

#### Notes / privacy
- TypeSafe support is **off by default**: `TypeSafeVerifier` will not construct without
  `TYPESAFE_API_KEY`, and when used it **sends `source_text` + `schema` + `extraction` to
  api.typesafe.ai** (a third party). Documented in the skill. Nothing is sent unless you
  set the key and select the `typesafe` verifier.
- Pattern adapted from TypeSafe's public SDE-cascade cookbook; rebuilt so the verifier is
  pluggable with a private local default.
- Skill count 72 -> 73.

---

## [6.65.1] - 2026-09-22

### Fixed
- **`skills/security-audit/validate_findings.py`** — close two integrity holes
  (CodeRabbit review on #67): a `confirmed` finding now requires **both**
  `found_by` and `validated_by` (an absent `found_by` no longer lets the
  finder≠validator rule pass silently), and the validator now enforces the
  published `report-schema.json` shape (id pattern `SA-<digits>`, title length,
  `location.line` integer ≥ 1) before the integrity checks, instead of only the
  enums.

---

## [6.65.0] - 2026-09-22

### Security audit skill — structured, adversarial, evidence-grounded

#### Added
- **`skills/security-audit/`** — a full security-audit methodology (not a
  checklist): six phases (recon → coverage-led hunting → finder≠validator
  validation → machine-readable findings → record verification → target-neutral
  report), a vuln-class taxonomy, and anti-patterns. Reuses `council-review`
  (adversarial validation), `cpg-analysis` (Joern/CodeQL static taint), and
  `agent-teams`/`polyphony` (isolated parallel hunters). Methodology inspired by
  Cloudflare's public security-audit-skill, rebuilt on maggy's own pieces.
- **`report-schema.json` + `validate_findings.py`** — a findings schema and a
  zero-dependency integrity validator that enforces the honest-audit rules: unique
  ids, valid enums, and every `confirmed` finding has a file:line location, an
  attack scenario, and a `validated_by` that differs from `found_by`.

- **Default part of the harness** — `commands/initialize-project.md` copies
  `security-audit/` into **every** project at init (alongside `security/`), so
  the audit methodology ships by default, not opt-in.

#### Changed
- **`skills/security/SKILL.md`** — points to `security-audit` (audit) and
  `/security-review` (quick branch pass); clarifies `security` is preventive.
- **`skills/base/SKILL.md`** — Definition of Done now calls for a security-audit
  pass on security-critical changes.
- Skill count 71 → 72 (README / GETTING_STARTED).

---

## [6.64.1] - 2026-09-19

### Fixed
- **`skills/demo-video/`** — the archive-naming example now allocates the next
  *free* index with a no-clobber loop instead of `wc -l + 1`, which reused an
  index (and overwrote an existing mp4) when an earlier file had been deleted.
  Addresses a CodeRabbit review finding on #64.
- **README** — added "visual validation" to the Bootstrap skills feature list;
  normalized the `### Fixed` changelog heading level.

---

## [6.64.0] - 2026-09-19

### Visual validation as a default for web projects

#### Added
- **`skills/demo-video/`** — captioned Playwright walkthrough that records a real
  user flow, doubles as a passing E2E test, and produces a stakeholder proof mp4.
  Now ships with the harness (previously a personal skill).
- **Web projects get it by default** — `commands/initialize-project.md` copies
  `demo-video/` into React Web, Full Stack, and PWA projects at init, alongside
  the web skills.

#### Changed
- **`skills/base/SKILL.md`** — the Definition of Done now requires a `demo-video`
  walkthrough as the evidence for any user-facing web flow (next to screenshots
  for UI changes and artifacts for generated content).
- **`skills/react-web/SKILL.md`** — new "Visual validation (default for web)"
  section relating `demo-video` (flow proof), `visual-validation`
  (screenshot-regression), and `playwright-testing` (behavior).
- Skill count 70 → 71 (README / GETTING_STARTED).

---

## [6.63.0] - 2026-09-19

### DataForSEO skill — keyword & SERP research

#### Added
- **`skills/dataforseo/`** — a user-invocable skill for grounding naming / SEO
  decisions in real Google Ads data (monthly search volume, competition, CPC,
  keyword ideas) via the DataForSEO API. Ships a small env-auth helper
  (`dataforseo.py`) with `whoami` / `volume` / `ideas` subcommands, guidance on
  reading the results for naming, cost/batching etiquette, and an endpoint map.
  Credentials are read from the environment only — never hardcoded or logged.
- Corrected the skill count in the README / GETTING_STARTED (67 → 70).

---

## [6.62.0] - 2026-09-19

### Codex dual auth — ChatGPT subscription *or* API key

#### Added
- **`scripts/model_routing.py`** — `codex_auth()` detects both Codex auth paths:
  a ChatGPT-subscription CLI login (`~/.codex/auth.json`, `auth_mode=chatgpt`)
  and a real OpenAI API key (`sk-…`). `codex_mode()` resolves the effective
  path (explicit `codex_auth` pref, else auto: API key first so Codex can back
  a Claude Code model, else subscription for CLI delegation).
- **`codex-status` / `set-codex-auth` CLI verbs** — inspect what's available
  and pin `auto | subscription | api_key`; stored as `codex_auth` in
  `~/.claude/model-config.json`.
- **`commands/model-config.md`** — documents both auth paths, what each unlocks,
  and the hard limit that Codex-as-a-model always needs the API key.
- **`tests/test_model_routing.py`** — coverage for subscription/api-key/none
  detection, the `srt_` dev-key exclusion, and mode resolution/preference.

#### Fixed
- **`detect_available`** no longer marks Codex usable off a `srt_` srooter dev
  key; it now requires a real API key or a subscription login.

#### Notes
- The ChatGPT subscription can only drive CLI delegation (`codex exec`); it
  cannot back a Claude Code model, because OpenAI has no Anthropic endpoint and
  the subscription OAuth is locked to OpenAI's own client.

---

## [6.61.0] - 2026-09-19

### Direct-provider launchers — run Claude Code straight on DeepSeek / GLM / Kimi

#### Added
- **`scripts/model_routing.py`** — a `DIRECT` map and `direct_config()` /
  `write_launcher()` for the three providers that expose a native
  Anthropic-compatible endpoint (DeepSeek `api.deepseek.com/anthropic`,
  Z.ai GLM `api.z.ai/api/anthropic`, Moonshot Kimi `api.moonshot.ai/anthropic`).
- **`write-launcher <backend>` / `write-launchers` CLI verbs** — generate
  `~/bin/claude-deepseek` / `claude-glm` / `claude-kimi`. Each wrapper exports
  `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_MODEL` (resolving
  the provider key from your env) and `exec`s `claude`, so that session runs
  directly on the provider with no srooter hop. Plain `claude` is untouched.
- **`commands/model-config.md`** — documents `/model-config <backend> --direct`
  and the launchers.
- **`tests/test_model_routing.py`** — coverage for `direct_config` (incl. that
  codex/minimax/unknown return `None`) and `write_launcher` (executable file,
  correct endpoint/model, non-direct rejection).

#### Notes
- **Codex is not direct-capable**: OpenAI has no Anthropic Messages API, so
  Codex stays routed through srooter's `/anthropic → /v1/responses`
  translation. No `claude-codex` launcher is generated.

---

## [6.60.0] - 2026-09-19

### Switch Claude Code to a pre-configured backend from within Claude Code

#### Changed
- **`scripts/model_routing.py`** — `MODELS` now maps the switchable backends to
  their real srooter aliases: `deepseek → deepseek-pro`, `kimi → kimi-k3`,
  `codex → codex` (was a no-op), and a new `glm → glm-5.3` entry. So
  `/model-config <backend>` moves Claude Code onto the intended model instead of
  a base/undefined alias.
- **`apply_to_srooter`** now rewrites **both** real-coding routes
  (`long_context` *and* `substantive`) in `srooter.yaml`, not just
  `long_context` — substantive coding traffic follows the chosen backend too.
  `trivial` and `think` are left untouched.
- **`PRIMARY_PRIORITY`** extended to include `glm` and `codex`.

#### Added
- **`commands/model-config.md`** — documents the four pre-configured backends
  (DeepSeek Pro, Kimi K3, GLM 5.3, Codex), their srooter aliases, the required
  provider keys, and that a switch needs a srooter restart + fresh session.
- **`tests/test_model_routing.py`** — coverage for the new backend→alias
  mappings and for the dual-route (`long_context` + `substantive`) rewrite.

---

## [6.59.0] - 2026-09-08

### Context shunt — cheap reads, small context (+ a tightened read gate)

#### Added
- **`bin/bulk-read`** — hands large / multi-file reads to a cheap worker model
  (default `deepseek --flash`, configurable via `SHUNT_MODEL`) and returns a
  compact, cited summary; the raw files never enter Claude's context. Prints a
  token-savings report to stderr. Inspired by Spotify's "shunt" plugin.
- **`hooks/context-shunt-gate`** — configurable, **size-aware** PreToolUse hook
  that supersedes the old size-blind `cbm-code-discovery-gate`. Steers reads of
  large files (code *or* logs/generated output, via `Read` or a `cat`/`head`/
  `tail` Bash call) to `bulk-read`, and keeps the once-per-session code-graph
  nudge. Fail-open (a bug can never wedge the session).
- **`skills/context-shunt/SKILL.md`** — when to read raw vs shunt vs graph.
- **`templates/shunt.conf`** — config seeded to `~/.claude/shunt.conf`:
  `SHUNT` (on/off), `SHUNT_MIN_LINES` (default 350), `SHUNT_MODE`
  (`suggest`/`block`/`off`, default `suggest` — nudges, never blocks),
  `SHUNT_GRAPH_NUDGE`, `SHUNT_MODEL`.

#### Changed
- `templates/settings.json` registers `context-shunt-gate` on `Read|Grep|Glob|Search`
  and `Bash`, so `/initialize-project` projects get it. `install.sh` ships the
  hook, `bulk-read`, and the config (non-destructively).

This is deliberately orthogonal to srooter / `route-task` (which route whole
turns): the shunt only trims what a single tool call pulls in when the turn is
already on the main model — the one slice whole-turn routing can't reach.

#### Tests
- `tests/test_context_shunt.py` — 15 cases: fail-open on bad input, block/suggest/off
  modes, small-read passthrough, Bash `cat` gating, non-read commands ignored, the
  graph nudge, and `bulk-read` guards + corpus piping.

---

## [6.58.2] - 2026-09-08

### Skill frontmatter — five skills now carry name/description (fixes #55)

#### Fixed
- **`skills/autonomous-testing`, `skills/build-in-public`,
  `skills/external-model-delegation`, `skills/model-routing`,
  `skills/visual-validation`** — added YAML frontmatter (`name`, `description`,
  `when-to-use`, `user-invocable`, `effort`) to each `SKILL.md`. They previously
  started at an `#` heading with no frontmatter, so Claude Code had no `name` or
  `description` to trigger them, and `skill_lint --fail-on error` (CI) was red.
  `PYTHONPATH=scripts python -m skill_lint --fail-on error skills/` is now green
  (0 errors).

---

## [6.58.1] - 2026-08-21

### Retired Claude model IDs replaced in skill docs

#### Changed
- **`skills/agentic-development/SKILL.md`, `skills/llm-patterns/SKILL.md`,
  `skills/ms-teams-apps/SKILL.md`, `skills/reddit-ads/SKILL.md`** — 16 occurrences of
  `claude-sonnet-4-20250514` replaced with `claude-sonnet-4-6`. That ID was retired on
  June 15, 2026, so the copied examples fail against the API.
- **`skills/ai-models/SKILL.md`** — the active model catalog carried three retired IDs.
  `opus4` now maps to `claude-opus-4-6`, `sonnet4` to `claude-sonnet-5`, and `haiku` to
  `claude-haiku-4-5-20251001`. The model selection guide had the same stale Haiku entry
  plus its old price, both corrected to Haiku 4.5 at $1/$5 per 1M tokens.

`sonnet` and `opus` are untouched: `claude-sonnet-4-5-20250929` and
`claude-opus-4-5-20251101` are still active per Anthropic's deprecation page.

---

## [6.58.0] - 2026-08-18

### Changelog discipline — every commit ships a CHANGELOG entry

#### Added
- **`rules/changelog.md`** — new conditional rule installed to `~/.claude/rules/`:
  every commit that changes behaviour, config, docs, or dependencies MUST update a
  `CHANGELOG.md` in the same commit (Keep a Changelog format, one entry per commit,
  staged with the code). Formatting-only and comment-typo changes are exempt.
- **`/initialize-project` seeds the rule into every project** — the generated
  `CLAUDE.md` now carries a "Changelog — Required for Every Commit" section, and
  init seeds a root `CHANGELOG.md` with a `[Unreleased]` block so the discipline
  holds from the first commit.

#### Changed
- Bootstrap `CLAUDE.md` Git Workflow now requires a `CHANGELOG.md` update in the
  same commit as the code.

---

## [6.57.0] - 2026-07-11

### GPT-5.6 council support, GLM executor, `/route-eval`, key/routing config

#### Added
- **GPT-5.6 support on the review council** — the multi-model reviewer now
  includes **GPT-5.6 Terra** (`gpt-5.6-terra`, OpenAI Responses API) as a
  first-class member alongside GPT-5.5-pro. It reviews with tool access and
  intentional reasoning effort — `high` by default (per OpenAI's GPT-5.6 guidance
  that code review is a high-value case), overridable with `OPENAI_TERRA_EFFORT`
  (`none`|`low`|`medium`|`high`|`xhigh`|`max`) and `OPENAI_TERRA_MODEL`. Auto-joins
  the council whenever `OPENAI_API_KEY` is set.
- **`bin/glm`** — Zhipu GLM / BigModel CLI (OpenAI-compatible), matching the
  `together`/`groq` wrappers. Self-loads `~/.maggy/.env` so keys set in the Maggy
  Settings UI work without shell sourcing. Configurable via `GLM_MODEL`,
  `GLM_BASE_URL` (defaults to `open.bigmodel.cn`; use `api.z.ai` for international).
- **`/route-eval` slash command** — evaluates a project's structure and past
  Claude/Codex routing history, then recommends a private per-machine routing
  profile (show-then-confirm). A `simple` project can route everything through
  one cheap model (e.g. GLM) while security-sensitive paths always escalate to
  Claude. Fully hand-editable afterward.
- **API keys + routing configurable from the Maggy UI** — a Settings "API Keys"
  card (set/unset any provider key, masked) and a "Data Sovereignty & Routing"
  card. Keys live in `~/.maggy/.env` (0600), shared with the CLI wrappers.

See `maggy/CHANGELOG.md` [6.57.0] for the full detail (API-key store internals,
per-project routing engine, and the 0600 + injection-guard credential hardening).

---

## [6.56.0] - 2026-07-01

### Visual validation framework + protocol hijack fix

#### Added
- **Visual regression tests** — golden-image comparison of the Maggy dashboard
  via Playwright + Pillow + numpy. `tests/visual/` mirrors the TDD RED→GREEN
  cycle for UI changes. Auto-skips without the `[visual]` extra installed.
- **Protocol matcher fix** — "implement it, test it, then merge it" no longer
  hijacked to run-only-tests. Build/multi-step intent vetoes protocol matches.

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) for full detail.

### Parallel chats per project — worktree-isolated

#### Added
- **Multiple chats per project, each in its own git worktree + branch.** The
  first chat runs on the project's main tree; every additional chat gets its own
  `git worktree` on a fresh `maggy/<id>` branch, so parallel chats never collide
  on files or branches. The backend auto-isolates a second chat even without the
  flag. Deleting an isolated chat removes its worktree (branch + commits kept).
  See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) for detail.

## [6.53.0] - 2026-06-21

> Published to PyPI as **`maggy-harness` 0.2.1** (together with 6.52.0). The
> changelog tracks feature versions; the PyPI package uses semver from 0.1.0.

### Backup / restore / diff — safe, reversible installs

#### Added
- **`maggy backup` / `maggy restore` / `maggy diff`** — snapshot your existing
  files before installing, roll back anytime, and preview exactly what a
  bootstrap would add or change vs your current setup. `maggy bootstrap`
  auto-backs-up first, so your pristine pre-Maggy state is always recoverable.
  Backups (settings.json + only the files Maggy would overwrite) live in
  `~/.maggy/backups/<timestamp>/`. See [UNINSTALL.md](UNINSTALL.md).

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) for the full per-release detail.

## [6.52.0] - 2026-06-21

### Uninstall path (#28)

#### Added
- **`maggy uninstall`** + **[UNINSTALL.md](UNINSTALL.md)** — a clean, reversible
  way to undo what the installer placed. Symmetric with `bootstrap`/`install.sh`:
  it removes only the bundled asset names (skills, commands, hooks, rules,
  templates, `~/bin` model wrappers, plugins, and the install marker), so your
  own files in `~/.claude`, `~/bin`, and `~/.maggy` are untouched. Dry-run by
  default; `--yes` to remove. The guide also covers the deliberately-left bits
  (the pip package, `~/.maggy` data, `settings.json` hooks, srooter routing).

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) for the full per-release detail.

## [6.44.0] - 2026-06-11

### Maggy: zero-config onboarding + architecture hardening

#### Onboarding — it just works out of the box
- **First boot auto-configures.** `maggy serve` on a fresh install discovers your
  local git repos, writes a clean config (keyless local mode), and **auto-opens
  the dashboard** pointed at your real repos. No placeholder `your-org` config,
  no hand-editing YAML, no API keys required to start. `install.sh` and
  GETTING_STARTED simplified to a 2-step, keys-optional flow.

#### Architecture hardening (council of experts, chief Claude Fable 5)
- **T1** gate the self-tuning router (shadow + outcome-validity + approval + audit).
- **T2** unify isolation: pinned, golden-tested CLI manifests (no `--help`
  parsing for known CLIs) + the autonomous pipeline now runs tool ops inside a
  Docker container, not on the host.
- **T4** SQLite `busy_timeout` on the concurrent multi-agent stores + an explicit
  memory-precedence rule (cikg > mnemos > history).
- **Claude Fable 5** wired as chief of the council across Maggy and bootstrap.

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) (6.46.0–6.49.0) for the full detail.

## [6.43.0] - 2026-06-10

### /initialize-project sets up model routing + council for every project

#### Added
- **`/initialize-project` Step 7d** — seeds the shared followed-model config
  (`~/.claude/model-config.json`, auto-detected) and the council of experts
  (`~/.claude/council.yaml`, chief `claude-fable-5`) if missing. Both are global,
  so a fresh machine is ready to route tasks to the cheapest capable model and
  convene the council on any project.
- `scripts/model_routing.py ensure` — CLI command to create-if-missing the
  followed-model config and print the primary.

## [6.42.0] - 2026-06-09

### Council Chief: Claude Fable 5

Claude Fable 5 (`claude-fable-5`, GA 2026-06-09) is now chief of the council of
experts across the stack: it leads every review panel and casts the deciding
synthesis.

- `~/bin/claude-fable-5` wrapper (Anthropic Messages API).
- council-review skill + `~/.claude/council.yaml`: `chief: claude-fable-5`, added
  as lead reviewer in plan/review/architecture.
- Maggy: `CouncilConfig.chief`, model registry + health allowlist entries.
- srooter: `council_chief` + `claude-fable-5` model + risk validator.

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) (6.46.0) for the Maggy detail.

## [6.41.0] - 2026-06-08

### Build-in-Public Reddit Agent + Gemini Search Fix

#### Added
- **Reddit is the third build-in-public channel** (with LinkedIn + X). The
  narrative engine generates a Reddit-native self-post and submits it directly
  (Reddit isn't a Buffer service).
- **Autonomous subreddit** — Maggy picks the target itself (defaults to
  r/ClaudeCode / r/buildinpublic); no manual config required.
- **Reddit Agent — voice + replies** (`plugins/build-in-public/voice.py`,
  user-definable under `config.voice`): every post/reply is run through
  `no_em_dash`, `strip_markdown` (Reddit-safe plain text), and optional human
  `typos`. A heartbeat monitors comments on Maggy's own posts and replies once
  each, rate-limited, never to itself.
- **Credential reuse** — Reddit creds resolve from the environment, then a
  sibling ideaminer checkout; auth supports refresh-token and script-app
  (username/password) grants.

#### Fixed
- **Gemini `--pro-search`** (`bin/gemini-api`) — grounding was sent to the
  OpenAI-compat endpoint (400 `Unknown name "google_search"`) with a
  non-existent model id. Now routes to the native `generateContent` endpoint on
  `gemini-3.5-flash`, where the `google_search` tool is valid.

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) (6.43.0–6.45.0) for the full Maggy
detail: iCPG dashboard auto-build, orchestrator image fix + isolated worktrees
+ isolation modes, the unsandboxed-agent security fix, and the Reddit agent.

---

## [6.40.0] - 2026-06-04

### Followed-Model Routing — One Choice, Every Layer (srooter + hooks + Maggy)

A single "followed" (primary) model is configured once and respected across the
srooter gateway, the route-task hooks, and Maggy — auto-detected from the
machine, overridable in onboarding. Smart mode keeps trivial/cheap asks local.

#### Added
- **Shared source of truth** — `scripts/model_routing.py` writes/reads
  `~/.claude/model-config.json` (`primary`, `classifier`, `mode`, `analyze`).
  `detect_available()` probes provider keys (env + `~/.zshrc` + srooter env),
  `~/bin` CLI wrappers, and local Ollama; `ensure()` auto-creates the config;
  `apply` syncs the primary into srooter's `long_context` route. CLI:
  `detect | show | get | set-primary | set-analyze | apply`. 12 tests.
- **Onboarding picker** — `scripts/onboard.sh` collects the MiniMax key and
  asks which detected model to follow; `/model-config` views/changes it anytime.
- **route-task hook** — additively injects `FOLLOWED MODEL: <primary>` into
  routing context (tier classification untouched; explicit overrides win).
- **MiniMax pre-analysis (opt-out)** — when `analyze: true` (default), the hook
  sends each prompt to MiniMax for a terse INTENT/SCOPE/RISKS/APPROACH brief
  injected into context so Claude executes accordingly; fails open, capped at
  `MINIMAX_TIMEOUT=20s`, toggle via `set-analyze`.
- **MiniMax wired into srooter** — `MINIMAX_API_KEY` activates the
  pre-configured `minimax-m2.5` main coding route; `~/bin/minimax` wrapper.

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) (6.43.0) for the Maggy-side changes.

---

## [6.39.0] - 2026-06-04

### Mnemos: Claude Transcript Ingestion + Per-Session Haziness Scoring

A new memory dimension — Mnemos now ingests Claude Code session transcripts and
scores how much each session *struggled*, so fatigue can be measured from real
history rather than only live signals.

#### Added
- **Transcript ingester** (`scripts/mnemos/claude_log.py`) — parses the per-session
  JSONL under `~/.claude/projects/` into `claude_sessions` / `claude_turns`.
  Idempotent (resumes via `last_line_offset`, `INSERT OR IGNORE` on
  `(session_id, idx)`). Stores **only** structural fields + a redacted 200-char
  preview — never full content.
- **Haziness scoring** (`scripts/mnemos/haziness.py`) — weighted 5-dimension score
  (correction density, redo ratio, first-try error rate, orphan tool-use,
  backtracking) with `clear`/`cloudy`/`hazy`/`lost` bands and dominant-dimension
  reporting, persisted to `claude_haze`.
- **Secret redaction** (`scripts/mnemos/redact.py`) — ordered patterns
  (PEM/JWT/Anthropic/Stripe/OpenAI/GitHub/AWS/credential) applied to every text
  field before it is persisted.
- **CLI** — `mnemos ingest-claude` (`--all` / `--session` / `--slug` /
  `--transcript`) and `mnemos haze` (`--recent` / `--session` / `--explain`).
- **Stop hook** (`templates/mnemos-stop-ingest.sh`) — ingests + scores the
  just-closed session on exit; never blocks the user; per-project opt-out via
  `touch .mnemos/claude-log.disabled`.
- **Session-hooks installer** (`scripts/install_session_hooks.py`) — idempotent,
  non-destructive merge of the session-hook chain into a project's
  `.claude/settings.json`. Wired into `/initialize-project` (new Step 7c) and
  shipped by `install.sh`.

#### Fixed
- **Schema migration for existing databases** — `MnemosStore.ensure_schema()`
  applies the schema idempotently so pre-existing `.mnemos/mnemo.db` files gain
  the new `claude_*` tables. Previously the first ingest on an existing DB failed
  with `no such table` (and the Stop hook swallowed it silently).

#### Hardened
- `install.sh` now `chmod +x` **all** `~/.claude/templates/*.sh` hook scripts
  (previously only two were made executable).

#### Tests
- 52 new tests covering ingestion, migration, redaction, idempotency, the two
  CLI commands, and the session-hooks installer. ruff + mypy clean.

---

## [6.38.1] - 2026-05-26

### Maggy: Model Health + Dashboard Regression Guards

#### Added
- **Model health checker** — parallel ping of all configured models with allowlist/blocklist security, timeout handling, latency tracking
- **Sidebar structure tests** — regression guards for tab/pane consistency, catches stale HTML after dashboard changes
- **Project scoping tests** — verifies JS functions pass project keys to API endpoints (inbox, team, cortex, memory, plugins)
- **Routes models tests** — structural checks for model/health/council API endpoints
- 30 new tests across 4 test files

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) for detailed changes.

---

## [6.38.0] - 2026-05-25

### Maggy: Council of Experts — Multi-Model Deliberation + Auto-Execution Gating

3-round deliberation engine where AI models independently evaluate, cross-examine each other's feedback, and reach consensus. Approved changes are gated through blast radius analysis (file count, subsystem boundaries, test coverage) and validation classification (objective vs subjective). Only low-blast objective changes auto-execute; critical paths always require human review.

#### Added
- **Council deliberation** — async parallel reviewer queries, 3 rounds max (independent → cross-examine → final)
- **Blast radius analyzer** — severity scoring (low/medium/high/critical), auth/UI/API detection
- **Executor gate** — decision matrix with 4 actions: AUTO_EXECUTE, AUTO_WITH_ROLLBACK, AUTO_WITH_NOTIFY, HUMAN_REVIEW
- **Audit log** — SQLite WAL persistence for all council decisions
- **Council config** — YAML-based reviewer panels (plan, review, architecture), 13-tier model registry
- 62 new tests across 6 test files

#### Fixed
- Build-in-public plugin: PluginManifest dataclass compatibility (was calling `.get()` on a dataclass)
- Dashboard: project-scoped activity filter, plugin list improvements

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) for detailed changes.

---

## [6.37.0] - 2026-05-24

### Maggy: Skill Protocols — Intent-Driven Execution

When a user says "push to git", Maggy now detects the intent, matches it to a **protocol** (YAML-defined workflow), and executes the steps: lint → test → stage → commit → push. Each step streams results in real-time with pass/fail status. If a required step fails, the protocol aborts.

#### Added
- **Protocol system** — YAML-defined workflows in `maggy/skills/protocols/`
- **Intent matcher** — matches user messages to protocol triggers (longest-match wins)
- **Protocol executor** — runs steps sequentially with condition checks, variable substitution, and abort-on-failure
- **AI-generated commit messages** — protocols with `requires: message` auto-generate via DeepSeek Flash
- **3 built-in protocols**: `git-push` (lint→test→stage→commit→push), `run-tests` (lint→typecheck→pytest), `create-pr` (test→push→gh pr create)
- **Frontend rendering** — protocol steps show as checklist with expandable output
- 24 new tests across 4 test files (models, loader, matcher, executor)

#### Architecture
- Protocols checked BEFORE LLM routing — if intent matches, protocol runs instead of chat
- YAML protocols are extensible — drop a `.yaml` file in `protocols/` and it's live
- LLM fallback for everything that doesn't match a protocol

---

## [6.36.0] - 2026-05-24

### Maggy: Unified Chat Pipeline + Cortex: Modular Edge Extraction

**Maggy** — Unified chat pipeline with real-time streaming, CLI session refresh, URL-based project routing, message persistence for all backends, and pipeline logging dashboard.

**Cortex** — Modular edge extraction (Python AST, TypeScript regex, Git co-change), cyclomatic complexity scoring, and expanded structure tool tests.

See [maggy/CHANGELOG.md](maggy/CHANGELOG.md) for detailed Maggy changes.

---

## [6.35.0] - 2026-05-24

### Telos -- Intent-Grounded Testing Framework

Replaced fragile AI subprocess calls in e2e-testkit with **[Telos](https://github.com/alinaqi/alinaqi/blob/main/docs/Telos_RFC_v1.1.md)**, an intent-grounded testing framework backed by **[Cortex MCP](cortex-mcp/)**. Three scoring planes, multiplicative IFS formula -- a zero in any plane collapses the total score. Telos reads Cortex's `reasons`, `drift_events`, `symbols`, and `edges` tables directly via read-only SQLite.

#### IFS (Intent Fidelity Scale)

| Plane | Metric | Source |
|-------|--------|--------|
| F1 -- Conformance | `passed / total` tests | pytest/vitest subprocess |
| F2 -- Validation | drift severity | Cortex `drift_events` table |
| F3 -- Integrity | IF-3 to IF-8 checks | Cortex `reasons` + `symbols` + `edges` |
| **IFS** | **F1 x F2 x F3** | Multiplicative -- all planes matter |

#### Integrity Checks (Plane 3)

- **IF-3** Orphan symbols (no reason edges)
- **IF-4** Empty contracts (no pre/post/invariants)
- **IF-6** Stale reasons (proposed > 7 days, never fulfilled)
- **IF-7** Scope sprawl (reason scopes > 10 files)

#### Added
- `plugins/telos/` -- full plugin: models, cortex_reader, 3 planes, IFS scorer, routes, manifest
- `CortexReader` -- read-only SQLite from `.cortex/cortex.db` (no MCP overhead)
- `/api/telos/status?project_dir=.` -- IFS breakdown endpoint
- `project.connected` hook -- auto-computes IFS on project open
- Graceful degradation -- no Cortex DB means F2=F3=1.0, IFS = F1 only
- 55 new tests across 7 test files (models, reader, planes, scorer, integration)

#### Fixed
- `test_cli_chat.py` stale import -- `cwd_project` moved to `cli_context`, test still pointed at `cli_chat`
- `chat_stream.py` whitespace bug -- `--resume` accepted whitespace-only session IDs
- Plugin hook wiring gap -- manifest `hooks` were declared but never subscribed by `PluginManager`
- `project.connected` emission -- added to `create_session`, `auto_connect`, `preload_sessions`

#### Architecture
- Telos reads Cortex directly (sync SQLite, `PRAGMA query_only=ON`) -- same monorepo, zero MCP overhead
- Per-reason drift severity capped at 1.0 (council feedback: prevents one noisy reason from dominating F2)
- `e2e-testkit` kept during transition per council recommendation

---

## [6.34.0] - 2026-05-23

### LLM-First Input Architecture + Cortex Integration

Redesigned Maggy's input routing to be strictly LLM-first. Added Cortex MCP as unified code intelligence layer.

#### Changed
- `!` prefix for shell commands -- explicit opt-in, no heuristic word lists
- `/` prefix for slash commands
- Everything else goes to LLM -- no word lists, no regex gatekeeping
- Pi-direct routing for non-Claude models (deepseek, kimi, qwen, gemini, codex, grok)

#### Fixed
- Thinking block loop (`Invalid signature in thinking block`) -- stale `claude_session_id` tracked with `session_cleared` flag
- Project switch -- chat window now resets session and loads correct project
- Natural language treated as commands -- removed all hardcoded word lists

---

## [6.33.0] - 2026-05-23

### Cortex MCP — Full Edge Parity + Cyclomatic Complexity

Cortex now **exceeds** codebase-memory-mcp on both coverage (+40% symbols) and depth (+24% edges).

#### Added
- **10 edge types** fully operational: CALLS, IMPORTS, DEFINES_METHOD, USAGE, TESTS, WRITES, ASYNC_CALLS, HANDLES, RAISES, HTTP_CALLS
- **Python edge extraction** (`python_edges.py`): full AST-based extraction for all edge types
- **TypeScript edge extraction** (`ts_edges.py`): regex-based CALLS, IMPORTS, ASYNC_CALLS, DECORATES, HTTP_CALLS, RAISES
- **Cyclomatic complexity** (`complexity.py`): per-function scoring for Python (AST) and TS/JS (regex)
- **Phantom symbol resolution**: unresolved edge targets (builtins like `ValueError`, `HTTPException`) stored as `symbol_type='external'` so edges are preserved
- **Git co-change analysis** (`git_edges.py`): FILE_CHANGES_WITH edges from `git log` (implemented, not yet wired into indexer)
- **Bidirectional graph traversal**: `cortex_trace` supports `direction='out'|'in'|'both'`
- **FTS5 camelCase splitting**: `validateToken` now searchable as `validate` + `token`
- **Deduplication**: recursive CTEs use `SELECT DISTINCT` for clean traversal results

#### Benchmark (claude-skills-package, 526 files)

| Metric | Cortex | CBM | Delta |
|--------|-------:|----:|-------|
| Symbols | 5,501 | 3,916 | +40% |
| Total edges | 14,850 | 12,010 | +24% |
| CALLS | 5,280 | 2,918 | +81% |
| HANDLES | 352 | 5 | +6940% |
| Incremental reindex | 0.03s | ~2s | 66x faster |
| Symbol search | 0.40ms | ~5ms | 12x faster |
| FTS search | 0.10ms | ~3ms | 30x faster |
| 3-hop traverse | 0.18ms | ~10ms | 55x faster |

#### Files Added/Modified
- `src/cortex/structure/python_edges.py` — full Python edge extraction via AST
- `src/cortex/structure/ts_edges.py` — full TS/JS edge extraction via regex
- `src/cortex/structure/complexity.py` — cyclomatic complexity scoring
- `src/cortex/structure/git_edges.py` — git co-change analysis
- `src/cortex/structure/edge_extractor.py` — refactored to thin coordinator
- `src/cortex/structure/indexer.py` — phantom symbols, complexity, FTS augmentation
- `src/cortex/storage/graph.py` — bidirectional traversal
- `docs/cortex-vs-codebase-memory.md` — updated benchmark report

---

## [6.32.0] - 2026-05-22

### Cortex MCP — Elixir Support + System Wiring

#### Added
- **Elixir AST extraction** in Cortex parser: `defmodule`, `def`, `defp`, route macros (`get/post/put/delete/patch`)
- `.ex`/`.exs` extensions recognized by the indexer
- 9 tests for Elixir extraction (modules, functions, private functions, routes, line numbers)
- **Cortex wired into local system**: Claude Code CLI, Claude Desktop, maggy codebases, engram, blueprint
- **Build-in-public plugin**: native X thread support via Buffer's `metadata.twitter.thread` API
- `on_thread_requested` event handler for pre-written tweet threads

#### Configuration
- `~/.claude/.mcp.json` — cortex server added (parallel with codebase-memory-mcp)
- `~/.claude/claude_desktop_config.json` — cortex server added
- `~/.maggy/config.yaml` — cortex-mcp registered as codebase
- `~/.maggy/engram.db` — tool capabilities stored
- `~/.maggy/blueprints.db` — `code_intelligence` blueprint added

---

## [6.31.0] - 2026-05-21

### ADR-Enforced Code Reviews

Every code review now requires architectural context. No more reviewing code in a vacuum.

#### How It Works

```
PR / code change
      |
  [1. Classify] — trivial changes (typos, deps, tests-only) skip the gate
      |
  [2. Discover] — scan docs/adr/, _project_specs/, iCPG, git history
      |
  ADRs found? --YES--> inject into review prompt as context
      |
      NO
      |
  [3. Reverse-engineer] — draft ADR from git log + code structure
      |
  [4. Present/auto-tag] — interactive: ask user to confirm
                          unattended (CI): write as Status: proposed
      |
  [5. Review runs WITH ADR context]
      |
  [6. Post-review] — extract decisions, log to decisions.md
```

#### Enforcement Modes
- **Interactive** (default): drafts ADR, asks user to confirm/edit/skip
- **Unattended** (CI/CD): auto-writes as `Status: proposed`, never marks accepted
- **Strict**: blocks review entirely until ADR exists

#### ADR Compliance Severity
| Finding | Severity |
|---------|----------|
| Code contradicts accepted ADR | Critical — blocks commit |
| Architectural decision without ADR | High — blocks commit |
| Stale/outdated ADR | Medium — can commit |
| Minor drift from ADR intent | Low — advisory |

#### Reverse-Engineering Protocol
When no ADR exists for non-trivial changes:
1. `git log --follow -5 <file>` — commit messages for WHY
2. Read module structure and imports for patterns chosen
3. Query iCPG ReasonNodes if indexed (optional, not required)
4. Check PR description and issue tracker for ticket references
5. Draft ADR with `Status: proposed`
6. Present to user OR auto-write in CI mode

#### Trivial Change Exemptions
These skip the ADR gate entirely:
- Typo/comment/whitespace fixes
- Dependency patch/minor version bumps
- Test-only changes that don't alter behavior
- Config value changes (not structural)
- Changelog/README updates

#### What Gets Installed (per project via /initialize-project)
- `docs/adr/` directory + `0001-project-init.md` seed ADR
- `.github/PULL_REQUEST_TEMPLATE.md` — PR requires ADR + spec links
- `.coderabbit.yaml` — CodeRabbit reads ADRs, doesn't flag documented patterns
- ADR compliance dimension added to all `/code-review` runs

#### What Gets Installed (globally via install.sh)
- `rules/adr-enforcement.md` — conditional rule, fires on code files
- `templates/adr.md` — lightweight ADR format
- `templates/PULL_REQUEST_TEMPLATE.md` — PR checklist
- `templates/.coderabbit.yaml` — CodeRabbit path instructions

### Added
- **ADR gate** (`skills/code-review/adr-gate.md`) — pre-review enforcement with discovery, reverse-engineering, and injection
- **ADR compliance review dimension** — 8th review category alongside Security, Performance, Architecture, etc.
- **PR template** — ADR + spec links required, compliance checklist
- **CodeRabbit config** — path instructions for `docs/adr/`, `src/`, `_project_specs/`, migrations
- **ADR enforcement rule** — global conditional rule installed via bootstrap
- **ADR template** — Status, Context, Decision, Consequences, Alternatives, Links
- **Post-review decision extraction** — auto-logs architectural findings to `decisions.md`

### Changed
- **Code-review skill** — mandatory ADR gate before any review engine runs
- **initialize-project** — creates `docs/adr/`, seeds ADR, installs PR template + .coderabbit.yaml
- **install.sh** — copies ADR templates idempotently, bumped to v4.1.0

---

## [6.30.0] - 2026-05-20

### Added
- **AGY (Antigravity) routing tier** — Google's terminal coding agent for end-to-end implementation (git+code+test)
- **Gemini CLI routing tier** — agentic coding agent for multi-file implementation within Google ecosystem
- **Grok routing tier** — xAI Grok 4.3 for competitor intel, CKG, deep reasoning

### Changed
- **Model routing expanded from 6-tier to 13-tier** — deduplicated tiers, added Gemini CLI (T5), AGY (T6), Grok (T9)
- **Routing heuristic updated** — added agentic coding, end-to-end impl, and competitor intel routing paths
- **Routing rules updated** — `model-routing.md` now includes GEMINI_CLI, AGY, GROK delegation rules

---

## [6.29.0] - 2026-05-20

### Added
- **In-browser file editor** — `vim`, `edit`, `nano`, `code` open files in editor tabs inside the chat window
- **Tab system** — Chat + editor tabs with dirty indicators, close buttons, cursor/scroll preservation
- **Editor API** — `GET /api/editor/read`, `POST /api/editor/write`, `GET /api/editor/stat` with path security
- **Atomic file saves** — temp file + rename prevents partial writes
- **Binary detection** — extension check + null-byte sniffing, graceful error for non-text files
- **Language inference** — 40+ file extensions mapped for future syntax highlighting
- **Keyboard shortcuts** — Ctrl+S save, Ctrl+W close tab, Tab inserts spaces
- **Line/column display** — real-time cursor position in editor header

### Changed
- **Editor programs extracted** — `vim`, `vi`, `nvim`, `nano`, `emacs`, `edit`, `code` now open editor instead of showing "blocked"
- **Path security refined** — narrowed macOS `/private` blocking to `/private/etc` and `/private/var` only

---

## [6.28.0] - 2026-05-20

### Added
- **Icons-only sidebar** — 52px compact sidebar with JS-positioned tooltips (z-index 9999)
- **CLI commands in chat** — `ls`, `cd`, `pwd`, `git`, `grep`, `find`, `tree` etc. via `/api/shell/exec`
- **Shell sandboxing** — allowlist + blocklist with 10s timeout, 8KB output cap
- **Slash commands** — `/mnemos`, `/icpg`, `/competitors`, `/budget`, `/routing`, `/progress`, `/forge`, `/status`, `/plan`
- **Self-healing command system** — Levenshtein fuzzy matching for unknown commands ("did you mean...")
- **Known programs list** — 80+ programs (vim, docker, python, etc.) show "use local terminal" instead of crashing
- **Command-like input detection** — `_looksLikeCommand()` heuristic intercepts mistyped commands before AI chat
- **Compact working indicator** — single-line joke rotation with "Working..." label

### Fixed
- **`/routing` data parsing** — correctly parses `list[dict]` heatmap grouped by model (was showing numbered indices)
- **`/mnemos` and `/status`** — use actual API fields (`total_memories`, `active_count`) instead of nonexistent `fatigue_score`
- **Unknown slash commands** — fuzzy-match suggestions instead of bare "Unknown command" error
- **`vim` crash** — blocked programs no longer fall through to AI chat causing API 400

### Changed
- **Default-collapsed projects** — inverted expand tracking (`maggy-expanded` localStorage key)
- **Sidebar tooltips** — switched from CSS `::after` pseudo-elements to JS-positioned fixed element (fixes z-index clipping)

---

## [6.26.0] - 2026-05-17

### Added
- **Mid-task model escalation** — real-time struggle detection with automatic tier switching
- **3-signal struggle detection**: consecutive errors, re-read loops, tool stagnation
- **Two-stage escalation**: warning (monitor) → escalate (force premium)
- **Dual-path integration**: PreToolUse hook (Claude Bootstrap) + ExecutorService (Maggy)
- **Max 3 escalations per session** to prevent escalation death spirals
- **Auto-resolve**: clears escalation flag when struggle patterns stop
- **Tested**: 6/6 Claude Bootstrap phases pass, 3/3 Maggy phases pass

### Changed
- **route-task-hook**: reads mid-task escalation flag, forces premium tier on next prompt
- **ExecutorService**: tracks per-session model failures, pushes fatigue to REM at 3+ failures
- **settings.json**: registered mid-task-escalation as PreToolUse hook

---

## [6.27.0] - 2026-05-19

### Added
- **Auto-isolation for concurrent sessions** — second Claude Code session in same project auto-provisions Polyphony Docker container workspace, preventing file/git conflicts
- **`polyphony-auto-isolate` hook** — SessionStart detection of sibling sessions, workspace provisioning

## [6.26.0] - 2026-05-19

### Added
- **Peekaboo integration** — native macOS screen capture for build-in-public plugin
- **Visual validation skill** — `skills/visual-validation/SKILL.md` with screenshot workflow
- **Collapsible tool calls** — click-to-expand tool details in chat dashboard

### Fixed
- **Font Awesome icons** — CDN switched from cdnjs to jsdelivr (CSP-compatible)
- **Duplicate "New" button** — main sidebar shows "New Session", removed duplicate
- **Ghost text overlap** — suggestion only shows when typing matches prefix
- **Active projects** — sidebar limits to 5 most recent from localStorage
- **Cmd+K search** — overlay click-to-close, keyboard shortcut functional
- **Multi-tab support** — `openChatTab()` for multiple chat threads

## [6.25.0] - 2026-05-17

### Added
- **E2E TestKit Plugin** — benchmark, drift detection, intent bug analysis for any project
- **Context-aware benchmark generation** — auto-detects project architecture and generates domain-specific benchmarks
- **Drift detection** — AI compares spec vs implementation, scores divergence
- **Intent bug detection** — finds flaws in original design assumptions
- **Plugin system upgrades** — router auto-registration, heartbeat jobs from manifests
- **Provider plugins extracted** — GitHub, Asana moved from core to plugins
#### Architecture Refactoring — Core → Plugin Extraction
- **Plugin system upgraded** —  now supports router auto-registration and heartbeat job registration
- **PluginManager** accepts FastAPI `app` and `HeartbeatScheduler` — plugins self-register routes and jobs on load
- **Plugin contract**: `plugin.yaml` declares `router: "module:var"` and `heartbeat: [{name, interval, fn}]`
- **Providers extracted from core**: GitHub Issues (`provider-github`), Asana (`provider-asana`) → plugins
- **IssueTrackerProvider protocol** stays in core as abstract interface
- **Forge connector** extracted →  with gap scan heartbeat
- **Kept in core**: routing, memory (Mnemos/Engram), execution, blueprints (learning patterns), competitor intel (autonomous market understanding)
- **8 plugins now**: build-in-public, e2e-testkit, provider-github, provider-asana, forge, and built-in plugins

- **Grok (xAI) integration** — 10th model tier via OpenAI-compatible API at `api.x.ai/v1`
- **10-tier routing**: Qwen3 → Gemini FL → DeepSeek Flash → DeepSeek Pro → Gemini Flash → Gemini CLI → Kimi → Grok → Gemini Pro Search → Codex → Claude
- **Competitor Intelligence Dashboard** — per-project competitor tracking (maggy, chess, edtech)
- **CompetitorIntel service**: auto-discovery, move tracking, threat levels, AI briefings
- **`/api/competitor-intel/{project}`**: competitors, moves, briefing, scan, discover endpoints
- **Usage-aware model routing**: per-model daily budget caps, auto-demote at 50%/80% thresholds
- **Cross-model usage analytics**: `maggy-usage` CLI + `/api/usage/report`
- **Per-response usage summary**: Stop hook shows route, cost, session delta
- **Reddit monitoring**: 21 subreddits, auto-commenting via OAuth2
- **X/Twitter API v2**: search, user lookup, live account monitoring
- **Full AI ecosystem watch map**: 80+ accounts across 8 categories

---

## [6.24.0] - 2026-05-16

### Added
- **Routing landscape comparison** in README — Maggy vs OpenRouter, Martian, Portkey, Semantic Router
- **Three unique differentiators**: fatigue-aware routing, cascading classifier resilience, semantic memory routing
- **Semantic cascading classifier** — `model_escalation.py`: qwen3 → kimi → deepseek-flash → Claude → keyword (keyword only as last resort)
- **Language-agnostic routing** — blast/intent now fully semantic, works across languages and domain jargon

---

## [6.23.0] - 2026-05-16

### Added

#### Build-in-Public Customization System
- **`customization.md`** — user-editable guidelines for channel voice, content rules, brands, and clickouts
- **`/build-in-public enable|disable`** — per-project activation via `projects.json`
- **`/build-in-public add brand <name>`** — explicitly allowlist brand names (all others redacted)
- **`/build-in-public add clickouts to <url>`** — set clickout URLs auto-appended to X posts
- **Per-project state** — `~/.maggy/build-in-public/projects.json` tracks enabled/disabled per project
- **Plugin reads customization on every generation** — no restart needed after edits

#### Buffer GraphQL API Migration
- **GraphQL endpoint** — migrated from deprecated REST `api.bufferapp.com/1` to `api.buffer.com`
- **`createPost` mutation** — posts scheduled via GraphQL with `customScheduled` mode
- **Channel discovery** — org ID + channel IDs auto-fetched via GraphQL queries
- **Auth** — Bearer token header (was query param in old REST API)

#### Content Scheduling
- **22 posts scheduled** — full monthly content calendar (May 18 - Jun 12)
- **8 LinkedIn deep dives** — 2-4 paragraph professional posts, each teaches something
- **14 X posts** — sharp singles + 6-tweet thread, all with `github.com/alinaqi/maggy` clickout
- **No coding stats** — removed "96 files, 14 commits" style metrics per voice guidelines
- **Per-channel differentiation** — LinkedIn teaches, X punches, each with distinct tone

### Fixed
- **PostCompact hook error** — removed invalid `PostCompact` from `settings.json` (not a valid Claude Code hook event)
- **Buffer `UnexpectedError`** — resolved by simplifying special characters in post text

### How It Works with Claude Bootstrap
The build-in-public plugin works standalone via `~/.claude/hooks/plugin-trigger` — no Maggy server needed. Drop the plugin folder into `~/.maggy/plugins/` and trigger events from any Claude Code hook:
```bash
~/.claude/hooks/plugin-trigger on_pr_merged '{"title":"Add auth","branch":"feature/auth"}'
~/.claude/hooks/plugin-trigger on_feature_shipped '{"feature":"JWT login"}'
```

---

## [6.22.0] - 2026-05-16

### Added

#### Plugin System — Event-Driven Architecture
- **`PluginManager`** — auto-discovers plugins from `~/.maggy/plugins/`, `maggy/plugins/`, `plugins/`
- **`HookBus`** — typed event bus with subscribe/emit pattern, async handlers with error isolation
- **`PluginManifest`** — YAML-defined: id, version, permissions, hooks, config schema
- **`/api/plugins`** — list, reload, emit test events via REST API
- **`plugin-trigger` (hook)** — standalone runner for Claude Bootstrap, no Maggy server needed
- **Dynamic module loading** — plugins import at startup, registration lifecycle with `register(bus, manifest)`

#### Build-in-Public Plugin — mWP First Plugin (7/11 Stars)
- **Autonomous storyteller** — notices work (PR merged, feature shipped, review passed), extracts narrative arc, publishes without asking
- **Multi-channel** — per-channel voice: LinkedIn (professional, teaches, 3000 chars) + X (sharp, punchy, 280 chars)
- **AI-powered synthesis** — DeepSeek Flash generates channel-native narratives from event data
- **Auto-redaction** — `anonymize.yaml` replaces sensitive names (company names → generic descriptors), strips revenue/user data via regex
- **Buffer API integration** — multi-profile scheduling per channel with fallback to `posts.jsonl`
- **Playwright screenshots** — captures hero screenshots of deployed features
- **Rate limiting** — configurable max posts/day per channel
- **Per-channel scheduling** — LinkedIn 09:00 UTC, X 10:30 UTC weekdays

#### Build-in-Public Skill
- **`skills/build-in-public/SKILL.md`** — 137-line reference with channel best practices
- What to share (technical decisions, failures, insights) vs never share (revenue, customers)
- Channel-specific formatting, tone, timing, anti-patterns
- Content calendar rhythm: daily X, weekly LinkedIn, per-event triggers
- Engagement rate targets and measurement signals

### Changed
- **`README.md`** — plugin system section with build-in-public as featured plugin
- **`main.py`** — plugin manager initialized at startup, plugins router registered

---

## [6.21.0] - 2026-05-16

### Added

#### Autonomous Plan → Validate → Execute Pipeline
- **`~/bin/validate-plan`** — sends plan to DeepSeek Pro + Codex + Gemini Pro in parallel
- **Multi-model voting** — 2+/3 approvals → auto-execute without user intervention
- **Goal detection** — route-task-hook: CLAUDE tier → PLAN FIRST with auto-validation
- **Approval thresholds**: 3/3 silent execute, 2/3 execute with feedback, 1/3 surface to user, 0/3 revise
- **`CLAUDE.md`** — documented autonomous plan→validate→execute flow

#### Autonomous Testing Agent
- **`services/autonomous_tester.py`** — full test lifecycle: discover → generate → execute → evaluate → fix
- **`api/routes_testing.py`** — `/api/testing/gaps`, `/api/testing/run`, `/api/testing/autonomous`
- **`skills/autonomous-testing/SKILL.md`** — reference for AI-driven test generation
- AI classifies failures as TEST_BUG vs CODE_BUG vs ENV_BUG
- AI auto-repairs TEST_BUGs, escalates CODE_BUGs to CLAUDE tier

#### GitHub Profile README Updated
- **Mission**: "Bringing personal super intelligence to every worker in the world"
- **Multi-model philosophy**: 9-tier routing, memory-first, autonomous agents, right tool for the job

---

## [6.20.0] - 2026-05-16

### Added

#### iCPG-Powered Explore Agent
- **`agents/explore.md`** — enhanced Explorer that uses codebase-memory-mcp graph tools first
- **`search_graph`**, **`trace_path`**, **`get_code_snippet`** over grep/glob for code discovery
- **`query_graph`** for complex dependency analysis and ReasonNode traversal
- Falls back to Grep/Glob/Read only for text content, config, non-code files

#### Plan-vs-Execute Decision Routing
- **route-task-hook** now classifies into PLAN FIRST vs EXECUTE DIRECTLY
- **CLAUDE tier** → "PLAN FIRST — explore, design approach, get approval"
- **DEEPSEEK_PRO / GEMINI_CLI tiers** → "EXECUTE DIRECTLY — no plan needed"
- Prevents unnecessary planning for workhorse coding tasks

#### Gemini CLI Integration
- **`~/bin/gemini-cli`** — full coding agent delegation (v0.42.0)
- Headless mode via `-p`, model selection via `-m` (pro/flash/flash-lite/auto)
- `--skip-trust` for automated environments, `--output-format json`
- Installed and tested: uses gemini-3-flash-preview, full tool support

### Changed
- **`onboard.sh`** — fixed cost display `$0` expansion bug
- **`gemini-cli`** — binary discovery path to avoid `~/bin/gemini` API delegator collision

---

## [6.19.0] - 2026-05-16

### Added

#### Autonomous Multi-Model Review
- **`~/bin/review`** — runs deepseek-pro + kimi + codex in parallel, merges findings
- **`auto-review-hook` (Stop)** — triggers reviews autonomously, no user prompt needed
- **Cascading classifier** for review decisions: qwen3 → kimi → deepseek-flash → skip
- **Dynamic qwen3 gatekeeper** — evaluates git state to decide if review is warranted
- **Cooldown** — minimum 5 turns between checks, 10 turns between reviews

#### Install Integration
- **`bin/`** — all delegation scripts (deepseek, gemini, kimi, qwen3, research, review)
- **`hooks/route-task-hook`** + **`hooks/auto-review-hook`** — packaged for install
- **`install.sh`** — copies scripts to `~/bin/`, hooks to `~/.claude/hooks/`
- **`skills/model-routing/SKILL.md`** — 159-line routing pipeline reference

#### PostCompact Recovery
- **`PostCompact` hook** — `mnemos-post-compact-inject.sh` restores context after compaction
- Routing cache survives compaction via `~/.claude/routing-cache.json`

---

## [6.18.0] - 2026-05-16

### Added

#### Gemini Integration — 9-Tier Model Routing
- **`~/bin/gemini`** — delegation script calling Gemini via OpenAI-compatible endpoint
- **Gemini 2.5 Flash-Lite** (Tier 2, $0.10/$0.40 per M) — bulk extraction, classification, CIG pipelines, cheapest model
- **Gemini 2.5 Flash** (Tier 5, $0.15/$0.60 per M) — multimodal (images, video, audio), brand asset analysis
- **Gemini 3.1 Pro + Search** (Tier 7, $1.25/$10 per M) — deep research, native Google Search grounding, 2M context window
- **`route-task-hook`** — expanded to 9 tiers with GEMINI_FLASH_LITE, GEMINI_FLASH, GEMINI_PRO_SEARCH
- **`model_router.py`** — DEFAULT_TIERS expanded from 6 to 9 entries with Google provider
- **`pi.py`** — DEFAULT_MODELS with Gemini entries and delegation conventions
- **`routing_rules_defaults.py`** — Gemini performance profiles (multimodal, bulk_extraction, deep_research, google_grounding)
- **`chat_router.py`** — added `use gemini` force pattern

### Changed
- **`CLAUDE.md`** — updated routing heuristic: bulk extraction → Gemini Flash-Lite, multimodal → Gemini Flash, deep research → Gemini Pro Search
- **`CLAUDE.md`** — 9-tier table with costs and roles

---

## [6.17.2] - 2026-05-16

### Added
- **Memory comparison table** — README now contrasts Maggy Mnemos vs Codex vs Claude Code across compaction triggers, preservation, transparency, recursive degradation, cross-session memory, team memory, and pre-compaction safety
- **Updated cross-tool table** — added DeepSeek V4 and Memory rows to compatibility matrix

---

## [6.17.1] - 2026-05-16

### Added

#### Research Tool with Auto-Evaluation
- **`~/bin/research`** — multi-backend research script with cascading fallback (deepseek-flash → deepseek-pro)
- **Auto-evaluation** — scores results 0-10 on content quality, structure, length, error detection
- **Backend preference auto-adjust** — tracks scores per backend and promotes the best performer
- **Evaluation log** — `~/.claude/research-eval.jsonl` with per-call scoring
- **Stats command** — `research --eval` shows per-backend success rates and average scores

#### Cascading Classifier Fallback
- **`route-task-hook`** — cascading classifier: qwen3 → kimi → deepseek-flash → cached tier
- **Routing cache** — `~/.claude/routing-cache.json` persists last tier across compactions
- **Per-call logging** — `classifier` field in routing log tracks which model did the classification

#### Tool Fallback Protocol
- Documented in `CLAUDE.md`: WebSearch/WebFetch failures → `~/bin/research` → `~/bin/deepseek`

---

## [6.17.0] - 2026-05-16

### Added

#### Maggy Dashboard UI Overhaul
- **Sidebar navigation** — modern vertical sidebar replacing horizontal tab bar, with grouped sections (Work, Intel, System)
- **Cmd+K / Ctrl+K command palette** — fuzzy project search with keyboard shortcut, instant jump between projects
- **Memory panel** — fatigue gauge with color-coded states (FLOW→COMPRESS→PRE_SLEEP→REM→EMERGENCY), engram stats, recent memories list
- **Progress panel** — real-time execution status per task, active/running/completed indicators with shimmer animations, recent activity signals log
- **Heartbeat indicator** — live status dot with pulse-glow animation, auto-refreshes every 30s
- **Model badge in header** — shows active model, blast score, task type during execution
- **Sidebar fatigue indicator** — compact fatigue percentage with color-coded state
- **CSS variable design system** — consistent dark theme with orange accent, scrollbar styling, badge components

#### Multi-Source Task Aggregator
- **`GET /api/aggregator/tasks`** — unified task list from `_project_specs/todos/` + GitHub Issues + Asana, deduplicated and priority-sorted
- **`POST /api/aggregator/execute-all`** — queue all pending tasks for TDD execution
- **`read_project_specs()`** — parses `active.md` and `backlog.md` markdown checklists into structured task objects

#### Progress Analysis Engine
- **`ProgressEngine`** — cross-model execution tracker with step history, blocker detection, model usage stats
- **Auto-adjust routing** — detects fatigue thresholds and consecutive failures, suggests model escalation
- **Next-action suggestions** — analyzes blocker state, model failures, and unvalidated completions to recommend next steps
- **`ProgressSnapshot`** — structured summary of active/completed/blocked tasks, elapsed time, model distribution

#### Background Heartbeat Jobs
- **`poll_inbox`** — auto-refreshes inbox from GitHub/Asana every 5 minutes (configurable interval)
- **`scan_competitors`** — periodic competitor news scanning for active project
- **`track_research`** — research trend tracking for active project
- All jobs registered in `HeartbeatScheduler` with per-job error isolation and status tracking

#### Generic Test Suite Generator
- **`test_generator.py`** — auto-detects Python (pyproject.toml/setup.py) and TypeScript (package.json) projects
- **Python scaffold** — generates `conftest.py`, `__init__.py`, per-module test stubs, `.coveragerc` with configurable thresholds
- **TypeScript scaffold** — generates `vitest.config.ts` with coverage thresholds, sample test file
- **`write_scaffold()`** — one-call detection + generation + file writing with summary output

### Changed
- **`main.py`** — registered `aggregator_router` for task aggregation endpoints
- **`progress_engine.py`** — new module with task state tracking and routing auto-adjustment
- **`routes_aggregator.py`** — new API routes for multi-source task listing and batch execution

### Stats
- 8 files changed across UI (2), backend (4), heartbeat (1), test gen (1)
- New panels: Memory, Progress (2) in redesigned sidebar
- New API endpoints: 3 (aggregator tasks, execute-all, progress status)
- All existing routing tests pass (38/38)

---

## [6.16.0] - 2026-05-16

### Added

#### Multi-Model Delegation Pattern
- **External model delegation via `~/bin/` scripts** — consistent pattern for calling Qwen3, DeepSeek, Kimi, and Codex from both Claude Code hooks and Maggy's executor
- **6-tier routing hook** — `UserPromptSubmit` hook classifies every prompt via qwen3 into QWEN / DEEPSEEK_FLASH / DEEPSEEK_PRO / KIMI / CODEX / CLAUDE tiers
- **`~/bin/deepseek`** — Python delegation script calling DeepSeek's Anthropic-compatible API via httpx, supports `--flash` / `--pro` flags
- **Project CLAUDE.md** — created with full skill references, routing table, and project structure docs

#### DeepSeek V4 in Maggy Routing
- `model_router.py` — expanded DEFAULT_TIERS from 4 to 6: local → deepseek-flash → deepseek-pro → kimi → codex → claude
- `ai_client.py` — DeepSeek API completion via OpenAI-compatible endpoint with httpx
- `adapters/deepseek.py` — DeepSeek orchestrator adapter registered for deepseek, deepseek-flash, deepseek-pro
- `routing_rules_defaults.py` — docs/tests route to deepseek-pro, security/architecture stay on claude
- `fatigue.py` — split deepseek into flash/pro context windows (128K each)
- `chat_router.py` — added `use deepseek` force pattern
- `pi.py` — DEFAULT_MODELS split into flash/pro, `_build_command` handles delegation script conventions

#### Skill Documentation
- `skills/external-model-delegation/SKILL.md` — complete reference: tier table, delegation script contract, routing hook flow, classification tiers, environment setup

### Tests
- `test_deepseek_routing.py` — 16 new tests for 6-tier routing, cost ordering, provider mapping, strength attributes
- Updated `test_routing_service.py`, `test_benchmark_scenario.py`, `test_multimodel_integration.py` for new tier structure
- 80 routing tests pass, 0 failures

---

## [6.15.0] - 2026-05-16

### Added

#### Mnemos Checkpoint Compatibility & Compact Recovery
- **Backward-compatible checkpoint serialization** — `checkpoint.py` extended with compat-layer serialization so older checkpoint formats deserialize cleanly into current `CheckpointNode` schema
- **`mnemos-compact-recovery.sh`** — New recovery script for post-compaction checkpoint restoration; detects compaction markers and re-injects checkpoint context automatically
- **`test_mnemos_checkpoint_compat.py`** — 162-line test suite for backward-compatible checkpoint round-trips across schema versions
- **`test_executor_bridge.py`** — 101-line test suite for chat executor bridge routing decisions and blast-score thresholds

#### Fatigue-Aware Model Routing
- **Mnemos fatigue wired into model routing** — `model_router.py` now queries fatigue state and adjusts routing: high fatigue biases toward simpler models to reduce context pressure
- **`test_fatigue_routing.py`** — 107-line test suite for fatigue-aware routing decisions

### Fixed

#### Defensive Hook Scripts
- **All hook scripts hardened** — Removed `set -euo pipefail` from all mnemos hooks; added `2>/dev/null || true` guards on `cat`/`jq` stdin reads so hooks never block Claude Code sessions
- **Defensive pattern established**: (1) no strict mode, (2) `INPUT=$(cat 2>/dev/null || true)`, (3) jq with `// empty` fallbacks, (4) always `exit 0` on failure
- **Kimi parser fix** — `history/parsers/kimi.py` improved session detection for cross-tool context injection
- **Executor bridge improvements** — `chat_executor_bridge.py` refined routing logic for actionable vs informational messages

### Changed
- **`models.py`** — Extended Mnemos model definitions with additional fields for checkpoint compat
- **`SKILL.md`** — Updated mnemos skill documentation with compact recovery and compat details
- **`templates/CLAUDE.md`** — Added mnemos compact recovery references
- **`templates/mnemos-post-compact-inject.sh`** — Improved injection logic for post-compaction context restoration

### Stats
- 79 files changed, +5,593 / -144 lines across the full PR
- New test files: 28 test files, **243+ tests passing**, 83% coverage

---

## [6.14.1] - 2026-05-15

### Fixed

#### Mnemos Stability — OOM Prevention and Concurrent Access
- **Bounded signal reads**: `read_recent_signals(n=30)` uses `deque` tail-read instead of loading entire `signals.jsonl` into memory — prevents OOM in long sessions
- **SQLite WAL mode**: `MnemosDB` now enables `PRAGMA journal_mode=WAL` on init — prevents "database is locked" errors when multiple hooks fire concurrently
- **Connection lifecycle**: `MnemosDB` implements context manager protocol (`with MnemosDB() as db:`), hook dispatch uses it to guarantee connection cleanup
- **Constant usage**: `_hook_pre_compact` uses `COMPACT_UTILIZATION` constant instead of hardcoded `0.83`
- **Type safety**: Hook handler signatures changed from `db: object` to `db: MnemosDB`
- **Clean imports**: `extraction.py` uses normal `from pathlib import Path` instead of inline `__import__`
- **8 new tests**: `read_recent_signals` (5 tests including malformed JSONL), WAL mode, context manager lifecycle — total now **243 tests**

---

## [6.14.0] - 2026-05-15

### Added

#### Mnemos Full Implementation — Task-Scoped Memory Lifecycle
- **Tier 0 Core**: `constants.py`, `models.py` (12 node types, Pydantic models), `db.py` + `db_queries.py` (SQLite CRUD + bulk ops), `fatigue.py` (token util with 4-dim upgrade path), `checkpoint.py` (write/read/cooldown), `status.py`, `cli.py` + `cli_hooks.py` + `cli_nodes.py`
- **Tier 1 Lifecycle**: `activation.py` (recency/frequency/centrality composite weights), `scope.py` (tag inference + Jaccard overlap), `signals.py` (JSONL tool call logger), `fatigue_dimensions.py` (4-dim: token 0.40, scatter 0.25, reread 0.20, error 0.15), `extraction.py` (tool-to-node pipeline), `consolidation.py` (micro-consolidation at COMPRESS range), `skills.py` (fingerprint + promotion algebra)
- **Full Tier**: `rem.py` + `rem_slow_wave.py` + `rem_skills.py` + `rem_pruning.py` + `rem_wake.py` (4-phase REM process), `delegation.py` (sub-agent inheritance rules), `merge.py` (5 conflict types, absolute ConstraintNode protection), `orchestrator.py` (5 signal types), `handoff.py` (fleet diagnostics)
- **Backward compat**: `_compat.py` preserves v0 `FatigueTracker` and `SignalLog` APIs
- **230 new tests** across 27 test files, 83% coverage

---

## [6.13.0] - 2026-05-15

### Added

#### Self-Healing System
- **`services/frustration.py`** — Frustration detection service with target taxonomy (app_bug / output_quality / task_difficulty), 5 weighted scoring dimensions (repetition 0.30, escalation 0.25, rapid re-sends 0.20, explicit language 0.15, abandonment 0.10), convergence bonus, and 4 threshold actions (log / adjust / notify / ticket)
- **`services/health_watchdog.py`** — Server health watchdog monitoring processes (PID), HTTP endpoints, and system memory (psutil with sysctl fallback); reports aggregate HEALTHY / DEGRADED / UNHEALTHY status
- **RFC Section 15** — "Self-Healing: Autonomous Fault Detection and Recovery" documenting three-signal-collector architecture, frustration target classification, triage engine, and integration points

#### iCPG Inspection
- **`api/routes_icpg.py`** — New API to browse iCPG reason graphs across all configured codebases: `/api/icpg/overview`, `/{project}/reasons`, `/{project}/drift`, `/{project}/graph`
- Dashboard iCPG tab with aggregate stats, drill-down by project, drift alerts, ReasonNode grouping by status, and SVG force-layout graph visualization

#### Chat UX Overhaul
- Multi-line textarea input with auto-expand (Shift+Enter for newlines, Enter to send)
- Progressive markdown rendering during streaming (debounced at 300ms instead of only after stream ends)
- Sidebar star/collapse — star projects to pin them top, collapse inactive ones; state persisted in localStorage
- Tab button transitions with hover states and active glow
- User messages preserve whitespace/newlines

#### Orchestrator
- **`orchestrator/isolation.py`**, **`merge.py`**, **`worktree.py`** — Worktree-based isolated agent execution with safe merge-back strategies

#### Phase Specs
- 14 phase documents for Maggy v2–v5 roadmap (PI adapter through event spine)

### Fixed
- **Codex executor timeout** — bumped `_POLL_TIMEOUT` from 300s to 600s; Codex planning tasks were timing out at ~298s and falling back to Claude unnecessarily

### Tests
- 13 tests for frustration detection (target classification, score dimensions, thresholds, edge cases)
- 11 tests for health watchdog (PID checks, endpoint checks, memory, aggregate status)
- 14 test files for budget, event spine, worktree isolation/merge, model routing, process intelligence

---

## [6.12.0] - 2026-05-13

### Added

#### Task Blueprints
- **`blueprint_store.py`** — Self-learning repeatable workflows; Maggy captures tool sequences from successful tasks and replays them with cheaper models on similar future tasks (e.g., generating benchmark reports for 16+ companies routes to local after 3 proven examples)
- SQLite-backed blueprint persistence with keyword overlap matching, project scoping, time-decay confidence, and collective matching (3+ similar blueprints prove a pattern)
- **`blueprint_extract.py`** — keyword extraction with path stripping, sha256 fingerprinting, template capture with `{path}`/`{value}` slots
- **`api/routes_blueprints.py`** — `GET /api/blueprints/` and `GET /api/blueprints/match` endpoints
- **`cli_blueprints.py`** — `/blueprints` CLI command with Rich table display (type, keywords, confidence, uses)

#### Session Persistence
- Chat sessions + messages now saved to SQLite, surviving server restarts
- **`services/session_store.py`** — SQLite store with sessions + messages tables, WAL mode, foreign keys

#### Claude CLI Improvements
- `_run_claude` now logs start/pid/exit/errors to `~/.maggy/server.log`
- Per-line 180s timeout prevents stale sessions from hanging forever; `_read_with_timeout` async generator
- Arrow key history — readline import enables up/down command recall in REPL

### Fixed
- **"Task chat-xxx not found"** — executor bridge created ephemeral Task but only passed ID to `executor.start()`, which tried to re-fetch from issue tracker; now passes pre-built Task object directly
- **Executor tasks not completing** — `executor_stream` read session once immediately after `start()` (which returns instantly); now polls session every 2s via `_poll_session()` until status leaves "running", streaming incremental output
- **Background task auto-finish** — `_bg_loop` now uses `select.select` with 0.3s timeout instead of blocking on `Prompt.ask`, so completed tasks display results immediately

### Changed
- Blueprint context injected into messages when routing matches a proven blueprint
- `routes_chat.py` captures tool_use events during streaming and records blueprints after successful completion
- `chat_router.py` checks blueprint store before standard routing; `RouteDecision` has `blueprint_context` field
- `chat_media.py` extracted from `chat.py` (detect_image, detect_document, stream_vision, stream_doc) for quality gate compliance
- `cwd_project()` moved from `cli_chat.py` to `cli_context.py`

---

## [6.11.0] - 2026-05-13

### Added

#### `/rules` Command
- Comprehensive routing rules summary showing task-type overrides, pipeline phases, model performance (strengths + weaknesses), team conventions, stakes classification patterns, and cascade policy in one panel
- **`cli_rules.py`** — `cmd_rules` with `_fmt_overrides`, `_fmt_phases`, `_fmt_perf`, `_fmt_conventions`, `_fmt_stakes`, `_fmt_cascade` formatters
- Full rules API — `/api/routing/rules` now returns pipeline phases, conventions text, stakes patterns, cascade policy, model weaknesses, and override confidence/source (was only returning overrides + strengths)
- `reviewer_heatmap()` client method (was missing from `cli_client.py`)

---

## [6.10.0] - 2026-05-13

### Added

#### Reviewer Evaluation & Knowledge Map
- Tracks reviewer performance (CodeRabbit vs Codex vs local) by finding category (security, performance, style, logic, architecture) with time-decayed scoring; builds knowledge map so Maggy learns which reviewer is better at what
- **`review_scores.py`** — SQLite-backed `ReviewerTable` with `record`, `best_reviewer`, `heatmap`, `compare` (same decay pattern as model rewards)
- **`services/reviewer_eval.py`** — keyword-based finding categorization, `evaluate_review` records to ReviewerTable, `compare_reviewers` for side-by-side
- **`api/routes_review.py`** — `/api/reviewers/heatmap` and `/api/reviewers/compare` endpoints
- `/reviewers` CLI command shows reviewer × category performance heatmap
- Review findings auto-recorded after review-type chat responses complete

---

## [6.9.0] - 2026-05-13

### Added

#### Non-Blocking REPL
- Long-running tasks (CodeRabbit reviews, Codex analysis, etc.) now run in a background thread; REPL stays responsive with `bg>` prompt for `/status` and `/cancel` commands
- **`cli_bg_task.py`** — thread-safe `TaskState` with `start_task`, `cancel_task`, `get_status`, `is_active`, `collect_result`
- `/status` command shows background task progress (model, chunks, tool calls)
- `/cancel` command stops a running background task

### Changed
- `_send_message()` returns `TaskState` for routed messages (background) or `None` for direct (blocking)
- `_repl_loop()` enters `_bg_loop()` when a background task starts, accepting commands during streaming
- `cmd_stats` moved from `cli_repl_cmds.py` to `cli_repl_info.py`
- `SessionState` has `bg_task` field for background task tracking

---

## [6.8.0] - 2026-05-13

### Fixed
- **Session history detection** — Claude parser `_slug()` now preserves full resolved paths instead of basename-only (was losing `/Users/ali/maggy` → `maggy`); Codex parser reads `cwd` from rollout files instead of using user-defined `thread_name`; Kimi parser reads `work_dirs` from `kimi.json` instead of hardcoding empty string
- **Project matching** — `_matches_project()` uses strict resolved-path comparison instead of loose substring matching that caused false positives
- **Context fallback** — `gather_cli_context()` falls back to `session_detect.detect_all()` when HistoryService returns no matches

### Added

#### Verified Context & Chat-to-Executor Bridge
- **`verified_context.py`** — gathers real git state (branch, status, recent commits) and active CLI sessions; injected alongside history so LLMs don't fabricate project state
- **Collapsible thinking** — tool events accumulate during streaming, collapsed summary (`[N tool calls]`) shown after response; `/thinking` command re-expands the last response's tool events
- **`chat_executor_bridge.py`** — routes actionable messages (blast >= 4, non-search/docs/review) through the full executor pipeline (iCPG, TDD, Mnemos, Engram) instead of raw LLM CLI passthrough
- `cli_repl_info.py` extracted from `cli_repl_cmds.py` for session/info/thinking commands

### Changed
- `stream_chunks()` now returns `dict` with `tool_events` list instead of `None`
- `SessionState` has `last_tool_events` field for `/thinking` command
- `_format_sessions()` uses full-path project values (no more basename matching)
- REPL command handlers split across `cli_repl_cmds.py` (routing/budget) and `cli_repl_info.py` (session/info/thinking)

---

## [6.7.0] - 2026-05-13

### Added

#### Tool Progress Display
- CLI now surfaces `tool_use` events from Claude CLI's stream-json, showing what Claude is doing (Read, Edit, Bash, Grep, etc.) as dim progress lines above the spinner, matching Claude Code's work-progress UX
- `_format_tool_use()` renders readable labels per tool type (file paths, commands, patterns)
- `parse_chunks()` replaces `parse_chunk()` — returns list of chunks, extracting both `text` and `tool_use` blocks from assistant messages

### Fixed
- **Model label duplication** — model name (codex, kimi, etc.) no longer repeats on every Live refresh; now printed once above the live area via `console.print` instead of being re-rendered inside the Live display
- **SSE timeout** — increased HTTP streaming timeout from 120s to 600s so long-running Claude/Codex operations don't get killed mid-response; also increased `ai_client.py` subprocess timeout to match
- `_StreamState` simplified — removed `model_label` field; routing/tool events print above Live area, Live only manages spinner + content

---

## [6.6.0] - 2026-05-13

### Changed
- **Claude Code-style streaming UX** — removed knock-knock jokes and joke thread; display is now a clean spinner ("Thinking...") with markdown output, matching Claude Code's minimal style
- Model label shown as dim text instead of a Rule separator
- `/history`, `/sessions`, `/monitor` commands moved to central dispatch in `cli_repl_cmds.py`

### Added

#### Multi-CLI Context Injection
- On startup, Maggy gathers recent session history from Claude Code, Codex, and Kimi and injects it into the first message so the LLM knows what you've been working on across tools
- **`cli_context.py`** — module for history gathering and project matching
- Server accepts `history_context` on session creation and uses it in the first Claude prompt

### Removed
- Knock-knock joke cycling thread and all 15 jokes from `cli_stream.py`
- Threading/lock machinery from `_StreamState`
- `_show_resume_info` startup dump (replaced by context injection)

---

## [6.5.0] - 2026-05-13

### Changed
- **CWD = project** — running `maggy` from any directory uses that directory as the project (like Claude Code), no config lookup needed
- Sessions now matched by `working_dir` path instead of `project_key` name, ensuring correct resume across identically-named folders
- Server accepts any existing directory as a project path (no codebase config required)
- REPL prompt pushed to bottom of terminal after welcome panel

### Removed
- Config-based project detection (`detect_project`, `detect_candidates`, `_is_inside`)
- Multi-project disambiguation prompt

---

## [6.4.0] - 2026-05-12

### Added

#### Claude Code-Style Streaming UX
- CLI REPL now shows animated spinner, model label (`Working with <model> · blast N`), and cycling knock-knock jokes during response streaming
- Web dashboard 4-zone chat layout — top progress shimmer, messages scroll, working zone (model label + jokes), sticky input bar with dividers

### Changed
- Streaming display extracted to `cli_stream.py` for cleaner separation of concerns
- Web chat switched from `/send` to `/send-routed` to display model metadata during streaming
- Jokes and response content render in separate DOM elements (web) / Rich Group zones (CLI), fixing invisible jokes

---

## [6.3.0] - 2026-05-12

### Added

#### Document Processing
- Paste Excel, DOCX, PDF, CSV, JSON, TXT paths in chat; text is extracted locally and forwarded to Claude for analysis
- **Auto-install dependencies** — missing optional packages (openpyxl, python-docx, pymupdf) are pip-installed automatically on first use
- **Ollama → Claude API escalation** — vision and intent classification auto-fallback to Claude API when local models are unavailable
- **`maggy restart`** — new CLI command to stop and restart the server

### Changed
- Intent classifier and blast scorer now use escalation (Ollama → Claude API → keyword fallback)
- Chat models extracted to `chat_models.py` for cleaner architecture

---

## [6.2.0] - 2026-05-12

### Added

#### Semantic Blast Score
- **`services/intent_classifier.py`** — `classify_blast()` estimates task complexity (1-10) via local Ollama model instead of keyword matching. Uses same pattern as `classify_intent()`: JSON prompt, `num_predict: 20`, `/no_think` directive. Falls back to keyword `estimate_blast()` on failure. ~200ms warm, 11/12 accuracy on edge cases.
- **`RoutedChat.decide()`** — now calls `classify_blast()` instead of keyword `estimate_blast()` when no override is provided. Both blast and intent are fully semantic.

#### Ghost-Text Suggestions
- **`static/app.js`** — Claude Code-style autocomplete suggestions in the chat input. Tracks recent messages and response context, shows a light-colored suggestion based on 14 context-aware rules (e.g., after fixing a bug → "now run the tests to verify the fix"). Tab accepts the suggestion, typing clears it.

### Stats
- 887 tests passing (881 + 6 new blast classifier tests)

---

## [6.1.0] - 2026-05-12

### Added

#### Semantic Intent Classification
- **`services/intent_classifier.py`** — Replaces brittle keyword matching with semantic classification via local Ollama model (`qwen3-coder:30b-a3b-q8_0`). Sends a short JSON-mode prompt to `localhost:11434/api/chat`, classifies into: review, security, search, docs, tests, frontend, general. 5s timeout, temperature 0. Falls back to keyword `estimate_type()` when Ollama is unavailable. Zero cost (local model).

#### Natural Language Model Forcing
- **`services/chat_router.py`** — `parse_model_force()` detects "use claude" / "use codex" / "use kimi" / "use local" inline in any chat message. Strips the directive, forces the model regardless of blast score. No flags or config needed — just type "use claude and review my code".

#### Review Task Type
- **`services/chat_router.py`** — Added "review" to `TYPE_KEYWORDS` (review, code_review, pr, pullrequest, audit, inspect, validate, verify) as keyword fallback. Semantic classifier handles primary detection.

#### Chat UX — Input Anchored to Bottom
- **`static/index.html`** — Outer container switched from `min-h-screen` to `h-screen flex flex-col overflow-hidden`. Main fills remaining viewport. Panes take full height. Input bar permanently anchored at bottom like Claude Code.

#### Chat UX — Knock-Knock Jokes While Waiting
- **`static/app.js`** — 50 dev-themed knock-knock jokes (git, docker, async, vim, regex, etc.) cycle every 1.8s while the model is thinking. Stops immediately when the first response chunk arrives.

### Changed
- `RoutedChat.decide()` is now async — calls `classify_intent()` for semantic classification, with keyword `estimate_type()` as degraded fallback path.

### Stats
- 881 tests passing (874 + 7 new intent classifier tests)

---

## [6.0.0] - 2026-05-12

### Added

#### Polyphony Container Orchestration — Parallel Execution
- **`maggy/orchestrator/`** — Polyphony orchestrator integrated as first-class Maggy subpackage. 20 files (~2700 lines) covering Docker container lifecycle, git workspace cloning, adapter routing (Claude/Codex/Kimi), 5-dimension complexity scoring, SQLite state tracking, and 7-state task machine.
- **`orchestrator/async_runtime.py`** — Async wrappers (`asyncio.to_thread`) around sync Docker subprocess calls. Non-blocking container create/start/wait/stop/remove.
- **`orchestrator/decomposer.py`** — LLM-based task decomposition. Asks Claude to split complex tasks into 2-5 independent subtasks. Falls back to single-task on failure. Capped at 5 subtasks.
- **`services/orchestrator.py`** — `OrchestratorService` manages team lifecycle: `spawn_team()` launches containers in parallel via `asyncio.gather`, `_run_one()` handles per-container Docker lifecycle (create → start → wait → logs → remove), `cancel_team()` for graceful shutdown.
- **`services/executor_helpers.py`** — `select_strategy()` decides parallel vs sequential: blast≥7 OR files≥5 OR user_requested → parallel.
- **`api/routes_orchestrator.py`** — REST endpoints: `POST /spawn` (decompose + launch team), `GET /teams` (list), `GET /teams/{id}` (status), `POST /teams/{id}/cancel`, all under `/api/orchestrator/`.
- **`config.py`** — `OrchestratorConfig` dataclass: `enabled`, `max_concurrent` (default 3), `workspace_root`, `container_timeout` (600s), `decompose_threshold` (7).
- **`main.py`** — Orchestrator router registered, service initialized when `orchestrator.enabled = true`.

### Stats
- 868 tests passing (843 + 25 new orchestrator tests)
- 5 new test files: strategy selector, async runtime, decomposer, orchestrator service, orchestrator routes

---

## [5.9.0] - 2026-05-12

### Added

#### Auto-Start — Zero-Config Bootstrap
- **`maggy/main.py`** — Server auto-starts on first CLI command if not already running. No separate `maggy serve` step needed.

#### Qwen3-VL Vision — `/screenshot` Command
- **`maggy/services/vision.py`** — Ollama HTTP vision client for Qwen3-VL (`qwen3-vl:32b`). Base64-encodes images, streams analysis via `POST /api/chat`. Supports `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`.
- **`/screenshot <path> [prompt]`** in REPL — Analyze screenshots for UI review, bug spotting, OCR, design-to-code. Custom prompts supported.

#### Module Extraction — Large Files Decomposed
- **`routing_rules.py`** split into 3 files — `routing_rules.py` (core), `routing_rules_defaults.py` (tier definitions), `routing_rules_io.py` (file I/O). Was 450+ lines, now each under 200.
- **`services/executor.py`** split into 4 files — `executor.py` (orchestration), `executor_helpers.py` (subprocess), `executor_prompts.py` (prompt templates), `executor_types.py` (dataclasses). Was 600+ lines.
- **`services/chat.py`** split — streaming extracted to `chat_stream.py`.
- **New service modules**: `cascade.py` (cascading model fallback), `context_compactor.py` (context size management), `convention_inferrer.py` (project convention detection), `convention_scanner.py` (file pattern scanning), `output_reviewer.py` (LLM output quality check), `stakes.py` (task risk assessment), `tdd_verifier.py` (TDD pipeline verification).
- **`cikg/graph.py`** decomposed — queries extracted to `cikg/queries.py`.

#### Reward Recording
- **`routes_chat.py`** — Routed chat endpoint now records routing outcomes (model, task type, blast score, quality score) after completion via `RoutingService.record_outcome()`. Feeds the reward heatmap for learning-based routing.

#### User Management
- **`services/users.py`** — User creation with bcrypt password hashing, SQLite storage, email uniqueness validation.
- **`api/routes_users.py`** — `POST /api/users` endpoint for user registration.

#### CI/CD
- **`.github/workflows/integration.yml`** — GitHub Actions workflow: pytest on Python 3.11 + 3.12, coverage >= 80%.

#### Documentation
- **`docs/architecture-v5.md`** — Full v5 architecture reference (v3→v4→v5 evolution, Pi agent harness, multi-project dashboard).
- **`docs/mnemos-implementation.md`** — Mnemos implementation addendum (signal access, hook integration, fatigue dimensions).
- **`docs/polyphony-spec.md`** — Polyphony multi-agent orchestration specification (6-layer architecture, task state machine, routing rules).

### Changed
- **GPT tier removed** from `DEFAULT_TIERS` — OpenAI deprecated the free research tier. Codex promoted to primary mid-range model (`routing_rules_defaults.py`, `model_router.py`).
- **Engram seed** now fills only missing memory types instead of requiring an empty store. Existing engrams preserved (`engram/seed.py`).

### Fixed
- **Routing rewards not recorded** — routed chat responses weren't feeding the reward heatmap. Added `record_outcome()` call after stream completion (`routes_chat.py`).
- **Engram seed skipped non-empty stores** — stores with some memory types but missing others weren't seeded. Now checks per-type and fills gaps (`engram/seed.py`).

### Tests
- `tests/test_routing_config.py` — 3 tests for GPT removal, codex promotion
- `tests/test_chat_routed.py` — 3 tests for reward recording
- `tests/test_engram.py` — +4 tests for seed edge cases (fill missing types, skip when all present)
- `tests/test_routes_users.py` — 7 tests for user registration
- **Total: 843 tests passing** (825 + 18 new)

---

## [5.8.0] - 2026-05-12

### Fixed

#### UX Fix Pass (12 issues from manual CLI testing)
- **Prompt character** — Changed from `maggy:` to `>` for cleaner input (`cli_chat.py:76`)
- **Ctrl+C during streaming** — Now cancels current response instead of exiting REPL. Added `except KeyboardInterrupt` in `_stream_chunks` (`cli_chat.py:161`)
- **`/health` 404** — Client was calling `/api/health/memory` (non-existent). Fixed to call `/api/engram/diagnostics` (`cli_client.py:260`)
- **`/route`, `/models`, `/budget`, `/stats`, `/health`, `/config` crash on server down** — Added `_call(fn, default)` safe wrapper that catches `Exception` and `SystemExit` from unreachable server. All display commands return fallback data instead of crashing (`cli_repl_cmds.py:18`)
- **Models shows "0 tracked" / "No data yet"** — When heatmap is empty, now shows the 5 known model tiers (local, kimi, gpt, claude, codex) with 0 samples (`cli_repl_cmds.py:129`)
- **`/use` accepts invalid model names** — Now validates against `_KNOWN_MODELS`, prints warning for unknown names while still setting the restriction (`cli_repl_cmds.py:147`)
- **Dir shows "?"** — Welcome banner now falls back to `os.getcwd()` when session `working_dir` is empty (`cli_welcome.py:36`)

### Added

#### Budget Subscription Awareness
- **`plan` field** on `BudgetConfig` — Users set `budget.plan: subscription` in `~/.maggy/config.yaml` (`config.py:150`)
- **`BudgetManager.budget_status()`** includes `plan` in response (`budget.py:163`)
- **`/budget`** shows "Subscription" instead of "$0.00 / $10.00" when plan is subscription (`cli_repl_cmds.py:87`)
- **Welcome banner** shows "Subscription" for subscription plans (`cli_welcome.py:54`)

#### Welcome Banner Improvements
- **Models count** — Shows "5 available" (known model count) instead of "0 tracked" when no heatmap data (`cli_welcome.py:62`)

### Changed
- **`_HELP` compressed** — 2-column layout saves 6 lines, fits all new features within 200-line limit (`cli_repl_cmds.py:191`)

### Tests
- `test_repl_cmds.py` — +5 tests: models_empty_shows_known, use_warns_unknown_model, budget_subscription_plan, health_graceful_failure, stats_server_down
- `test_cli_welcome.py` — +3 tests: dir_shows_cwd_fallback, models_shows_available_count, budget_subscription_welcome
- `test_cli_chat.py` — +1 test: chat_prompt_uses_angle_bracket
- **Total: 825 tests passing** (816 + 9 new)

---

## [5.7.0] - 2026-05-12

### Added

#### `/monitor` Command — Background Tracker Polling
- **`maggy/services/monitor.py`** — MonitorService with SQLite-backed polling for GitHub PRs and Monday.com items. `MonitorConfig` and `MonitorEvent` dataclasses, `add/remove/list_active/is_new/mark_seen/status/poll` methods
- **`maggy/providers/monday.py`** — Monday.com provider implementing `IssueTrackerProvider` protocol via GraphQL API. Maps board items to Task dataclass
- **`maggy/api/routes_monitor.py`** — REST endpoints: `GET /api/monitor/status`, `POST /api/monitor/start`, `POST /api/monitor/stop`
- **`/monitor` handler** in REPL — shows active monitor count (`cli_chat.py:94`)

#### `/health` Command — Memory Health Dashboard
- **`cmd_health()`** — Shows Engram health score (color-coded) and Mnemos fatigue state in Rich Panel (`cli_repl_cmds.py:180`)
- **`health_dashboard()`** and **`engram_diagnostics()`** client methods (`cli_client.py:259`)

#### Enhanced Welcome Banner
- **`cli_welcome.py`** — New file with Rich Panel welcome banner showing project info, budget, models, status, and memory health score

#### Search Routing to Local Model
- **"search" type** added to `TYPE_KEYWORDS` in `chat_router.py` — 11 keywords (find, search, grep, where, locate, which, look, scan, show, list, read) route to local/Qwen model for free

#### Account Switching Guidance
- **`maggy/services/account_guide.py`** — Detects CLI auth profiles from `~/.claude/`, `~/.codex/`. `suggest_switch()` returns CLI instructions, `render_switch_guide()` prints Rich-formatted guidance
- **Quota error detection** — `_QUOTA_MARKERS` in `cli_chat.py` triggers account switch guidance on rate limit errors

### Tests
- `test_monitor.py` — 8 tests for MonitorService
- `test_monday_provider.py` — 6 tests for MondayProvider
- `test_account_guide.py` — 5 tests for account switching
- `test_chat_router.py` — +3 tests for search type detection
- `test_repl_cmds.py` — +3 tests for health command
- `test_cli_welcome.py` — +2 tests for health and session history
- `test_cli_chat.py` — +1 test for quota error guidance
- **Total: 816 tests passing** (788 + 28 new)

---

## [5.1.0] - 2026-05-11

### Added

#### REPL Slash Commands — Stats, Routing, Model Control
- **`maggy/cli_repl_cmds.py`** — 9 command handlers for the interactive REPL:
  - `/stats` — Budget + model performance summary (spend, status, reward heatmap)
  - `/budget` — Detailed per-provider breakdown with visual progress bar
  - `/route` — Routing rules, task type overrides, model strengths/success rates
  - `/models` — Full reward heatmap grid by model × task type × blast tier
  - `/use claude,codex` — Restrict routing to specific models for this session
  - `/use all` — Remove model restriction
  - `/config` — Configuration summary (codebases, routing mode, budget limit)
  - `/claude-md` — Render project's CLAUDE.md in terminal
  - `/help` — List all available commands
- **`SessionState`** dataclass — Mutable session-level state (session_id, working_dir, allowed_models)
- **`dispatch()`** router — Parses slash commands, routes to handlers, returns True if handled
- **`GET /api/routing/rules`** endpoint — Exposes routing mode, task type overrides, model performance
- **`allowed_models`** field on `RoutedMessageRequest` — Server-side model restriction: if routed model not in allowed list, picks first allowed model with updated reason

#### Qwen3-Coder Benchmarks
- **75.7 tok/s average** — 3.4× faster than Qwen2.5-Coder (22.1 tok/s), 2× faster than Claude API (37.4 tok/s)
- MoE architecture (3.3B active / 30B total params) on M4 Max 128GB
- Quality: 10/10 BST correctness, 9/10 async rate limiter (token bucket + asyncio.Lock)
- Cold start: ~13s model load; hot runs: <100ms start

#### mWP Mindset — Full Framework
- **`skills/base/SKILL.md`** — Added complete mWP section with 11-Star Framework (Brian Chesky), mWP planning checklist (obvious → magical → multiplier)
- **`routing_rules.py`** — Expanded mWP convention injected into all CLI prompts (codex, kimi, qwen3, claude) with 3-question framework and 11-star reference

### Changed
- **`cli_chat.py`** — Integrated `SessionState` and `dispatch()` from `cli_repl_cmds`; passes `allowed_models` to `chat_send_routed()`; mode hint now shows `/help for commands`
- **`cli_client.py`** — Added `budget_by_provider()`, `routing_rules()` methods; updated `chat_send_routed()` signature to accept `allowed_models`
- **`benchmark-results.md`** — Qwen3-Coder results filled in (was TBD), quality assessment section added

### Tests
- `tests/test_repl_cmds.py` — 10 tests (dispatch routing, stats, budget, route, models, use, claude-md, help)
- `tests/test_cli_chat.py` — Updated 2 assertions for `allowed_models=None` parameter
- **Total: 653 tests passing** (643 maggy + 10 session detect)

---

## [5.0.0] - 2026-05-10

### Added

#### Interactive Chat — Session Takeover
- **`maggy/services/chat.py`** — ChatManager for interactive Claude sessions with SSE streaming
  - Auto-connects to all active CLI sessions (Claude, Codex, Kimi) via ActivityService process scanning
  - Session continuity with `--resume <session-id>` for multi-turn conversations
  - `CLAUDECODE` env var stripping to allow nested Claude subprocess spawning
  - `--verbose` flag for `--output-format stream-json` compatibility
  - Deduplication via dict keyed by project name
- **`maggy/services/chat_context.py`** — Context builder for session enrichment
  - Path-based history matching (not just exact project name) via `_path_candidates()`
  - `_SKIP_DIRS` set prevents matching common system directories (Users, Documents, Library)
  - Recent prompt injection from activity data per project
  - Claude `session_id` resolution from `~/.claude/history.jsonl` for true `--resume`
- **`maggy/api/routes_chat.py`** — Chat API (5 endpoints)
  - `POST /api/chat/auto-connect` — detect all active sessions, enrich with history context
  - `POST /api/chat/sessions` — create session
  - `GET /api/chat/sessions` — list sessions
  - `GET /api/chat/sessions/{id}` — get session + messages
  - `POST /api/chat/sessions/{id}/send` — send message, stream response via SSE
  - `DELETE /api/chat/sessions/{id}` — delete session
- **Chat UI** in `app.js` — full web-based chat interface
  - Auto-connects on tab load, shows all active project sessions in sidebar
  - Message thread with user/Claude bubbles
  - SSE EventSource for real-time streaming
  - Session history context display
  - New session creation from active + configured projects

#### Auto-Bootstrap — No Empty Tabs
- **`_bootstrap()` in `main.py`** — seeds all services on startup
  - `history.analyze()` — parses CLI sessions immediately (260+ sessions, 11,994 prompts)
  - `introspector.analyze()` — collects signals, emits events
  - `_seed_cikg()` — scans configured codebases, creates nodes for repos + detected languages

#### UI Navigation Cleanup
- **Grouped navigation** — 9 flat tabs reorganized into 3 logical groups:
  - **Work** (Chat, Tasks, Watching) — things you do
  - **Intel** (Competitors, Insights) — things you learn
  - **System** (gear dropdown: Budget, Models, Forge, Settings) — things you configure
- **Tab renames** — Inbox→Tasks, Followed→Watching, Process→Insights
- **Chat is default tab** — loads on startup, auto-connects immediately
- **Gear dropdown** — system tabs collapsed into icon menu, reduces nav clutter
- **Section labels** — tiny uppercase "WORK" / "INTEL" separators

#### Process Intelligence Tab Enhancement
- Parallel fetch of activity, history, improve, events, CIKG data
- Health signals display (routing, memory, reliability, cost percentages)
- Live activity section showing active sessions + recent prompts
- Session patterns from history analysis
- Button spinner feedback + success toast on Analyze History / Self-Improve

#### Infrastructure
- **No-cache static middleware** — `_NoCacheStatic` adds `Cache-Control: no-store` to `/static`
- **Cache-busting** — `?v=3` on script tag
- **`showToast()`** — green success notification for async operations

### Security
- **Chat path validation** — `project_path` now validated against configured codebase roots (blocks arbitrary filesystem access via `--dangerously-skip-permissions`)
- **Chat streaming lock** — per-session `asyncio.Lock` rejects concurrent `/send` requests, preventing duplicate subprocess spawning and workspace corruption

### Fixed
- Engram `expire_engrams` referencing `self` outside class context
- `auto_connect` returning duplicate sessions for same project
- `CLAUDECODE` env var blocking nested Claude subprocess spawning
- `--verbose` flag required when using `--output-format stream-json` with `-p`
- History matching missing projects stored under parent dir name (e.g. "AI-Playground" vs "claude-skills-package")
- Process tab buttons doing nothing due to browser-cached old JS
- 500-row limit in history store masking projects — switched to aggregated report data

### Changed
- Default tab: `inbox` → `chat`
- Org name in config: `"Your Org"` → read from `~/.maggy/config.yaml`
- README fully rewritten to reflect current feature set (was still describing MVP)

### Tests
- `tests/test_chat.py` — 17 tests (ChatManager + AutoConnect)
- `tests/test_chat_context.py` — 18 tests (path candidates, history matching, prompts, session ID)
- Total: **466 tests passing**

---

## [4.0.0] - 2026-05-05

### Added

#### Polyphony — Multi-Agent Orchestration (Core)
- **`scripts/polyphony/`** — Full multi-agent orchestration package with container-isolated workspaces. Each agent session runs in its own Docker container with independent git branches.
- **Domain models** (`models.py`) — Task, Identity, AgentProfile, RunSpec, Result dataclasses
- **Task state machine** (`state_machine.py`) — DISCOVERED -> CLAIMED -> ROUTED -> PROVISIONED -> RUNNING -> VERIFYING -> LANDED with FAILED/BLOCKED paths
- **SQLite store** (`store.py`) — Persistent CRUD for tasks, run_specs, results with state audit log
- **YAML config** (`config.py`) — Configuration loading from `~/.polyphony/` with defaults merging
- **5-dimension complexity scoring** (`scoring.py`) — Cyclomatic depth, fan-out, security boundary, concurrency, domain invariants (0-10 scale)
- **Pure function router** (`router.py`) — Task x Policy -> RunSpec, first-match rules with fallback chains
- **Identity broker** (`identity.py`) — Named credential bundles with volume mounts and env overlays
- **Workspace manager** (`workspace.py`) — Per-task git clone lifecycle with `--reference`/`--dissociate` mirror support
- **Docker runtime** (`runtime.py`) — Container create/start/stop/wait/logs/rm lifecycle
- **Event parser** (`events.py`) — NDJSON/stream-json parsing from container stdout
- **Orchestrator** (`orchestrator.py`) — Supervisor loop: discover -> claim -> route -> provision -> run -> verify -> land
- **Agent adapters** (`adapters/`) — Claude (`-p --output-format stream-json`), Codex (`exec --full-auto`), Kimi (`--print -y`)
- **Work sources** (`sources/`) — GitHub Issues via `gh api`, local SQLite task queue
- **CLI** (`__main__.py`) — `polyphony {init|spawn|status|cleanup}` commands
- **Skill** (`skills/polyphony/SKILL.md`) — Full documentation for the orchestration system
- **Commands** — `/polyphony-init`, `/polyphony-spawn`, `/polyphony-status`
- **Templates** — `Dockerfile.polyphony`, `polyphony-config.yaml`, `polyphony-identities.yaml`, `polyphony-agents.yaml`, `polyphony-routing.yaml`
- **Spec** (`docs/polyphony-spec.md`) — Full specification reference (12 sections)
- **173 tests** across 13 test files with full TDD coverage

---

## [3.6.1] - 2026-05-04

### Changed
- **Complexity-based delegation replaces file-count heuristic** (`skills/cross-agent-delegation/SKILL.md`) — Kimi delegation now scored on 5 dimensions (cyclomatic depth, fan-out, security boundary, concurrency, domain invariants) × 0-2 each, sourced from iCPG signals + Claude reasoning. Routing: 0-3 → Kimi solo, 4-6 → Kimi + Codex auto-review, 7-10 → Claude direct. Adds trivial-case shortcut (<2 files + no risk keywords → auto-Kimi without scoring) and single-dimension override (7+ in any one dim keeps Claude). PR #16.

---

## [3.6.0] - 2026-05-03

### Added

#### Cross-Tool Compatibility (Claude + Kimi + Codex)
- **`scripts/detect-agents.sh`** — Detects installed AI CLI tools (Claude Code, Kimi CLI, Codex CLI)
- **`scripts/install-skills.sh`** — Reusable skill copier for any target directory
- **`templates/AGENTS.md`** — Codex project instructions template (mirrors CLAUDE.md with `.agents/skills/` paths)
- **`templates/config.toml`** — Hooks in TOML format for Kimi/Codex compatibility
- **`scripts/convert-hooks-to-toml.sh`** — JSON to TOML hook converter (requires jq)
- **`commands/sync-agents.md`** — `/sync-agents` command for cross-tool config sync
- **`install.sh`** auto-detects and installs skills to `~/.kimi/skills/` and `~/.codex/skills/`
- **`/initialize-project`** question 9: "Which AI CLI tools do you use?" with auto-detection
- Cross-tool directories (`.kimi/`, `.codex/`, `.agents/`) added to `.gitignore` template

#### Cross-Agent Intelligence
- **`templates/codex-auto-review.sh`** — Stop hook that auto-runs Codex review on changed files
  - Checks for Critical/High severity issues only
  - Exit 0 = pass, Exit 2 = feed findings back to Claude for fixing
  - Truncates diff to 8000 chars to prevent Codex token overflow
  - Gracefully skips if Codex CLI not installed
- **`skills/cross-agent-delegation/SKILL.md`** — Delegation skill with:
  - Tool detection (checks `command -v` for each CLI)
  - iCPG blast radius rules for Kimi delegation (<=3 files suggest Kimi, 4-8 offer option, 9+ stay Claude)
  - iCPG mandatory pre-task queries for all agents (prior, constraints, risk)
  - Mnemos mandatory memory lifecycle for all agents (goals, checkpoints, fatigue)
  - 10-step cross-agent workflow summary
- **Codex auto-review Stop hook** added to `settings.json` (after TDD, before iCPG record, 120s timeout)
- **Codex auto-review TOML hook** added to `config.toml` for Kimi/Codex compatibility
- **Cross-Agent Workflow** section added to both `CLAUDE.md` and `AGENTS.md` templates
- **`cross-agent-delegation/`** added to always-copy skill list in `/initialize-project`

#### Tests
- **`tests/test_cross_tool.py`** — 12 tests for cross-tool compatibility (detect-agents, install-skills, templates, sync-agents)
- **`tests/test_cross_agent.py`** — 22 tests for cross-agent intelligence (codex-auto-review, delegation skill, settings.json hook ordering, config.toml, template refs)

### Changed
- `install.sh` bumped to v3.6.0
- `install.sh` now makes `codex-auto-review.sh` executable during install
- `tests/validate-structure.sh` includes cross-tool template validation
- Total skills increased from 60 to **61 skills**
- Total tests: 62 pytest + 238 validation checks

---

## [3.5.2] - 2026-04-22

### Fixed
- **Hook error behavior revised** — the 3.5.1 fix silently no-op'd missing scripts, which hid real installation problems. Hook commands now:
  - **Fail loud on real errors** — if the script exists and crashes, its stderr + non-zero exit propagate to Claude Code so you can debug
  - **Print one actionable line on missing installs** — `[claude-bootstrap] hook script 'X' not installed — run <claude-bootstrap>/install.sh …` and exit 0 (no blocking error, but you see exactly what to do)
  - **Use `exec` to run the resolved script** — exit code + stderr pass through unchanged
- **Hook scripts stop swallowing stderr** — removed 19 instances of `2>/dev/null` across `mnemos-*.sh`, `icpg-*.sh`, and `tdd-loop-check.sh`. Python tracebacks and Python stderr now surface to Claude Code's hook diagnostics. Command substitution (`$(...)`) only captures stdout, so this doesn't affect any value parsing.

## [3.5.1] - 2026-04-21

### Fixed
- **PreToolUse hook "Bash hook error" on any tool call.** `templates/settings.json` declared hook commands as relative paths (`scripts/mnemos-*.sh`) that don't exist in most projects — the scripts live in `templates/` and nothing copies them to `<project>/scripts/`. Every tool call triggered a hook-not-found error shown as `PreToolUse:Bash hook error` in the session (non-blocking but noisy).
- Hook commands now try `.claude/scripts/<name>.sh` first (project-local override), fall back to `$HOME/.claude/templates/<name>.sh` (always installed by `install.sh`), and no-op cleanly when neither exists. Applied to all 8 hook script references across `PreCompact`, `PreToolUse`, `PostToolUse`, `Stop`, and `SessionStart`.

---

## [3.5.0] - 2026-04-19

### CI
- **`skill-review.yml`**: both `tessl` and `skills-ref` jobs now space-join the detected-skills list before writing to `$GITHUB_OUTPUT`. The old plain `echo "skills=$CHANGED"` with a multi-line `$CHANGED` value failed GHA's output parser ("Invalid format") AND broke the downstream `for skill in ${{ outputs.skills }}` loop. Space-joining keeps both happy and unblocks multi-skill PRs (like this one, which touches both `maggy/` and `mnemos/`).

### Third review pass fixes (Copilot iteration)
- **Package renamed `src/` → `maggy/`.** The top-level `src` package name was a well-known Python packaging anti-pattern that collides with other projects. The Python code now lives at `claude-bootstrap/maggy/maggy/` and imports as `from maggy.X import Y` (matching the icpg/mnemos/skill_lint convention). `pyproject.toml` entrypoint + includes, `install.sh`, and the launcher commands updated to `python3 -m maggy.main`.
- **SQLite PRAGMAs** — `InboxService` and `CompetitorService` open connections via a shared helper that sets `journal_mode=WAL`, `foreign_keys=ON`, and `busy_timeout=30000`. Matches the convention used by `scripts/icpg/store.py` and prevents "database is locked" errors when the FastAPI handlers race the heartbeat worker.
- **Host-safety startup check** — `create_app()` now refuses to boot when `dashboard.auth_mode="local"` is combined with a non-loopback host (anything other than `127.0.0.1`/`localhost`/`::1`). Execute spawns `claude --dangerously-skip-permissions`, so binding to `0.0.0.0` with no auth would expose that to the local network. Users are directed to switch to token auth or rebind.
- **`is_configured()` no longer accepts `linear`** — `providers.build()` raises `NotImplementedError` for Linear (stub), so treating it as configured would crash `create_app()` at startup. Now returns `False` cleanly.
- **`providers.build()`** raises `NotImplementedError` with a clear "use github or asana" hint for `linear`.
- **GitHub provider logs non-200s** in `list_tasks` — previously a 401/403/404 silently yielded an empty inbox. Now WARNING-logged with the repo slug and first 200 chars of the response body for debuggability.
- **Removed unused `timedelta` import** from `inbox.py`.

### Second review pass fixes (CodeRabbit iteration 2)
- `AsyncAnthropic` used in async methods — inbox ranking + competitor discovery + daily briefing no longer block the event loop on multi-second LLM round-trips
- RSS/Google News feed date handling uses `parsedate_to_datetime` + ISO parser and compares real `datetime` objects — RFC 822 strings aren't lexicographically ordered (day-of-week cycles weekly)
- iCPG CLI invocation fixed: `python3 -m scripts.icpg query prior --text ...` against the real argparse entrypoint, not the utility submodule `scripts.icpg.symbols` which has no `__main__`
- Background `asyncio.create_task()` reference kept in a set + `add_done_callback(discard)` so GC can't kill the TDD pipeline mid-run
- `GitHubIssuesProvider.list_followed()` and `search_tasks()` refuse to run when `repos` is empty (otherwise the query has no repo filter and searches all of public GitHub)
- `AsanaProvider.list_tasks()` drops the dead `completed_filter` variable and skips sending `completed_since=""` (Asana validator rejects empty string); filters `closed` state properly
- `install.sh` enforces Python 3.11+ minimum (was only checking `python3` existed)
- `/static/index.html`: added CSP meta tag; Font Awesome pinned with SHA-384 SRI; Tailwind Play CDN annotated with vendor-for-prod TODO
- `static/app.js`: added `jsStr()` for JS-string-context escaping in inline onclick handlers (esc() alone leaves single quotes intact — XSS via ticket titles was possible)
- `regenerateBriefing()` catches and displays errors instead of swallowing them
- `commands/maggy.md`: reads `dashboard.host`/`dashboard.port` from config before probing health (was hardcoded 8080)
- `commands/maggy-init.md`: removed the "offer to write to .env" suggestion — the runtime doesn't load that file, so it would leave tokens on disk with no reader
- `config.example.yaml`: removed the Linear section (stub only, shouldn't be in the advertised selectable set)
- `PLAN.md`: config sample aligned with the actual runtime schema (removed spurious `config:` nesting)
- `maggy/README.md`: install path no longer assumes `~/Documents/AI-Playground/...`; uses relative `cd claude-bootstrap/maggy`
- `providers/__init__.py`: `__all__` alphabetized (RUF022)
- `skills/maggy/SKILL.md`: explicit permission-model disclosure box explaining the `--dangerously-skip-permissions` tradeoff and the `working_dir` whitelist mitigations

### Added
- **Maggy — AI engineering command center** (optional extension under `maggy/`)
  - Local FastAPI + vanilla JS dashboard; install with `maggy/install.sh`, zero build step
  - Provider abstraction: `GitHubIssuesProvider`, `AsanaProvider`, `LinearProvider` (stub) implement a single `IssueTrackerProvider` Protocol — swap trackers without touching services
  - AI-prioritized inbox with 30-min SQLite cache; stale-cache fallback when provider is unavailable
  - Generic competitor discovery + RSS + Google News monitoring with daily AI briefing (cached per day)
  - TDD execute pipeline (plan → tests → implement) spawns `claude -p --dangerously-skip-permissions` locally in the right codebase, with iCPG context auto-injected from the bootstrap's iCPG CLI
  - Config-driven (`~/.maggy/config.yaml`) — no hardcoded org IDs, repo names, or competitor lists
  - `/maggy` command launches dashboard; `/maggy-init` runs interactive setup
  - `skills/maggy/SKILL.md` documents capabilities; README skills table updated
- Maggy skill included in the skills table (fixes RI002 lint error for this PR)

### Fixed
- Added YAML frontmatter to `skills/mnemos/SKILL.md` (fixes FM001 lint error that was blocking CI on main)
- Skill lint now passes across all 60 skills

### Security (Maggy)
- RSS URL validation before fetching competitor feeds — blocks loopback, link-local, private-network, and non-HTTP(S) targets (SSRF prevention)
- `safeHref()` in dashboard JS — only allows `http(s)`/`mailto` schemes in external links, blocks `javascript:`/`data:` URIs that would slip past HTML escaping
- `working_dir` validated against configured codebase roots before launching Claude Code — prevents arbitrary-cwd execution of `--dangerously-skip-permissions`
- Execute-mode input validated via `Literal["tdd", "plan"]`; typos rejected at request boundary
- GitHub `_decode_id()` returns `None` on malformed input instead of raising — surfaces as 404 not 500
- LLM ranking output validated (index range, numeric rank, dedupe) before applying

### Resilience (Maggy)
- `provider.list_tasks` failure falls back to last cached ranking (flagged `stale=true`) instead of 500
- Route-level `_require_configured()` returns 503 + onboarding hint when `~/.maggy/config.yaml` is missing, instead of dereferencing `None` services
- `is_configured()` requires provider credentials (token) in addition to org/repos; refreshes cache on each check
- Claude subprocess kill on timeout (`proc.kill()` + `await proc.wait()`), non-zero exits marked as failed sessions
- `_run_claude()` returns `(ok, output)` tuple — TDD pipeline now aborts chain on first-step failure
- Competitor news events use deterministic SHA-256 IDs with `INSERT OR IGNORE` — prevents duplicate rows on cursor reset / overlapping scans

### Changed (Maggy)
- `pyproject.toml` console script `maggy = "src.main:main"` (proper callable) instead of `"src.main:app"` (ASGI instance)

---

## [3.4.1] - 2026-04-10

### Fixed
- Fixed broken `build-backend` in all three pyproject.toml files (icpg, mnemos, skill_lint). Changed `setuptools.backends._legacy:_Backend` to `setuptools.build_meta`. (Community reported)

### Added
- Cheeky personality section in CLAUDE.md template for new projects

---

## [3.4.0] - 2026-04-07

### Added
- **Skill Quality Gates** — Automated linter, CI integration, and behavioral evals
  - `scripts/skill_lint/` — Python package with 20 check rules across 4 categories:
    - Frontmatter (FM001-FM009): YAML validation, name/description/field checks
    - Spec (SP001-SP003, SR001): SKILL.md existence, line count limits, skills-ref integration
    - Content (CQ001-CQ006): ASCII art detection, vague phrase detection, filler intensity, code block density, stale references, H1 heading
    - References (RI001-RI002): Cross-skill link validation, README coverage
  - CLI: `PYTHONPATH=scripts python3 -m skill_lint [--format text|json] [--severity error|warning|info] [--skill NAME] [--fail-on error|warning] skills/`
  - Inline suppression: `<!-- skill-lint: disable=SP002 -->` in first 10 lines
  - 28 unit tests covering all check modules, report formatters, and CLI
  - `.github/workflows/skill-lint.yml` — Runs linter + tests on PR/push to skills/ or scripts/skill_lint/
  - `.github/workflows/skill-review.yml` — Tessl skill review + skills-ref validation on PRs (requires TESSL_TOKEN)
  - `evals/` — 18 behavioral eval scenarios for 15 skills with deterministic and LLM-judged criteria
  - `evals/run-evals.sh` — Eval runner with baseline comparison mode
- Updated `CONTRIBUTING.md` with quality gate requirements and linter usage

### Scan Results (59 skills)
- Errors: 1 (mnemos/ missing frontmatter)
- Warnings: 85 (19 skills over 500 lines, 30+ with ASCII art)
- Clean: 3 skills

---

## [3.3.2] - 2026-04-07

### Fixed
- Removed stale `Load with: base.md` line from all 53 skills. Since v3.0, base skill loads via `@include` in CLAUDE.md, not per-skill. The leftover line caused confusion about missing files. (Fixes #13)

### Housekeeping
- Closed #10 (Gen Agent Trust Hub security audit) — false positives from scanning markdown code samples as executable code.
- Closed #12 (Dispatch discoverability) — will address skill description metadata in a future cleanup pass.
- Closed #11 (Low quality skills) — will revisit with specific eval criteria.

---

## [3.3.1] - 2026-04-03

### Added
- **Post-Compaction Task Restoration** (Two-Layer Defense)
  - `templates/mnemos-post-compact-inject.sh` — PreToolUse hook (no matcher, fires on ALL tools) that detects compaction via `.mnemos/just-compacted` marker and re-injects the full checkpoint into Claude's context. Fast path ~5ms when no compaction, ~100ms injection when triggered.
  - `build_task_narrative()` in `checkpoint.py` — Reads signals.jsonl to build human-readable summary of recent activity (files edited, read counts, focus area, error patterns). Automatically included in checkpoints.
  - `format_for_post_compact_injection()` in `checkpoint.py` — Formats checkpoint as structured restoration block with goal, constraints, activity narrative, progress, key files, git state.
  - Compaction marker system (`write_compaction_marker`, `check_compaction_marker`, `consume_compaction_marker`) — Atomic marker write/consume to prevent parallel injection.

### Changed
- **`mnemos-pre-compact.sh`** — Enhanced from advisory to assertive. Now includes inline checkpoint content in preservation instructions, writes compaction marker for Layer 2, builds task narrative from signals, and uses stronger verbatim framing.
- **`CheckpointNode`** — Added `task_narrative` (str) and `recent_files` (list[dict]) fields for richer checkpoint content.
- **`settings.json`** — Added new PreToolUse entry (no matcher) for `mnemos-post-compact-inject.sh` before the existing Edit|Write matcher.
- **`SKILL.md`** — Documented post-compaction recovery mechanism.
- **`README.md`** — Rewrote Mnemos section with two-layer defense architecture, resilience failure mode table, "why not just a plain file" rationale, and post-compaction restoration flow diagram.

## [3.3.0] - 2026-04-03

### Added

#### Mnemos — Task-Scoped Memory Lifecycle
Agents crash when context fills up. Claude Code's compaction is lossy — it summarizes everything uniformly. Mnemos solves this with typed memory, continuous fatigue monitoring, and checkpoint/resume.

- **`scripts/mnemos/`** — Python package (zero external dependencies)
  - `models.py` — MnemoNode (8 types with typed eviction policies), FatigueState, CheckpointNode
  - `store.py` — SQLite MnemoGraph storage with mnemo_nodes, checkpoints, fatigue_log tables
  - `fatigue.py` — 4-dimension fatigue model from passively observed signals (no agent cooperation needed)
  - `signals.py` — Behavioral signal collection from hooks (scope scatter, re-read ratio, error density)
  - `checkpoint.py` — CheckpointNode write/load with iCPG bridge, git state capture, formatted resume output
  - `consolidation.py` — Micro-consolidation: compress ResultNodes, evict cold ContextNodes, decay weights
  - `__main__.py` — CLI: init, status, fatigue, checkpoint, resume, consolidate, nodes, add, bridge-icpg

- **4-Dimension Fatigue Model** (all passively observed from hooks):
  - Token utilization (0.40) — real context_window.used_percentage from statusline
  - Scope scatter (0.25) — unique directories in recent tool calls (from PreToolUse)
  - Re-read ratio (0.20) — files Read more than once, strongest signal of context loss (from PreToolUse)
  - Error density (0.15) — failed tool calls ratio (from PostToolUse)
  - States: FLOW (0-0.4), COMPRESS (0.4-0.6), PRE-SLEEP (0.6-0.75), REM (0.75-0.9), EMERGENCY (0.9+)

- **Auto-Feeding Token Signal**:
  - `templates/mnemos-statusline.sh` — Statusline receives `context_window` JSON from Claude Code, writes `fatigue.json`, delegates display to ccusage (if installed) or shows simple context %
  - JSONL fallback in PostToolUse — reads conversation JSONL to estimate context usage when statusline not configured (0.75 correction factor for cache overhead, ~1-2pp accuracy)
  - `statusLine` config added to `templates/settings.json` — auto-activates on install, no separate configuration needed

- **Fatigue-Aware Hook System**:
  - `templates/mnemos-pre-edit.sh` — PreToolUse: logs file signals, reads fatigue, auto-checkpoints at 0.60+, auto-consolidates at 0.40+, includes iCPG context
  - `templates/mnemos-post-tool.sh` — PostToolUse: logs tool success/failure for error density, auto-feeds token signal from JSONL when statusline is stale
  - `templates/mnemos-session-start.sh` — SessionStart: loads checkpoint on resume, bridges iCPG state
  - `templates/mnemos-pre-compact.sh` — PreCompact: emergency checkpoint + typed preservation priorities (NEVER DROP goals/constraints, OK TO DROP file contents)
  - `templates/mnemos-stop-checkpoint.sh` — Stop: writes final session checkpoint

- **MnemoNode Eviction Policies**:
  - GoalNodes, ConstraintNodes, CheckpointNodes, HandoffNodes: NEVER evicted
  - ResultNodes, WorkingNodes, SkillNodes: compressed first (summary kept), then evictable
  - ContextNodes: evictable when activation weight drops below threshold

- **iCPG Bridge**: `mnemos bridge-icpg` imports ReasonNodes as GoalNodes, postconditions/invariants as ConstraintNodes

- **Skill + Commands**:
  - `skills/mnemos/SKILL.md` — Full skill documentation with fatigue states, CLI reference, agent instructions
  - `commands/mnemos-status.md` — `/mnemos-status` slash command
  - `commands/mnemos-checkpoint.md` — `/mnemos-checkpoint` slash command

- **Documentation**:
  - `docs/mnemos-implementation.md` — Implementation addendum for the Mnemos RFC

### Changed

#### iCPG Fixes
- `scripts/icpg/bootstrap.py` — Fixed `_get_commits()` git log parsing (was producing 0 symbols linked)
- `scripts/icpg/drift.py` — Added `check_file_drift()` for fast, file-scoped drift (O(symbols-in-file))
- `scripts/icpg/__main__.py` — Added `drift file <path>` subcommand, `_resolve_path()` for relative path handling
- `templates/icpg-pre-edit.sh` — Now includes file-scoped drift detection alongside context and constraints

#### Settings Template
- `templates/settings.json` — Added `statusLine` config for auto-feeding token signal, Mnemos hooks replace standalone iCPG hooks, added PostToolUse hook, added mnemos permission allows
- `templates/CLAUDE.md` — Added `@.claude/skills/mnemos/SKILL.md` to skill includes

---

## [3.2.0] - 2026-04-02

### Added

#### iCPG Full Implementation (Intent-Augmented Code Property Graph)
- **`scripts/icpg/`** — Python CLI package implementing the full iCPG RFC v8
  - `models.py` — ReasonNode, Symbol, Edge, DriftEvent data models with Design by Contract (preconditions, postconditions, invariants)
  - `store.py` — SQLite storage layer with 4 tables, WAL mode, indexed queries
  - `symbols.py` — Language-aware symbol extraction: Python (AST), TypeScript/JS (regex), Go, Rust, Elixir
  - `drift.py` — 6-dimension drift detection: spec, decision, ownership, test, usage, dependency
  - `contracts.py` — Design by Contract layer with LLM inference (Claude/OpenAI) and heuristic fallback
  - `vectors.py` — Tiered duplicate detection: ChromaDB → TF-IDF → exact match fallback
  - `bootstrap.py` — Git history inference: cluster commits, LLM-infer ReasonNodes, link symbols
  - `__main__.py` — CLI with subcommands: init, create, record, query, drift, bootstrap, status
  - `pyproject.toml` — pip-installable with optional deps (chromadb, sentence-transformers, openai)

- **3 Canonical Pre-Task Queries** (RFC Section 2.1):
  - `icpg query prior "<goal>"` — Vector-based duplicate detection before starting work
  - `icpg query constraints <file>` — Get invariants/contracts for files being modified
  - `icpg query risk <symbol>` — Drift score, ownership history, modification count

- **Hook Integration**:
  - `templates/icpg-pre-edit.sh` — PreToolUse hook: injects intent context + constraints before every Edit/Write
  - `templates/icpg-stop-record.sh` — Stop hook: auto-records symbols to active ReasonNode after implementation

- **Slash Commands**:
  - `commands/icpg-impact.md` — `/icpg-impact <id>` blast radius visualization
  - `commands/icpg-why.md` — `/icpg-why <symbol>` trace symbol to creating intent
  - `commands/icpg-drift.md` — `/icpg-drift` full drift report across all dimensions
  - `commands/icpg-bootstrap.md` — `/icpg-bootstrap` infer intents from git history

### Changed

#### iCPG Skill Rewrite
- **`skills/icpg/SKILL.md`** — Complete rewrite aligning with RFC v8
  - ReasonNode now carries formal contracts (preconditions, postconditions, invariants)
  - Drift formally defined as predicate failure (not vague metric)
  - 6-dimension drift model with 0-1 severity scores per dimension
  - CLI reference for all `icpg` subcommands
  - Hook integration documentation (PreToolUse + Stop)
  - Agent Teams integration section with updated pipeline

#### Agent Team iCPG Integration
- **`skills/agent-teams/agents/team-lead.md`** — Team lead now creates ReasonNodes and checks for duplicates before creating task chains
- **`skills/agent-teams/agents/feature.md`** — Feature agents query constraints/risk before implementing, auto-record symbols after
- **`skills/agent-teams/agents/quality.md`** — Quality agent runs drift checks during GREEN verify, validates spec-intent alignment
- **`skills/agent-teams/SKILL.md`** — Updated "Integration with Existing Skills" table with iCPG + code-graph entries

#### Settings Template
- **`templates/settings.json`** — Added PreToolUse hook (icpg-pre-edit.sh), Stop hook extension (icpg-stop-record.sh), icpg permission allows

---

## [3.1.0] - 2026-04-02

### Added

#### iCPG Skill (Initial Spec)
- **`skills/icpg/SKILL.md`** — Initial iCPG skill spec (now superseded by 3.2.0 full implementation)

---

## [3.0.0] - 2026-03-31

### Breaking Changes

This release aligns Claude Bootstrap with how Claude Code actually works internally. Several features that referenced non-existent infrastructure have been replaced with real Claude Code mechanisms.

- **Ralph Wiggum plugin removed** — The `/ralph-loop` command, `claude-plugins-official` marketplace, and plugin stop-hook mechanism never existed in Claude Code. All references removed.
- **TDD loops now use real Stop hooks** — Claude Code's Stop hook (exit code 2 feeds stderr back to the model) replaces the fake plugin. `scripts/tdd-loop-check.sh` runs tests/lint/typecheck after each response.
- **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` removed** — Agent spawning and task management are standard Claude Code features, not gated behind an env var. All references removed.
- **CLAUDE.md template uses `@include` directives** — Skills are loaded via `@.claude/skills/base/SKILL.md` syntax which Claude Code resolves at parse time (recursive, max depth 5, cycle detection).
- **Quality gates moved from CLAUDE.md to `.claude/rules/`** — Rules use YAML frontmatter with `paths:` globs for conditional activation.
- **"STRICTLY ENFORCED" / "Non-Negotiable" language removed** — Claude Code treats CLAUDE.md as user-level context (not system prompt) wrapped in `<system-reminder>` tags with "may or may not be relevant" caveat. Aggressive language wastes tokens without creating binding constraints.

### Added

#### Stop Hook TDD Loops
- **`templates/tdd-loop-check.sh`** — Universal TDD loop script for Stop hooks
  - Runs tests, lint, typecheck after each Claude response
  - Exit 0 (all pass) = Claude stops; Exit 2 (failures) = stderr fed back to Claude
  - Iteration counter with configurable max (default 25)
  - Detects project type (Node.js/Python) and runs appropriate commands
  - Distinguishes code errors (loop) from environment errors (stop)

- **`templates/settings.json`** — Pre-configured Claude Code settings
  - Stop hook configuration for TDD loops
  - SessionStart hook for auto-context injection
  - Permission allow rules: test runners, linters, git read commands, gh CLI
  - Permission deny rules: `rm -rf`, `git push --force`, writing `.env` files
  - Ready to copy into any project's `.claude/settings.json`

#### Conditional Rules System
- **`.claude/rules/` directory** with 7 rule files using proper YAML frontmatter:
  - `quality-gates.md` — Always active: 20 lines/function, 200 lines/file, 3 params, 80% coverage
  - `tdd-workflow.md` — Always active: RED-GREEN-VALIDATE workflow
  - `security.md` — Always active: no secrets in code, parameterized queries, bcrypt
  - `react.md` — Active on `**/*.tsx`, `**/*.jsx`, `src/components/**`
  - `typescript.md` — Active on `**/*.ts`, `**/*.tsx`
  - `python.md` — Active on `**/*.py`
  - `nodejs-backend.md` — Active on `src/api/**`, `src/routes/**`, `server/**`

#### CLAUDE.local.md
- **`templates/CLAUDE.local.md`** — Private developer override template
  - Not checked into git (higher priority than project CLAUDE.md)
  - Template with common overrides: preferences, local environment, quality gate tweaks

#### Agent Definition Frontmatter
- All 6 agent definitions now use proper Claude Code frontmatter:
  - `name` — Agent identifier
  - `description` — When-to-use hint
  - `model` — Model selection (sonnet, inherit)
  - `tools` — Tool allowlist (e.g., `[Read, Glob, Grep, TaskCreate]`)
  - `disallowedTools` — Tool denylist (e.g., `[Write, Edit, Bash]`)
  - `maxTurns` — Maximum agentic turns before stopping
  - `effort` — Thinking depth (medium/high)

#### @include Directives in CLAUDE.md
- CLAUDE.md template now uses `@.claude/skills/base/SKILL.md` syntax
- Claude Code resolves these at load time (recursively inlined)
- Skills actually become part of the prompt instead of decorative text

#### CLAUDE.md Template Structure
- Added **Project Structure** section — tells Claude where things live without filesystem exploration
- Added **Key Decisions** section — prevents Claude from re-litigating settled architectural choices
- Added **Conventions** section — patterns Claude should follow (test colocation, API shape, etc.)
- Added **Don't** section — short guardrails (no .env writes, no secret leaks)
- Removed Session Persistence section (belongs in skills, not root template)

#### PreCompact Hook for Smarter Compaction
- **`templates/pre-compact.sh`** — PreCompact hook that injects project-specific preservation priorities into the compaction summarizer
  - Auto-detects project type (TypeScript, Python, Next.js, FastAPI, Flutter, etc.)
  - Finds schema files (Drizzle, Prisma, SQLAlchemy) and tells summarizer to preserve all schema discussion verbatim
  - Finds API directories and tells summarizer to preserve exact endpoint paths, request/response shapes
  - Extracts Key Decisions from CLAUDE.md and tells summarizer to reference them by name
  - Injects live git state (branch, uncommitted changes, staged files) into summary priorities
  - Tells summarizer to preserve exact error messages and fix context (not paraphrased)
  - Tells summarizer what NOT to preserve (dead ends, full file contents, formatting noise)
  - Zero overhead during normal usage — only runs when compaction fires
  - Configured in `.claude/settings.json` under `hooks.PreCompact`

#### Full Skill Frontmatter (all 57 skills)
- Added undocumented-but-functional Claude Code skill frontmatter to all 57 skills:
  - `when-to-use` — guidance for when Claude should invoke the skill
  - `user-invocable` — 11 skills are user-invocable (code-review, codex-review, gemini-review, security, existing-repo, ticket-craft, workspace, cpg-analysis, playwright-testing, ai-models), 46 are model-only
  - `effort` — thinking depth per skill (6 high, 47 medium, 4 low)
  - `paths` — file glob patterns for 24 language/framework/database skills (e.g., `["**/*.py"]` for Python, `["**/*.tsx"]` for React)
  - `allowed-tools` — restricted tool access for 3 review/security skills (`[Read, Glob, Grep, Bash]`)

### Changed
- `install.sh` now copies rules/, templates/, and no longer checks for Ralph Wiggum plugin
- `iterative-development/SKILL.md` completely rewritten for Stop hooks
- `base/SKILL.md` — Ralph Wiggum auto-invoke section replaced with Stop hook explanation
- `agent-teams/SKILL.md` — Removed experimental env var requirement
- `commands/spawn-team.md` — Removed env var check, removed Shift+Up/Down and Ctrl+T UI references
- All agent definitions in `skills/agent-teams/agents/` rewritten with frontmatter
- Total files: 57 skills + 7 conditional rules + 3 templates

### Removed
- All Ralph Wiggum plugin references (`/ralph-loop`, `/plugin install`, `--completion-promise`, `<promise>` tags)
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` env var requirement
- Plugin marketplace references (`claude-plugins-official`)
- `Shift+Up/Down` and `Ctrl+T` UI interaction assumptions
- "STRICTLY ENFORCED" and "Non-Negotiable" language throughout

### Migration

```bash
cd "$(cat ~/.claude/.bootstrap-dir)"
git pull
./install.sh

# Then in each project:
claude
> /initialize-project
# Will update to v3.0.0 structure
```

**Manual steps for existing projects:**
1. Copy `templates/settings.json` to `.claude/settings.json`
2. Copy `templates/tdd-loop-check.sh` to `scripts/tdd-loop-check.sh` and `chmod +x`
3. Replace skill listings in CLAUDE.md with `@include` directives
4. Copy `rules/` files to `.claude/rules/`
5. Add `CLAUDE.local.md` to `.gitignore`
6. Remove `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` from environment

---

## [2.7.0] - 2026-03-23

### Added

#### Tiered Code Graph System (MCP-based)
- **Code Graph skill** (`code-graph/SKILL.md`) - Always-on code intelligence via MCP
  - "Graph first, file second" workflow — Claude queries the graph before reading files
  - Integrates with codebase-memory-mcp: 14 MCP tools, 64 languages, sub-ms queries
  - Decision tables for when to use graph vs direct file reads
  - Workflow: LOCATE → UNDERSTAND → BLAST → TRACE → CHANGE → VERIFY
  - Anti-patterns guide for common graph-ignoring mistakes

- **CPG Analysis skill** (`cpg-analysis/SKILL.md`) - Opt-in deep code analysis
  - Tier 2: Joern CPG via CodeBadger MCP (40+ tools, AST+CFG+CDG+DDG+PDG)
    - Control flow graph analysis, data flow tracing, dead code detection
    - CPGQL query examples for common analysis patterns
    - 12 language support (Java, Python, TypeScript, Go, C/C++, etc.)
  - Tier 3: CodeQL MCP for interprocedural taint analysis and security auditing
    - OWASP vulnerability detection, source-to-sink data flow
    - 10+ languages including Rust (which Joern doesn't support)
  - Combined workflow: Tier 1 scope → Tier 2 flow → Tier 3 security

- **Graph tools installer** (`scripts/install-graph-tools.sh`)
  - Platform-detecting installer (macOS/Linux, ARM64/AMD64)
  - `--joern` flag for Tier 2 (Docker + Python setup)
  - `--codeql` flag for Tier 3 (CodeQL CLI + query packs)
  - `--all` flag for all tiers

- **Post-commit graph hook** (`hooks/post-commit-graph`)
  - Lightweight (~10ms) hook that signals codebase-memory-mcp file watcher
  - Filters to code files only, never blocks git workflow
  - Auto-installed by `/initialize-project`

- **Graph freshness check** (`hooks/workspace/check-graph-freshness.sh`)
  - Session-start advisory warns if graph data is stale
  - Cross-platform timestamp comparison (macOS/Linux)

#### Initialize Project Updates
- New question 4b: "Code graph analysis level?" (Standard/Deep/Security/Full)
- New Step 4b: Automatic MCP server configuration (`.mcp.json`)
- `.code-graph/` auto-added to `.gitignore`
- Post-commit graph hook auto-installed
- CLAUDE.md template now includes "Code Graph (MCP)" section
- Summary output shows graph tier configuration

### Changed
- Total skills increased from 55 to **57 skills**
- `install.sh` now copies `install-graph-tools.sh` to `~/.claude/`
- `install.sh` summary output includes graph tools commands

---

## [2.6.0] - 2026-02-14

### Added

#### AI-Native Ticket Writing
- **Ticket Craft skill** - Write Jira/Asana/Linear tickets optimized for Claude Code execution
  - INVEST+C criteria: standard INVEST plus "Claude-Ready" verification
  - 4 ticket templates: Feature, Bug, Tech Debt, Epic Breakdown
  - Claude Code Context section: file refs, pattern refs, verification commands, constraints
  - Claude Code Ready Checklist: 16-point validation before tickets enter sprint
  - Anti-patterns guide: 6 common ticket-writing mistakes that cause AI agents to fail
  - Story point calibration for AI agents (different from human estimation)
  - Epic slicing techniques: by workflow, data variation, user role, CRUD, happy path
  - Given-When-Then acceptance criteria format
  - Integration guide for Jira, Asana, Linear, and GitHub Issues
  - Maps tickets directly to the agent-teams 10-task pipeline

#### Bug Fixes
- **Fix pre-push hook false positive** - Hook was blocking pushes even when review passed with 0 Critical/High issues (fixes #8, reported by @shawnyeager)
  - `grep` pattern matched "Critical" in table headers and pass messages
  - Now checks for explicit `Status: ✅ PASS` / `Status: ❌` lines instead

#### Community Contributions
- **Flexible install directory** - Bootstrap can now be cloned anywhere, not just `~/.claude-bootstrap` (PR #9 by @victortrac)
  - Install path saved to `~/.claude/.bootstrap-dir` for runtime resolution
  - Removes fragile symlink approach
- **Workspace skill frontmatter fix** - Added missing YAML frontmatter to workspace skill (PR #9 by @victortrac)

### Changed
- Total skills increased from 54 to **55 skills**

### Contributors
- @victortrac - Flexible install path, workspace skill fix (PR #9)
- @shawnyeager - Pre-push hook bug report (#8)

---

## [2.5.0] - 2026-02-07

### Added

#### Agent Teams (Default Workflow)
- **Agent Teams skill** - Coordinated team of AI agents as the default development workflow
  - Strict TDD pipeline: Specs > Tests > Fail > Implement > Test > Review > Security > Branch > PR
  - Task dependency chains enforce pipeline ordering (no step can be skipped)
  - Multiple features run in parallel with shared verification agents
  - Quality gates at every stage with cross-agent verification

- **Default agent roster** (5 permanent agents):
  - **Team Lead** - Orchestration only (delegate mode), task breakdown, feature agent spawning
  - **Quality Agent** - TDD verification (RED/GREEN phases), spec review, coverage >= 80%
  - **Security Agent** - OWASP scanning, secrets detection, dependency audit
  - **Code Review Agent** - Multi-engine code review (Claude/Codex/Gemini)
  - **Merger Agent** - Feature branches, PR creation via `gh` CLI

- **Feature agents** - One per feature, each follows the strict pipeline end-to-end
  - Writes spec, tests, implementation, validation
  - Hands off to Quality, Review, Security, Merger at each gate

- **Agent definition files** in `skills/agent-teams/agents/`:
  - `team-lead.md`, `quality.md`, `security.md`, `code-review.md`, `merger.md`, `feature.md`
  - Copied to `.claude/agents/` during project initialization

- **`/spawn-team` command** - Spawn the agent team on any project
  - Checks prerequisites (env var, agent definitions, feature specs)
  - Spawns all agents and creates task dependency chains
  - Shows team status summary

- **10-task dependency chain per feature**:
  1. Spec → 2. Spec Review → 3. Tests → 4. RED Verify → 5. Implement →
  6. GREEN Verify → 7. Validate → 8. Code Review → 9. Security Scan → 10. Branch+PR

### Changed
- Total skills increased from 53 to **54 skills**
- `/initialize-project` Phase 6 now sets up agent team by default (replaces manual next steps)
- CLAUDE.md template includes agent teams section
- `team-coordination.md` superseded by `agent-teams.md` for automated coordination

---

## [2.4.0] - 2026-01-20

### Added

#### Multi-Repo Workspace Awareness
- **Workspace skill** - Dynamic multi-repo and monorepo awareness for Claude Code
  - Workspace topology discovery (monorepo, multi-repo, hybrid detection)
  - Dependency graph generation (who calls whom)
  - API contract extraction (OpenAPI, GraphQL, tRPC, TypeScript, Pydantic)
  - Key file identification with token estimates
  - Cross-repo capability index (search before reimplementing)
  - Token budget management (P0-P3 priority allocation)

- **`/analyze-workspace` command** - Full workspace analysis
  - Phase 1: Topology discovery (~30s)
  - Phase 2: Module analysis (~60s)
  - Phase 3: Contract extraction (~45s)
  - Phase 4: Dependency graph (~30s)
  - Phase 5: Key file identification (~30s)
  - Generates TOPOLOGY.md, CONTRACTS.md, DEPENDENCY_GRAPH.md, KEY_FILES.md, CROSS_REPO_INDEX.md

- **`/sync-contracts` command** - Lightweight incremental contract sync
  - Checks only contract source files (~15s)
  - Diff mode to preview changes
  - Validate mode to check consistency
  - Lightweight mode for hooks

#### Contract Freshness System
- **Session start hook** - Staleness check (~5s, advisory)
- **Post-commit hook** - Auto-sync when contracts change (~15s)
- **Pre-push hook** - Validation gate (~10s, blocking)
- `.contract-sources` file to track monitored files
- Freshness indicators: 🟢 Fresh, 🟡 Stale, 🔴 Outdated, ⚠️ Drift

#### Cross-Repo Change Detection
- Automatic detection when changes affect other modules
- Impact analysis with recommended action order
- Breaking change protocol

### Changed
- Total skills increased from 52 to **53 skills**
- Added 3 new commands: `/analyze-workspace`, `/sync-contracts`, `/workspace-status`
- Added 3 workspace hooks for contract freshness

---

## [2.3.0] - 2026-01-17

### Added

#### Google Gemini Code Review
- **Gemini Review skill** - Google Gemini CLI for code review with Gemini 2.5 Pro
  - 1M token context window - analyze entire repositories at once
  - Free tier: 1,000 requests/day with Google account
  - Code Review Extension: `/code-review` command in Gemini CLI
  - Headless mode for CI/CD: `gemini -p "prompt"`
  - Benchmarks: 63.8% SWE-Bench, 56.3% Qodo PR, 70.4% LiveCodeBench

- **Multi-engine code review** - `/code-review` now supports up to 3 engines
  - Claude (built-in) - quick, context-aware reviews
  - OpenAI Codex - 88% security issue detection
  - Google Gemini - 1M token context for large codebases
  - Dual engine mode - run any two engines, compare findings
  - Triple engine mode - maximum coverage for critical/security code

- **GitHub Actions workflows** for all configurations
  - Gemini-only workflow
  - Triple engine (Claude + Codex + Gemini) workflow
  - Updated dual engine workflow

### Changed
- Total skills increased from 51 to **52 skills**
- Updated `/code-review` to support engine selection: `--engine claude,codex,gemini`
- Added `--gemini` and `--all` shortcuts for common configurations

---

## [2.2.0] - 2026-01-17

### Added

#### Existing Repository Support
- **Existing Repo skill** - Analyze existing codebases, maintain structure, setup guardrails
  - Repo structure detection (monorepo, full-stack, frontend-only, backend-only)
  - Tech stack auto-detection (TypeScript, Python, Flutter, Android, etc.)
  - Convention detection (naming, imports, exports, test patterns)
  - Guardrails audit (pre-commit hooks, linting, formatting, type checking)
  - Structure preservation rules - work within existing patterns, don't reorganize
  - Gradual implementation strategy for adding guardrails to legacy projects
  - Cross-repo coordination for separate frontend/backend repos

- **`/analyze-repo` command** - Quick analysis of any existing repository
  - Directory structure mapping
  - Guardrails status audit (Husky, pre-commit, ESLint, Ruff, commitlint, etc.)
  - Convention detection and documentation
  - Generates analysis report with recommendations
  - Offers to add missing guardrails
  - **Auto-triggered** by `/initialize-project` when existing codebase detected

#### Initialize Project Enhancement
- **Auto-analysis for existing codebases** - `/initialize-project` now automatically analyzes existing repos before making changes
- **User choice after analysis** - Options: skills only, skills + guardrails, full setup, or just view analysis
- **Existing-repo skill auto-copied** - When working with existing codebases

#### Guardrails Setup (for JS/TS and Python)
- **Husky + lint-staged** setup for JavaScript/TypeScript projects
- **pre-commit framework** setup for Python projects
- **commitlint** configuration for conventional commits
- **ESLint 9 flat config** template
- **Ruff + mypy** configuration for Python

### Changed
- Total skills increased from 50 to **51 skills**
- Updated README with `/analyze-repo` usage pattern

---

## [2.1.0] - 2026-01-17

### Added

#### Mobile Development (contributed by @tyr4n7)
- **Android Java skill** - MVVM architecture, ViewBinding, Espresso testing, GitHub Actions CI
- **Android Kotlin skill** - Coroutines, Jetpack Compose, Hilt DI, MockK/Turbine testing
- **Flutter skill** - Riverpod state management, Freezed models, go_router, mocktail testing
- **Android/Flutter auto-detection** - `/initialize-project` now detects Flutter, Android Java, and Android Kotlin projects

#### Database Skills (addresses #7)
- **Firebase skill** - Firestore, Auth, Storage, real-time listeners, security rules, offline persistence
- **Cloudflare D1 skill** - Serverless SQLite with Workers, Drizzle ORM integration, migrations
- **AWS DynamoDB skill** - Single-table design, GSI patterns, SDK v3 TypeScript/Python
- **AWS Aurora skill** - Serverless v2, RDS Proxy, Data API, connection pooling for Lambda
- **Azure Cosmos DB skill** - Partition key design, consistency levels, change feed, SDK patterns

#### Code Review Enhancements
- **Codex Review skill** - OpenAI Codex CLI for code review with GPT-5.2-Codex (88% detection rate)
- **Code review engine choice** - `/code-review` now lets you choose: Claude, OpenAI Codex, or both engines
- **Dual engine review mode** - Run both Claude and Codex, compare findings, catch more issues
- **CI/CD templates** - GitHub Actions workflows for Claude, Codex, and dual-engine reviews

### Changed
- Total skills increased from 44 to **50 skills**
- Updated README with new database and mobile skill listings

### Contributors
- @tyr4n7 - Android Java, Android Kotlin, Flutter skills and auto-detection
- @johnsfuller - Feature request for database skills (#7)

---

## [2.0.0] - 2026-01-08

### Breaking Changes
- **Skills structure changed** - Skills now use folder/SKILL.md structure instead of flat .md files
  - Before: `~/.claude/skills/base.md`
  - After: `~/.claude/skills/base/SKILL.md`
- All skills now require YAML frontmatter with `name` and `description` fields

### Added
- **Validation test** (`tests/validate-structure.sh`) - Validates skills structure, commands, hooks
  - `--full` mode: All 142 checks
  - `--quick` mode: Essential checks for initialize-project
- **Phase 0 validation** in `/initialize-project` - Checks bootstrap installation before setup
- **Conversion script** (`scripts/convert-skills-structure.sh`) - Migrates flat skills to folder structure
- Install script now runs validation automatically
- Symlink created at `~/.claude-bootstrap` for easy access to validation tools

### Fixed
- Skills now load properly in Claude Code (fixes #1)
- Install script properly copies skill folders instead of merging contents

### Migration
```bash
cd ~/.claude-bootstrap
git pull
./install.sh
```

---

## [1.5.0] - 2026-01-07

### Added
- **Code Deduplication skill** - Prevent semantic code duplication with capability index
- **Team Coordination skill** - Multi-person projects with shared state and todo claiming
- `/check-contributors` command - Detect solo vs team projects
- `/update-code-index` command - Regenerate CODE_INDEX.md
- Pre-push hook for code review enforcement

### Changed
- Code reviews now mandatory before push (blocks on Critical/High issues)

---

## [1.4.0] - 2026-01-06

### Added
- **Code Review skill** - Mandatory code reviews via `/code-review`
- **Commit Hygiene skill** - Atomic commits, PR size limits
- Pre-push hooks installation script

---

## [1.3.0] - 2026-01-05

### Added
- **MS Teams Apps skill** - Teams bots and AI agents with Claude/OpenAI
- **Reddit Ads skill** - Agentic ad optimization service
- **PWA Development skill** - Service workers, caching, offline support

---

## [1.2.0] - 2026-01-04

### Added
- **Playwright Testing skill** - E2E testing with Page Objects
- **PostHog Analytics skill** - Event tracking, feature flags
- **Shopify Apps skill** - Remix, Admin API, checkout extensions

---

## [1.1.0] - 2026-01-03

### Added
- Session management with automatic state tracking
- Decision logging for architectural choices
- Code landmarks for quick navigation

---

## [1.0.0] - 2026-01-01

### Added
- Initial release with 30+ skills
- `/initialize-project` command
- TDD-first workflow with Ralph Wiggum loops
- Security-first patterns
- Support for Python, TypeScript, React, React Native
- Supabase integration skills
- AI/LLM patterns for Claude and OpenAI
