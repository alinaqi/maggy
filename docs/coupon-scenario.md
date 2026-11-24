# Coupon scenario: Phase 5 exit run

The factory doc's coupon ticket ("Fix what happens when a coupon expires", sections 1, 2
and 5) run end to end by `maggy/tests/test_coupon_scenario_exit.py`. Everything below was
recorded from a real run on 2026-11-24 (`MAGGY_COUPON_RECORD=<dir> pytest
tests/test_coupon_scenario_exit.py`), not written by hand.

## What runs

| Part | In this run |
|---|---|
| AWG | the REAL `awg` CLI, temp `HOME` / `AWG_HOME`, runner `agent` + `ci` tokens minted by `ensure_awg` |
| Git | the rig repo with the buggy checkout on `main`, a local bare `origin` |
| GitHub | a fake `gh`: one issue for `awg sync github`, draft PRs recorded to a file |
| Agents | fake CLIs replaying structured output: spec author, spec reviewer, planner; the build agent applies the real fix diff and writes the planned browser tests |
| Browsers | real Chromium (Python Playwright, the cached `ms-playwright` browsers) for the regression tests, the AC1/AC2 functional checks and the AC3 captures |
| Vision | a fake backend returning `pass`; Ollama is not installed here, and without a backend AC3 stays PENDING (never PASS) |
| Review council | a fake council with no findings, fed the approved criteria, test plan and diff |

The fixture app is `maggy/tests/fixtures/coupon_app`: `repo/` is a static `checkout.html`,
`api.js` (the tiny JS coupon API: seeded $100 cart, `SAVE10` 10% off, `EXPIRED` expired in
UTC against a fixed clock) and `app.js` with the doc's bug (an expired code clears the field
and shows no field error). `agent/fix.diff` is the fix; `agent/*.py.txt` are the browser
tests the build agent writes. `maggy/tests/test_coupon_fixture.py` proves every planned test
fails by an assertion on the buggy page and passes with the fix.

## The run, step by step

1. **Intake.** `maggy run intake` turns the labelled issue into `AWG-1` at `stage:spec`.
2. **Spec asks ONE question.** The reviewer returns `needs_clarification` with: "Should an
   expired code stay visible in the field so the shopper can correct it, with expiry judged in
   UTC rather than the shop's local time zone?" The item goes to `WAITING_HUMAN` with exactly
   that comment.
3. **Human answers** (comment + `READY`): keep the code visible and editable; expiry stays UTC.
4. **Spec approved.** The author's next draft (its prompt carries the answer) has AC1-AC3 from
   the doc; the reviewer says `ready`; the WORK criteria, REQUIREMENT nodes and the
   `spec-approved` DECISION are written and the item moves to `stage:plan`.
5. **Plan.** T1-T3 with DEPENDS_ON T1 <- T2 <- T3 and the doc's test plan: AC1 and AC2 as
   `e2e` browser tests, AC3 as `visual` with the route, actions, 390x844 / 1440x900 viewports
   and layout assertions. Each entry is a VALIDATION (`[ACn] <test>: <expected>`, CI trust)
   on its task.
