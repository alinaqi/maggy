# Worker replay set (Phase 2 exit)

`maggy worker replay` runs five small, self-contained tasks through the full worker
pipeline (RFC personal-harness §2.3/§2.6: launch policy, scrubbed env, budget reservation
and deadline, runner-side commit, required checks in a fresh worktree at the candidate,
protected paths, agent blockers) once per agent, and prints a comparison table plus an
optional JSON report.

```bash
maggy worker replay                                  # offline: fake CLIs, all 5 tasks x 4 agents
maggy worker replay --agents claude,codex --tasks implement,off_by_one \
  --live --model claude=haiku --budget 0.25 --json report.json   # real CLIs, real spend
```

## Tasks (`maggy/maggy/worker/replay/tasks/*.yaml`)

| id | kind | expected outcome |
|---|---|---|
| `implement` | implement `slugify` so a failing test passes | candidate, checks green |
| `off_by_one` | fix an off-by-one in `page()` | candidate, checks green |
| `cli_flag` | add `--shout` to a tiny argparse CLI, with a test | candidate, checks green |
| `refactor` | extract `format_line` from `summary` without behaviour change | candidate, checks green |
| `ambiguous` | "apply the new discount rules" (rules never given) | `blocked` with a question, no edits |

Each task is a fixture repo created from the YAML at runtime in a temp dir and
git-initialised. Two required checks run on the candidate: `test` (the repo's own
`unittest` suite) and `e2e` (hidden acceptance tests written *outside* the repo, so an
agent cannot weaken them). Every prompt ends with the blocker convention: reply with a
`QUESTION:` line instead of guessing. Verdict `pass` means: all checks green on a
candidate, or for `ambiguous`, outcome `blocked` with no candidate commit.

## Modes

- **Offline (default).** A bin dir of fake `claude`/`codex`/`opencode`/`pi` executables is
  put first on the worker's PATH. They are invoked with the shipped adapters' real argv
  (logged to `bin/calls.jsonl`), apply the task's reference solution and print that CLI's
  recorded output (`replay/recordings/`, copies of the contract-test fixtures; opencode and
  pi recordings are synthetic) with the final text set to the task's reply. The fakes are
  maggy's own scripts, so offline runs allow host execution; state stays in the run dir.
- **Live (`--live`).** The real CLIs on PATH, under the personal profile's fail-closed
  launch policy: adapters without a native sandbox (opencode, pi) are refused unless
  `worker.allow_host_execution: true` is set in `~/.maggy/harness.yaml`. Required checks
  run candidate code and there is no check sandbox yet, so since the review fixes every
  live replay (claude and codex too) needs that opt-in; without it the row is refused
  before launch. The per-run budget
  (`--budget`, default 0.25) is reserved in the ledger and passed to Claude as
  `--max-budget-usd`. State (ledger, logs, STOP file) defaults to `~/.maggy`.

## Live run, 2026-11-23

Note: this run predates the check-boundary fix. Its claude and codex rows ran the
required checks on the host without `allow_host_execution`; the runner now refuses that.

Claude Code 2.1.330 (`--model haiku`, `--max-budget-usd 0.2500`) and codex-cli 0.163.0
(default model), permission `workspace`, deadline 300 s, throwaway repos and state dir under
a scratch directory. Four model calls in total.

| task | agent | verdict | outcome | checks | changed | cost | elapsed | model |
|---|---|---|---|---|---|---|---|---|
| implement | claude | pass | succeeded | 2/2 | textutil.py | $0.0008 | 157.6s | claude-haiku-4-5 |
| implement | codex | fail | blocked | 0/0 | - | $0.0000 | 22.0s | unknown |
| implement | opencode | refused | - | 0/0 | - | - | - | - |
| implement | pi | refused | - | 0/0 | - | - | - | - |
| off_by_one | claude | pass | succeeded | 2/2 | pager.py | $0.0128 | 52.7s | claude-haiku-5-5 |
| off_by_one | codex | pass | succeeded | 2/2 | pager.py | $0.0000 | 29.6s | unknown |
| off_by_one | opencode | refused | - | 0/0 | - | - | - | - |
| off_by_one | pi | refused | - | 0/0 | - | - | - | - |

Observations:

- Codex on `implement` read the code and tests, then raised a blocker instead of editing:
  "Should punctuation between letters split words (`"foo.bar"` → `"foo-bar"`) or be
  removed (`"foo.bar"` → `"foobar"`)?". The runner reported it as `blocked` with that
  question, as designed; the verdict is `fail` because the task is meant to be
  unambiguous. This is a real behavioural difference: with the blocker convention in the
  prompt, codex asks earlier than Claude.
- Codex does not report cost in `--json` output (cost $0, model `unknown`); its runs are
  reserved at the adapter's fixed 1.00 USD reservation.
- Claude reported different model ids for the two runs of `--model haiku`
  (`claude-haiku-4-5`, `claude-haiku-5-5`), as parsed from its `modelUsage`.
- opencode and pi: refused before launch by the fail-closed policy (no native sandbox, no
  `allow_host_execution` opt-in in the personal profile). No live calls were made for them
  and their configuration was not changed; they have no configured provider on this
  machine either. Their offline rows use synthetic recordings.

The offline replay (all 5 tasks x 4 agents) passes 20/20 and runs in the test suite
(`maggy/tests/test_worker_replay_run.py`).
