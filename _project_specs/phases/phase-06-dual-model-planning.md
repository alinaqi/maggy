# Phase 6: Dual-Model Planning (Claude + Codex)

**Status:** superseded. The in-memory stubs `planning.py`, `models/plan.py` and `api/routes_planning.py` were deleted in the personal-harness Phase 6 cleanup (see `docs/rfc-personal-harness.md`); the deliverables below are historical.
**Priority:** P2 — quality improvement, not blocking
**Effort:** Medium
**Dependencies:** Phase 1 (PiAdapter for multi-model access)

---

## Scope

Every non-trivial plan goes through a two-model review before execution. The primary model creates the architecture plan; a second model independently counter-checks for missing edge cases, over-engineering, security gaps, and simpler approaches. Maggy shows both perspectives in a diff view for user approval.

## What Gets Built

1. **Dual-plan orchestrator** (`maggy/maggy/planning.py`)
   - Input: ticket/task description + iCPG blast radius context
   - Step 1: Primary model (Claude) generates plan with file list, approach, risks
   - Step 2: Counter-check model (Codex/GPT-4o) independently reviews the plan
   - Step 3: Merge into diff view with conflicts highlighted
   - Blast threshold: only trigger dual-plan for blast >= 4 (configurable)

2. **Plan diff format**
   - Structured output: `{agreed: [...], conflicts: [...], primary_only: [...], counter_only: [...]}`
   - Each conflict has: primary's approach, counter's approach, trade-off explanation
   - User resolves conflicts via dashboard or CLI

3. **Plan reward tracking**
   - Track which plan approach (primary vs counter) leads to better outcomes
   - Feed into L3 weekly analysis: is dual-planning worth the latency?
   - Auto-disable for task types where counter-check never catches issues

4. **Dashboard integration**
   - Plan diff view in Maggy dashboard
   - One-click approve with merged approach
   - History of past plans and their outcomes

## Deliverables

- [ ] `maggy/maggy/planning.py` — Dual-plan orchestrator
- [ ] `maggy/maggy/models/plan.py` — Plan and PlanDiff Pydantic models
- [ ] `maggy/maggy/api/routes_planning.py` — Plan creation and approval endpoints
- [ ] `tests/test_planning.py` — Plan generation and diff tests
- [ ] Dashboard plan diff component

## Success Criteria

- [ ] Dual-plan catches at least 1 meaningful issue per 10 plans (blast >= 4)
- [ ] Plan diff clearly shows agreements vs conflicts
- [ ] User can approve/merge in < 30 seconds
- [ ] Auto-disables for task types where it adds no value (negative reward)
- [ ] All tests pass, coverage >= 80%

## Risks

- Second model call adds latency — mitigate by running both models in parallel
- Counter-check quality depends on second model having enough context — share iCPG data
- Could feel like unnecessary friction for experienced developers — make blast threshold configurable