6. **Build.** Each child runs through `maggy run --once`; its regression test is proven RED on
   `main` (base + only the candidate's test files) and GREEN on the candidate, in fresh
   worktrees with the check env, before the ci token attaches PASS to the `[ACn]` validation
   and the child's draft PR opens. Just before the last child is submitted, the runner
   re-tags `AWG-1` from `stage:planned` to `stage:verify`.
7. **Verify, first pass.** The children are merged into `maggy/AWG-1`; AC1/AC2 browser tests
   pass on the integrated SHA; AC3 renders at both viewports, passes the layout assertions,
   and has no baseline: PENDING with two proposed images, so `AWG-1` goes to `WAITING_HUMAN`
   naming each image and its approval command. The vision reviewer is not asked yet.
8. **Human approves the baselines**: one `baseline-approved:AC3:<viewport>` DECISION per image,
   carrying its sha256, then `READY`.
9. **Verify, second pass.** The runner commits the approved baselines to `.maggy/baselines/`
   on `maggy/AWG-1` (a new candidate SHA), re-runs every check there: AC3 matches the
   baseline at both widths and the vision reviewer passes each capture. The gate opens, the
   draft PR body gets the evidence table and the item is submitted.

## PR body (draft PR for `maggy/AWG-1`)

```markdown
## Summary

Candidate for AWG-1 produced by the Maggy runner.

- AWG ref: `AWG-1`
- Candidate SHA: `52d59b6aafc9ec0ef04740dc8f1f8796c8e04931`
- Attempt: `af685232-e733-44fe-a3b7-6bd083e20f53`

## Checks

| Check | Result | SHA |
|---|---|---|
| lint | PASS | `52d59b6aafc9ec0ef04740dc8f1f8796c8e04931` |

## Evidence

- Ticket: `AWG-1`
- Spec version: `16`
- Tested commit: `52d59b6aafc9ec0ef04740dc8f1f8796c8e04931`
- Gate: open (every required criterion passed; no blocking review findings)

| Criterion | Verdict | Check(s) | Evidence | Detail | Artifacts |
|---|---|---|---|---|---|
| AC1 | passed | functional | e2e | test_ac1_expired_coupon_keeps_code passed | - |
| AC2 | passed | functional | e2e | test_ac2_valid_code_after_expired passed | - |
| AC3 | passed | visual mobile, visual desktop, vision mobile, vision desktop | visual | matches the approved baseline; fake-vision: pass (coupon error): AC3 at mobile; fake-vision: pass (coupon error): AC3 at desktop | mobile expected `attempts/af685232-e733-44fe-a3b7-6bd083e20f53/verify/visual/AC3/mobile-expected.png` (sha256:727bf10d408d)<br>mobile actual `attempts/af685232-e733-44fe-a3b7-6bd083e20f53/verify/visual/AC3/mobile-actual.png` (sha256:727bf10d408d)<br>desktop expected `attempts/af685232-e733-44fe-a3b7-6bd083e20f53/verify/visual/AC3/desktop-expected.png` (sha256:4cc168c204c5)<br>desktop actual `attempts/af685232-e733-44fe-a3b7-6bd083e20f53/verify/visual/AC3/desktop-actual.png` (sha256:4cc168c204c5) |
| Release impact | - | - | - | No high-risk paths in the plan. Plan tasks: T1, T2, T3. Draft PR only; nothing merges or deploys automatically. | - |

### Review council

No blocking findings.

### Verification gaps

- [AC1] functional log withheld from the PR: secret scan (high-entropy token)
- [AC2] functional log withheld from the PR: secret scan (high-entropy token)

Draft opened by the Maggy runner; it never merges or marks a PR ready.
```

The two gaps in this recorded run were a false positive, since fixed: the pytest logs of
the AC1/AC2 functional runs print the checkout's absolute temp path, and the secret scan's
high-entropy rule then treated the whole path as one token. The scan no longer joins path
segments (`/` is not part of a token), so a re-run references those logs from the AC1/AC2
rows instead (`test_the_same_log_without_a_token_is_referable`). The verdicts are unaffected.

## `awg proof AWG-1 --json` (runner-agent credential)

The final candidate `52d59b6a...` carries the CI-trust (3) PASS from `maggy-runner-ci`; the
first-pass candidate `ac79498a...` (before the baselines were committed) is still listed but
`fresh: false`, so it no longer counts.

```json
{
  "work": {
    "display_id": "AWG-1",
    "category": "TASK",
    "state": "DONE",
    "priority": 2,
    "risk": "medium",
    "acceptance_criteria": [
      "[AC1] Applying an expired coupon shows \"This coupon has expired\" next to the field and keeps the entered code available for editing. The cart total stays at $100.",
      "[AC2] Applying a valid 10% coupon to the same $100 fixture updates the total to $90. Applying a valid code after an expired one clears the error.",
      "[AC3] At 390 px and 1440 px, the message sits under the coupon field and leaves the Apply button and order total visible and usable."
    ],
    "origin": {
      "system": "github",
      "number": 12,
      "url": "https://example.invalid/acme/shop/issues/12",
      "external_id": "I_12",
      "key": "acme/shop#12",
      "repo": "acme/shop",
      "imported_closed": false,
      "policy_exempt": false
    },
    "repository_refs": [
      "github:acme/shop"
    ],
    "execution_policy": {
      "capabilities": [
        "maggy-runner",
        "project:repo",
        "stage:verify"
      ]
    },
    "revision_sha": "52d59b6aafc9ec0ef04740dc8f1f8796c8e04931",
    "verification_state": "PASS",
    "unmet_dependency_count": 0,
    "dependent_count": 0,
    "state_reason": "verification PASS",
    "claimed_by": null,
    "attempt_id": null,
    "human_email": null,
    "paused": false,
    "lease_expires_at": null,
    "heartbeat_at": null,
    "fencing_token": 5,
    "version": 18,
    "created_at": 1795486222.2931762,
    "updated_at": 1795486419.386133,
    "id": "2a3d6673-a8ff-4034-9a1e-04aff8a90f91",
    "workspace_id": "f48e5efb-bdfb-49d3-a0e7-8694fd527d0b",
    "title": "Fix what happens when a coupon expires",
    "description": "Fix what happens when a coupon expires.",
    "properties": {},
    "project_id": "858a47b2-e25c-4078-9bf6-8883f53ba831",
    "node_type": "WORK",
    "human": null,
    "labels": [
      "factory"
    ],
    "attributes": {
      "author": [
        "me"
      ],
      "github_number": [
        "12"
      ],
      "github_state": [
        "open"
      ],
      "keyword": [
        "coupon",
        "expired",
        "expiry",
        "utc",
        "visible"
      ]
    }
  },
  "verdict": "PASS",
  "validations": [
    {
      "id": "f59555d3-c476-4fc4-b89e-cc99dcdae5a7",
      "kind": "test",
      "title": "CI tests pass",
      "required": true,
      "min_trust": 3,
      "freshness": "revision",
      "status": "PASS",
      "evidence": [
        {
          "verdict": "PASS",
          "producer": "maggy-runner-ci",
          "trust_class": 3,
          "commit_sha": "52d59b6aafc9ec0ef04740dc8f1f8796c8e04931",
          "artifact_ref": null,
          "environment": null,
          "at": 1795486400.8346229,
          "fresh": true
        },
        {
          "verdict": "PASS",
          "producer": "maggy-runner-ci",
          "trust_class": 3,
          "commit_sha": "ac79498af625292ff28dadc78f8edf6df0e5acad",
          "artifact_ref": null,
          "environment": null,
          "at": 1795486365.117066,
          "fresh": false
        }
      ]
    }
  ],
  "attempts": [
    {
      "actor": "maggy-runner-agent",
      "model": "cli",
      "state": "PAUSED",
      "summary": null,
      "artifact_refs": [],
      "started_at": 1795486223.6099908,
      "ended_at": 1795486227.770593
    },
    {
      "actor": "maggy-runner-agent",
      "model": "cli",
      "state": "PAUSED",
      "summary": null,
      "artifact_refs": [],
      "started_at": 1795486229.952296,
      "ended_at": 1795486238.691941
    },
    {
      "actor": "maggy-runner-agent",
      "model": "cli",
      "state": "PAUSED",
      "summary": null,
      "artifact_refs": [],
      "started_at": 1795486240.072285,
      "ended_at": 1795486261.189116
    },
    {
      "actor": "maggy-runner-agent",
      "model": "cli",
      "state": "PAUSED",
      "summary": null,
      "artifact_refs": [],
      "started_at": 1795486347.245655,
      "ended_at": 1795486378.133653
    },
    {
      "actor": "maggy-runner-agent",
      "model": "cli",
      "state": "COMPLETED",
      "summary": "maggy: verified 52d59b6aafc9: {'AC1': 'PASS', 'AC2': 'PASS', 'AC3': 'PASS'}",
      "artifact_refs": [],
      "started_at": 1795486380.9888158,
      "ended_at": 1795486419.38499
    }
  ],
  "commits": [
    "52d59b6aafc9ec0ef04740dc8f1f8796c8e04931",
    "ac79498af625292ff28dadc78f8edf6df0e5acad"
  ],
  "done_at": 1795486419.386318
}
```

## Proof of every item (validations and evidence only)

Parent and build children; every validation has CI-trust PASS evidence bound to that item's
final revision.

```json
{
  "AWG-1": {
    "title": "Fix what happens when a coupon expires",
    "state": "DONE",
    "verdict": "PASS",
    "revision_sha": "52d59b6aafc9ec0ef04740dc8f1f8796c8e04931",
    "validations": [
      {
        "title": "CI tests pass",
        "kind": "test",
        "min_trust": 3,
        "status": "PASS",
        "evidence": [
          {
            "producer": "maggy-runner-ci",
            "trust_class": 3,
            "verdict": "PASS",
            "commit_sha": "52d59b6aafc9ec0ef04740dc8f1f8796c8e04931",
            "fresh": true
          },
          {
            "producer": "maggy-runner-ci",
            "trust_class": 3,
            "verdict": "PASS",
            "commit_sha": "ac79498af625292ff28dadc78f8edf6df0e5acad",
            "fresh": false
          }
        ]
      }
    ]
  },
  "AWG-2": {
    "title": "Reproduce the expired coupon and fix the field error",
    "state": "DONE",
    "verdict": "PASS",
    "revision_sha": "e06966764d7acf69686a78900adde921a2e29b99",
    "validations": [
      {
        "title": "CI tests pass",
        "kind": "test",
        "min_trust": 3,
        "status": "PASS",
        "evidence": [
          {
            "producer": "maggy-runner-ci",
            "trust_class": 3,
            "verdict": "PASS",
            "commit_sha": "e06966764d7acf69686a78900adde921a2e29b99",
            "fresh": true
          }
        ]
      },
      {
        "title": "[AC1] test_ac1_expired_coupon_keeps_code: exact error shown, input keeps EXPIRED, total $100",
        "kind": "test",
        "min_trust": 3,
        "status": "PASS",
        "evidence": [
          {
            "producer": "maggy-runner-ci",
            "trust_class": 3,
            "verdict": "PASS",
            "commit_sha": "e06966764d7acf69686a78900adde921a2e29b99",
            "fresh": true
          }
        ]
      }
    ]
  },
  "AWG-3": {
    "title": "Fix the recovery after an expired coupon",
    "state": "DONE",
    "verdict": "PASS",
    "revision_sha": "1c061a75b581147a07115a0ed8e33a5f1a8cf720",
    "validations": [
      {
        "title": "CI tests pass",
        "kind": "test",
        "min_trust": 3,
        "status": "PASS",
        "evidence": [
          {
            "producer": "maggy-runner-ci",
            "trust_class": 3,
            "verdict": "PASS",
            "commit_sha": "1c061a75b581147a07115a0ed8e33a5f1a8cf720",
            "fresh": true
          }
        ]
      },
      {
        "title": "[AC2] test_ac2_valid_code_after_expired: the error disappears and the total becomes $90",
        "kind": "test",
        "min_trust": 3,
        "status": "PASS",
        "evidence": [
          {
            "producer": "maggy-runner-ci",
            "trust_class": 3,
            "verdict": "PASS",
            "commit_sha": "1c061a75b581147a07115a0ed8e33a5f1a8cf720",
            "fresh": true
          }
        ]
      }
    ]
  },
  "AWG-4": {
    "title": "Verify the integrated checkout layout",
    "state": "DONE",
    "verdict": "PASS",
    "revision_sha": "985f72290657de9717e764c49bf1ee2465794d72",
    "validations": [
      {
        "title": "CI tests pass",
        "kind": "test",
        "min_trust": 3,
        "status": "PASS",
        "evidence": [
          {
            "producer": "maggy-runner-ci",
            "trust_class": 3,
            "verdict": "PASS",
            "commit_sha": "985f72290657de9717e764c49bf1ee2465794d72",
            "fresh": true
          }
        ]
      },
      {
        "title": "[AC3] test_ac3_expired_layout: message under the field; Apply and total in view",
        "kind": "test",
        "min_trust": 3,
        "status": "PASS",
        "evidence": [
          {
            "producer": "maggy-runner-ci",
            "trust_class": 3,
            "verdict": "PASS",
            "commit_sha": "985f72290657de9717e764c49bf1ee2465794d72",
            "fresh": true
          }
        ]
      }
    ]
  }
}
```

## Notes and known limits

- Build children are created from the default branch, not stacked on their dependencies, so
  each child that owns a regression test also carries the fix that test proves; the verify
  stage merges them (identical hunks merge cleanly). Stacked child branches are future work.
- The parent's only validation in AWG is the default `CI tests pass`; the per-criterion
  results of verify (functional, visual, vision) are attached as commit-bound ci evidence with
  `meta` (spec_version, criterion_id, check, viewport) and summarised in the PR table.
- No network: issue and PRs go through the fake `gh`, pushes go to the local bare remote.
