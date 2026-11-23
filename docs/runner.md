# Maggy runner (`maggy run`)

The runner claims AWG work items that need the `maggy-runner` capability and one of
`stage:spec`, `stage:plan` or `stage:build` (see Stages).
Claiming is opt-in: it passes `--require-capabilities=maggy-runner`, so an item that declares
no capabilities (a hand-made task, an unlabelled import) is never claimed.
It runs a worker in the item's own worktree, runs the required checks itself, and attaches
evidence tied to the candidate commit. It then pushes `maggy/<ref>`, opens or updates a
**draft** PR, and submits the item. AWG's completion contract decides whether the item ends
up DONE or VERIFYING. The design is in RFC personal-harness §2.4 and §2.6.

## Setup

1. Install AWG. The runner needs a build that has `next --capabilities`, the
   `--attempt`/`--fencing-token` fence flags, `evidence --commit-sha/--meta/--validation`,
   `annotate --key`, `annotations` and `sync github --label --capability`.
2. Run `maggy harness init`. If AWG is not initialised yet, this runs `awg init`. It then mints
   one agent token per agent CLI, plus the runner's two credentials (see Tokens).
3. Configure the worker in `~/.maggy/harness.yaml` (personal) or `<repo>/.maggy/harness.yaml`:
   - `worker.adapter`
   - `commands.*`
   - `validation.required`
   - optionally `intake.label` and `intake.capabilities`
4. Run `maggy harness doctor`. It checks that both runner tokens exist, are mode 0600, and can
   reach AWG.

## Tokens

| File | AWG kind | Used for |
|---|---|---|
| `~/.maggy/tokens/runner-agent.token` | `agent` (trust 1) | claim, heartbeat, submit, release, block, comments, annotations |
| `~/.maggy/tokens/runner-ci.token` | `ci` (trust 3) | `awg evidence` only |

- Both files are mode 0600. The secrets go from `awg token mint --json` straight into these
  files and are never printed or passed in argv: the runner passes `--token-file`.
- The child environment drops `AWG_TOKEN`.
- Worker (agent) sessions get no AWG credential at all.
- The default `test` validation requires CI trust (3). Evidence written with an agent token
  (trust 1) cannot satisfy it, so an agent cannot mark its own work as tested **through
  AWG's credential split**.
- **Limit: CI trust is not enforceable under host execution.** The ci token is a 0600 file
  owned by the same user that runs the worker and the required checks, and container
  isolation is not implemented yet, so the runner can only run with
  `worker.allow_host_execution: true`. Code the agent writes (for example a test the checks
  execute) can read `~/.maggy/tokens/runner-ci.token` and attach trust-3 evidence itself.
  Mode 0600 does not protect against the same uid. Until the ci credential lives outside the
  worker's reach (a separate uid or keychain, or a sandbox that denies reading
  `~/.maggy/tokens`), treat CI evidence from the runner as produced on a trusted host by
  untrusted code, and review the PR. `maggy harness doctor` and `maggy run` warn about this.

## Intake

```
maggy run intake --repo OWNER/REPO [--label factory] [--project KEY] [--checkout PATH]
                 [--state-dir DIR]
```

This wraps `awg sync github OWNER/REPO --label L --capability maggy-runner --capability
stage:spec --capability project:KEY --json`, so every imported ticket starts at the spec
stage.

- **Label:** intake is opt-in by label. The label comes from `--label` or `intake.label`.
  Without either, intake refuses to run.
- **Capabilities:** taken from `intake.capabilities`, defaulting to `maggy-runner,
  stage:spec`. Set `[maggy-runner, stage:build]` to skip spec and plan for tickets that
  are already precise.
- **Project binding:** every imported item also gets `project:KEY`. KEY is `--project`,
  else the checkout's repo name, the same default `maggy run` uses. A runner only claims
  items that declare `maggy-runner` and its own `project:KEY`, so a runner bound to repo A
  never claims, builds, pushes or opens a PR for project B's items. (`awg next` has no
  project filter yet, so the binding is carried as a required capability.)
- **Pause:** intake refuses to run while KEY is paused.
- **Credentials:** `awg sync` needs the AWG admin scope, so it runs with your own AWG
  credential, never with the runner's tokens. GitHub is read with your own `gh` login.

## Running

```
maggy run --once --repo PATH   # at most one item, then exit
maggy run --repo PATH          # loop until STOP; sleeps when idle or paused
```

Each item goes through these steps:

1. Claim, then show the item. A `stage:spec` or `stage:plan` item goes to that stage (see
   Stages); the steps below are the build stage.
2. Open the worktree on `maggy/<ref>`. A branch from an earlier attempt is resumed, not reset.
3. Run the worker under a heartbeat. If the heartbeat fails, the worker's process group is
   killed.
4. Check that the spec version is unchanged. If it changed, the item is sent back for spec
   review.
5. Attach evidence with the ci token:
   - one record per check, bound to the candidate SHA and to the item's `test` validation;
   - with `spec_version` and the check name in its metadata;
   - written once, guarded by keyed intent/result annotations.
