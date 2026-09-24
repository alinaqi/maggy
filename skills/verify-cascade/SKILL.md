---
name: verify-cascade
description: Verification-gated model escalation — run a cheap model, verify its output with decomposed per-field checks, and escalate to a strong model only when a flag fires. Optional TypeSafe (jev) verifier.
when-to-use: When you want the token economy of a cheap model but the reliability of a strong one — structured extraction, data pulls, patch/summary checks — and would rather escalate on evidence than route blindly by task type.
user-invocable: true
allowed-tools: [Bash, Read, Write]
effort: medium
---

# Verify-Cascade — extract cheap, verify, escalate only on a flag

maggy already routes by *task complexity*. This makes routing **output-aware**: a
cheap model does the work, a **decomposed verifier** checks it, and you escalate to a
strong model (Claude) **only when the verifier flags a real problem**. The cheap rung
handles the easy items for near-free; only flagged items pay for the strong model —
most of the quality of the big model at a fraction of the cost.

It's the same discipline as the `security-audit` finder ≠ validator gate, applied to
routing: an independent verifier catches the cheap model's blind spots.

## The loop

```
1. EXTRACT   cheap model produces an output (extraction / answer / summary)
2. VERIFY    a decomposed verifier asks narrow per-field yes/no questions,
             framed so "bad = true", and returns P(wrong) per question
3. GATE      escalate if ANY question's P(wrong) > fire threshold (max, not mean)
4. ESCALATE  only the flagged items pay for the strong model; the rest keep the cheap answer
```

Schema-validation is necessary but not sufficient: a cheap model produces confident,
**schema-valid fabrications** (a blank field filled with a plausible invented value).
A structural check can't see that — a *semantic* verifier can.

## Verifiers (pluggable) — `verify_cascade.py`

```bash
VC="$(cat ~/.claude/.bootstrap-dir)/skills/verify-cascade/verify_cascade.py"
python3 "$VC"          # self-test (stubbed judge, no network, no model)
```

### LocalVerifier — the default, nothing leaves your machine
Runs the whole decomposed question battery through a cheap CLI model in one call and
returns `{field::metric: P(wrong)}`. No external service.
```python
import sys
sys.path.insert(0, f"{__import__('subprocess').check_output(['cat', __import__('os').path.expanduser('~/.claude/.bootstrap-dir')]).decode().strip()}/skills/verify-cascade")
# (or simply: sys.path.insert(0, "<bootstrap-dir>/skills/verify-cascade"))
from verify_cascade import get_verifier, build_questions, cascade
v = get_verifier("local")                     # uses $MAGGY_JUDGE_CMD (default: deepseek --flash)
result = cascade(
    extract  = lambda: cheap_extract(...),     # your cheap-model call -> dict
    verify   = lambda rec: v.verify({"source_text": source}, build_questions(rec, schema)),
    escalate = lambda: strong_extract(...),    # your strong-model call -> dict
    fire_t   = 0.7,
)
# result: {record, escalated: bool, fired: [qid...], scores: {qid: p}}
```
Set the judge model with `MAGGY_JUDGE_CMD` (e.g. `qwen3`, `deepseek --flash`) or pass
your own `judge=callable(prompt)->text`. The default passes the prompt on **stdin** (no
shell, so prompt content is never interpreted as a command), so `MAGGY_JUDGE_CMD` must
read from stdin. Questions are scored in complete batches and an over-long source warns
on stderr rather than being silently truncated.

### TypeSafeVerifier — OPT-IN, and it sends data to a third party
TypeSafe's hosted `jev` model is purpose-built and calibrated for this. But:

> ⚠️ **Data leaves your machine.** `TypeSafeVerifier.verify()` POSTs the `source_text`,
> `schema`, and `extraction` to **api.typesafe.ai**. Only use it for content you are
> willing to send to a third party. It is **off by default** — it will not even
> construct without `TYPESAFE_API_KEY`, so nothing is sent unless you opt in.

```bash
pip install typesafe_sdk
export TYPESAFE_API_KEY=…            # opt-in; enables the external call
```
```python
v = get_verifier("typesafe")         # raises unless TYPESAFE_API_KEY is set
```
Everything else (questions, gate, cascade) is identical — the verifier is the only swap.

## What makes a good verifier signal
- **Narrow + grounded** — one checkable yes/no about one field against the source, not a
  vague "is this good?".
- **Bad = TRUE, explicit criteria** — frame the escalate case as the `true` case.
- **Per-field, aggregate with `max`** — a per-field flag localizes the error and stays
  sparse; `max` means one confident red flag escalates instead of being averaged away.
- **Independent + cheap** — a dedicated verifier judges the worker's output and catches
  its blind spots, and it has to be cheap or there are no savings left to capture.
- **Calibrated** — high on real errors, low on correct ones, so one threshold splits
  accept vs escalate.

## When to reach for it vs plain routing
Use verify-cascade when the *output* can be checked against a source (extractions, RAG
answers, data pulls, structured summaries). For open-ended generation with no ground
truth, stick to maggy's task-complexity routing. The two compose: classify to pick the
cheap rung, verify to decide whether to escalate.

## Attribution
Pattern from TypeSafe's public "SDE cascade" cookbook, rebuilt so the verifier is
pluggable and the private LocalVerifier is the default; TypeSafe is an optional adapter.
