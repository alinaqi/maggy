# Spec 01: Runtime Observability for Drift Detection

**Status:** pending
**Priority:** Tier 1 (highest leverage)
**Effort:** Medium

## Context

`iCPG` detects drift **statically** — it can tell you a symbol's checksum changed, its tests disappeared, or a postcondition's predicate no longer holds against the current codebase. What it cannot tell you is whether the running system still delivers what the intent promised.

An autonomous agent that ships code needs a feedback signal after deploy. Otherwise:

- A refactor passes all tests and drift checks but tanks p99 latency in production → agent has no signal
- A bug fix validates against one invariant but introduces regressions users hit → silent
- An intent's postcondition is "<500ms response" — a static graph can't verify this

## Goal

Bridge `iCPG` to runtime telemetry so drift detection includes post-deploy signals, not just pre-commit signals.

## Approach

### Step 1 — Define a runtime-signal abstraction

Add a new edge type to iCPG:

```
VALIDATED_IN_PROD    Reason → Metric    (intent's postcondition has a runtime check)
```

A `Metric` node references an observability query:

```yaml
metric:
  id: "checkout_p99_under_500ms"
  source: "datadog"       # datadog | sentry | honeycomb | prometheus
  query: "avg:trace.checkout.latency.p99{env:prod}"
  predicate: "value < 500"
  window: "1h"
```

### Step 2 — Pluggable observability adapters

One-file adapters per backend (`scripts/icpg/observability/`):

- `datadog_adapter.py` — query API key from env, return metric value
- `sentry_adapter.py` — query event frequency for a given issue
- `honeycomb_adapter.py` — run a Honeycomb query and extract result
- `prometheus_adapter.py` — PromQL
- `stub_adapter.py` — for testing, reads from a JSON file

Each exposes `fetch(metric_id, window) -> float | None`.

### Step 3 — Extend `icpg drift check` with `--include-runtime`

When the flag is set, evaluate every `VALIDATED_IN_PROD` edge by calling its adapter. Runtime predicate failure adds a 7th drift dimension:

```
Runtime drift   Postcondition metric violates its predicate in production
```

### Step 4 — Hook into claude-bootstrap's post-commit flow

The `hooks/post-commit-graph` script runs `icpg record`. Add an optional `--check-runtime` step that queries the adapters for any symbols touched in this commit, so the agent sees drift before the change ships.

## Integration points

- `scripts/icpg/models.py` — add `MetricNode`, `RuntimeEdge`
- `scripts/icpg/drift.py` — add `check_runtime_drift()`
- `scripts/icpg/__main__.py` — wire `drift check --include-runtime` flag
- `skills/icpg/SKILL.md` — document the pattern
- `templates/icpg-metric.yaml` — template for declaring metrics

## Success criteria

1. `icpg drift check --include-runtime` queries configured adapters and reports runtime-dimension drift
2. At least one adapter (Datadog or Sentry) ships with docs + example config
3. A test harness using `stub_adapter` verifies runtime drift triggers correctly
4. Agent receives runtime signal in pre-task query output (`icpg query risk` includes current runtime state)
5. Zero network calls when no `VALIDATED_IN_PROD` edges exist — backward compatible

## Depends on

None — can be built independently on top of current iCPG.

## Follow-ups

- Spec 02 (rollback) uses the same signal to auto-revert on severe drift
- Spec 05 (confidence calibration) learns from runtime failures
