# Maggy runner (`maggy run`)

The runner claims AWG work items that need the `maggy-runner` and `stage:build` capabilities.
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
  (trust 1) cannot satisfy it, so an agent cannot mark its own work as tested.

## Intake

```
maggy run intake --repo OWNER/REPO [--label factory] [--project KEY] [--checkout PATH]
```

This wraps `awg sync github OWNER/REPO --label L --capability maggy-runner --capability
stage:build --json`.

- **Label:** intake is opt-in by label. The label comes from `--label` or `intake.label`.
  Without either, intake refuses to run.
- **Capabilities:** taken from `intake.capabilities`, defaulting to the runner's own.
- **Credentials:** `awg sync` needs the AWG admin scope, so it runs with your own AWG
  credential, never with the runner's tokens. GitHub is read with your own `gh` login.

## Running

```
maggy run --once --repo PATH   # at most one item, then exit
maggy run --repo PATH          # loop until STOP; sleeps when idle or paused
```

Each item goes through these steps:

1. Claim, then show the item. Only the `build` stage runs; other stages are given back.
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

## Kill switch

- `maggy run stop` creates `~/.maggy/STOP` and SIGKILLs every registered worker process group.
  While STOP exists, nothing is claimed, reconciled, pushed or submitted. Delete the file to
  resume.
- `maggy run pause --project KEY` and `maggy run resume --project KEY` stop and restart intake
  for one project.

## Crash recovery

`~/.maggy/runner/state.json` records each held lease: the claim, plus the WorkerResult once the
checks have run. Writes are atomic.

On startup (and before every claim), the runner reconciles each held item:

1. **Settle dangling push/PR intents.** It looks each one up by its stable name (the remote
   `maggy/<ref>`, the open PR whose head is that branch) and records a `reconciled` result.
2. **Roll forward** when the lease is still live and the worker had finished. It re-runs the
   conclusion: evidence already attached is skipped, the push is skipped when the remote
   already holds the SHA, the PR is edited rather than created again, and then it submits.
3. **Otherwise, roll back.** It releases the item with a handoff that names the last SHA and
   the next step. The worktree and branch are kept, so the next attempt resumes from the
   branch.

The Phase 3 exit test (`tests/test_runner_phase3_exit.py`) runs against the real awg CLI. It
kills the runner with SIGKILL after the push but before the PR, then restarts it, and checks
that this converges to exactly one draft PR and one submit.