6. Push `maggy/<ref>` with a lease, then create or edit the draft PR, found by its head
   branch.
7. Submit at the candidate SHA.

Two rules apply throughout:

- **Fencing:** before every side effect, the runner checks that STOP is absent and that its
  fencing token is still the live one.
- **Branch rule:** the runner pushes only `maggy/*` branches. It never merges and never marks
  a PR ready.

## Stages

`maggy run` claims with `--capabilities=maggy-runner,stage:spec,stage:plan,stage:build,
project:KEY`. `worker.stages` in the profile (default `[spec, plan, build]`) restricts which
stages a runner holds, so one machine can, for example, only build. Each claimed item is
driven by its `stage:<name>` capability:

```
intake -> stage:spec --(question)--> WAITING_HUMAN --(human answers, READY)--> stage:spec
       -> spec approved -> stage:plan --(high-risk paths)--> WAITING_HUMAN (plan-approved)
       -> children READY with stage:build, parent parked as stage:planned -> build -> draft PR
```

- **Spec** (`stage:spec`). A read-only author (`agents.default`) returns one fenced json
  block of acceptance criteria; a reviewer in a fresh session (`agents.prefer.review`)
  returns `ready`, `needs_clarification` or `blocked`. Malformed output gets one retry
  with the validation error, then the attempt fails without touching the graph.
  - `needs_clarification`: exactly ONE question, posted as the item's comment, and the
    item goes WAITING_HUMAN. Answer with `awg comment REF "..."`, then
    `awg state REF READY`; the next author run sees the comments.
  - `ready`: the WORK criteria become `[AC1] ...` lines (bumping the WORK version), one
    REQUIREMENT node per criterion, and a `spec-approved` DECISION recording the spec
    version and the criteria fingerprint. The item is re-tagged `stage:plan`.
- **Plan** (`stage:plan`). If the criteria changed since approval, the item goes back to
  `stage:spec`. A read-only planner returns tasks (files, `depends_on`) and a per-criterion
  test plan, checked as an acyclic DAG covering every criterion. Children are created in
  BACKLOG with `stage:build`, linked DEPENDS_ON, and given one VALIDATION per test-plan
  entry (linked to the criterion's REQUIREMENT node) before any of them is READY. Plans that
  touch `risk.high` or the spec's risk paths wait for a human `plan-approved` DECISION.
- **Build** (`stage:build`): the steps under Running, per child, in dependency order.

The Phase 4 exit test (`tests/test_runner_phase4_exit.py`) runs this whole flow against the
real awg CLI with recorded agent replies: an ambiguous ticket gets one question, the test
answers it, and the first child ends as a draft PR with CI-trust evidence.

## Kill switch

- `maggy run stop` creates `~/.maggy/STOP` and SIGKILLs every registered worker process group.
  Each entry records the leader's pid and start time; a group is killed only while its leader
  is still that process, so a reused pid is never signalled.
  While STOP exists, nothing is claimed, reconciled, pushed or submitted. Delete the file to
  resume.
- `maggy run pause --project KEY` and `maggy run resume --project KEY` stop and restart intake
  for one project: while KEY is paused, `maggy run intake` refuses to import for KEY and the
  runner bound to KEY claims nothing. Runners bound to other projects keep working, and they
  never claim KEY's items anyway (project binding above). Pause flags live in the state dir,
  so pass the same `--state-dir` to `pause` as to `run` and `intake`.

## One runner per state dir, and retries

`maggy run` takes an exclusive lock on `~/.maggy/runner/runner.lock` (the kernel releases it
when the process dies, even on SIGKILL). A second runner on the same state dir reports
`locked` and touches nothing, so it never mistakes a live runner's lease for a crash.

After any pass that made no progress (idle, paused, failed, unsupported, interrupted) the loop
sleeps before the next claim. After three consecutive failed attempts on one item
(`max_failures`), the next claim blocks the item for a human instead of running the agent
again. A human comment or unblock resets the count.

## Crash recovery

`~/.maggy/runner/state.json` records each held lease: the claim, plus the WorkerResult once the
checks have run. Writes are atomic.

On startup (and before every claim), the runner reconciles each held item. It first kills
the dead run's worker process group, which outlives the runner because it has its own
session, and removes its pid entry, so no orphan keeps editing the worktree.

1. **Settle dangling push/PR intents.** It looks each one up by its stable name (the remote
   `maggy/<ref>`, the open same-repository PR whose head is that branch) and records a
   `reconciled` result. A fork PR from a branch with the same name is never adopted.
2. **Roll forward** when the lease is still live and the worker had finished. It re-runs the
   conclusion: evidence already attached is skipped, the push is skipped when the remote
   already holds the SHA, the PR is edited rather than created again, and then it submits.
3. **Otherwise, roll back.** It releases the item with a handoff that names the last SHA and
   the next step. The worktree and branch are kept, so the next attempt resumes from the
   branch.

The Phase 3 exit test (`tests/test_runner_phase3_exit.py`) runs against the real awg CLI. It
kills the runner with SIGKILL after the push but before the PR, then restarts it, and checks
that this converges to exactly one draft PR and one submit.
