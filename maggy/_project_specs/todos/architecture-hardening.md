# Architecture Hardening — Council of Experts Review

Source: council review of Maggy architecture (2026-06-10).
Panel: **Claude Fable 5 (chief)**, DeepSeek Pro, Gemini 2.5 Pro, Grok.

## Verdict tally

| # | Todo | Chief | DeepSeek | Gemini | Grok | Decision |
|---|------|-------|----------|--------|------|----------|
| T1 | Gate the self-tuning router | rec | NOW | NOW | NOW | **IMPLEMENT** |
| T2 | Unify isolation on containers | rec (top) | NOW | NOW | NOW | **IMPLEMENT (priority #1)** |
| T3 | Extract a frozen kernel | rec | LATER | LATER | LATER | **DEFER** |
| T4 | Reconcile memory + coordination | risk | NOW | LATER | NOW | **IMPLEMENT** |

Unanimous #1 priority (all 3 members): **T2**.

---

## T2 — Unify isolation on containers  [priority #1]
**Why:** the least-supervised path (autonomous pipeline) has the weakest containment
(path-validated sandbox); the Pi adapter builds subprocess calls by parsing untrusted,
unstable CLI `--help` text.
**Do:**
- Run the autonomous pipeline in Docker (reuse Polyphony's per-agent containers).
- Delete the path-validation sandbox once containers cover its cases.
- Replace `--help` auto-discovery with pinned per-CLI adapter manifests + golden tests
  that fail loudly on vendor drift.
**Watch (Grok):** container startup latency can starve tight feedback loops — pool/warm
containers or reuse per session.
**Done when:** pipeline tool execution runs only inside a container; no path-sandbox code
on the autonomous path; adapter manifests pinned + golden-tested; latency benchmarked.

## T1 — Gate the self-tuning router
**Why:** routing rules rewrite themselves from outcomes with no sample threshold or
approval — a feedback loop that optimizes against the same signal used to judge quality
(reward-hacking the benchmark).
**Do:**
- Rule changes run in SHADOW mode (logged, not applied) until a min-N outcome threshold.
- Promote via the existing inbox approval flow; every change a diffed, revertible audit
  artifact.
**Watch (DeepSeek):** min-N alone is insufficient if the success metric is gameable — add
outcome-validity rules (reject poisoned/degenerate outcomes before they count).
**Done when:** no rule auto-applies without shadow + min-N + approval; all changes diffed
in the audit log and revertible; outcome-validity filter in place.

## T4 — Reconcile memory + coordination
**Why:** cikg / mnemos / history are three separate "what the system knows" models with no
precedence; SQLite is also the multi-agent task state machine (single-writer under
concurrent Polyphony agents → lock contention / silent corruption).
**Do:**
- Define explicit precedence between the memory systems (which wins on conflict, who the
  executor gate trusts).
- Move multi-agent task state off single-writer SQLite (or enforce WAL + proper locking +
  a reconciliation policy).
**Done when:** documented precedence + a conflict-resolution path; concurrent-agent state
has no single-writer contention under a load test.

## T3 — Extract a frozen kernel  [DEFERRED]
Carve router + executor gate + audit log + event spine into a contract-tested kernel;
demote council/plugins/cikg/mnemos/Polyphony to consumers. Council: hygiene, not a live
risk — do **after** T1/T2/T4 stabilize the seams.

## Cross-cutting (Gemini)
Add correlated tracing/observability across the 331 modules — without it, debugging the
new "safer" components will be near-impossible. Fold into each todo's done-criteria.
