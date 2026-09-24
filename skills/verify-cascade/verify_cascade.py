#!/usr/bin/env python3
"""Verification-gated escalation for maggy — extract cheap, verify, escalate only on a flag.

Pattern (the TypeSafe SDE cascade, generalized): a cheap model produces an output;
a DECOMPOSED verifier asks narrow per-field yes/no questions framed so "bad = true";
if ANY question's P(wrong) exceeds the fire threshold, escalate to a stronger model.
The cheap rung handles the easy items for near-free; only flagged items pay for the
strong model. This makes maggy's routing output-aware, not just task-classification-based.

Verifiers are PLUGGABLE:
  - LocalVerifier (DEFAULT): runs the questions through a cheap model via a judge command
    (e.g. `deepseek --flash`). NO data leaves your machine.
  - TypeSafeVerifier (OPT-IN): calls TypeSafe's hosted `jev` verifier at api.typesafe.ai.
    It SENDS source_text + schema + extraction to a THIRD PARTY. Off unless you set
    TYPESAFE_API_KEY and select it explicitly. Requires `pip install typesafe_sdk`.

A good verifier signal is narrow + grounded, bad=TRUE with explicit criteria, per-field,
and aggregated with `max` (one confident red flag escalates, instead of averaged to silence).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any, Callable, Protocol

# Per-field checks, framed so TRUE = something is wrong (escalate). Empty fields get
# only ``absence_wrong``; non-empty fields get the rest.
METRICS = {
    "hallucinated": "Is the value unsupported by, or absent from, the source text?",
    "off_target": "Was the value pulled from incidental text rather than a genuine report of this field?",
    "incomplete": "Is the field wrongly empty or missing a value the source supports?",
    "format_violation": "Does the value violate the format/constraints implied by the field description or type?",
    "unreasonable": "Would a reasonable person not have extracted this value for this field?",
}
ABSENCE = "The value is empty. Does the source actually contain the information this field describes, making the empty result wrong?"
FIRE_T = 0.7


def _is_empty(v: Any) -> bool:
    return v is None or (isinstance(v, (str, list, dict)) and len(v) == 0)


_CONSTRAINT_KEYS = ("enum", "pattern", "format", "minimum", "maximum", "minLength", "maxLength")


def build_questions(record: dict, schema: dict | None = None) -> dict[str, dict]:
    """Decompose a record into per-field ``field::metric`` yes/no questions (bad = true).

    Iterates the UNION of record keys and schema fields, so a **required schema field
    missing from the record** still gets an ``absence_wrong`` question (otherwise an empty
    or partial extraction would produce no scores and be accepted without escalation).
    The field spec carries schema ``constraints`` (enum/pattern/format/bounds) so the
    ``format_violation`` check can actually test them.
    """
    schema = schema or {}
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    # ordered union of record keys, declared properties, AND required names (a required
    # name need not appear in `properties` per JSON Schema, but must still be checked).
    names = list(dict.fromkeys([*record.keys(), *props.keys(), *required]))
    qs: dict[str, dict] = {}
    for name in names:
        p = props.get(name, {})
        if isinstance(p, bool):  # JSON Schema allows a boolean property schema (true/false)
            spec = {"path": name, "type": "unknown", "description": "",
                    "constraints": {}, "boolean_schema": p, "required": name in required}
        else:
            spec = {
                "path": name,
                "type": p.get("type", "unknown"),
                "description": p.get("description", ""),
                "constraints": {k: p[k] for k in _CONSTRAINT_KEYS if k in p},
                "required": name in required,
            }
        value = record.get(name)
        if name not in record or _is_empty(value):
            qs[f"{name}::absence_wrong"] = {"field": spec, "value": value, "question": ABSENCE}
            continue
        for metric, q in METRICS.items():
            qs[f"{name}::{metric}"] = {"field": spec, "value": value, "question": q}
    return qs


class Verifier(Protocol):
    def verify(self, state: dict, questions: dict[str, dict]) -> dict[str, float]: ...


# --- Local verifier (default; no external egress) -------------------------

def _default_judge(prompt: str) -> str:
    """Run the local judge command (default `deepseek --flash`) on a prompt.

    The prompt is passed on **stdin**, never as an argv element: no shell, list args, and
    the (possibly large) prompt is data the OS never interprets as a command — so this
    stays local and avoids ARG_MAX limits. The command named by ``MAGGY_JUDGE_CMD`` must
    read its input from stdin (most model CLIs do).
    """
    cmd = os.environ.get("MAGGY_JUDGE_CMD", "deepseek --flash").split()
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"judge command failed: {proc.stderr[:200]}")
    return proc.stdout


class LocalVerifier:
    """Decomposed verification through a cheap local/CLI model. Nothing leaves the box.

    ``judge`` is a callable(prompt)->text; the default runs ``MAGGY_JUDGE_CMD`` with the
    prompt on stdin. Questions are scored in **complete batches** (never truncated — a
    dropped question would default to 1.0 and force a spurious escalation), and an
    over-long source is truncated only with a **visible stderr warning**, never silently.
    A missing/unparsable score defaults to 1.0 (escalate) — the safe direction.
    """

    def __init__(self, judge: Callable[[str], str] | None = None,
                 max_source_chars: int = 40000, batch: int = 40,
                 raise_on_oversize: bool = False):
        self.judge = judge or _default_judge
        self.max_source_chars = max_source_chars
        self.batch = max(1, batch)
        self.raise_on_oversize = raise_on_oversize

    def _source(self, state: dict) -> str:
        """Return the source. Over-length handling is EXPLICIT: raise if
        ``raise_on_oversize`` (caller must chunk), else warn loudly and verify the prefix —
        never a silent truncation. For full coverage of a long source, split it into
        bounded calls and combine per question with a **metric-aware** rule: for
        evidence-presence checks (``hallucinated``/``off_target``/``absence_wrong``/
        ``incomplete``) take the **min** P(wrong) across chunks (supported by ANY chunk =
        not wrong); intrinsic checks (``format_violation``/``type``/``unreasonable``) are
        source-independent, so any chunk's score applies."""
        src = str(state.get("source_text", ""))
        if len(src) > self.max_source_chars:
            msg = (f"source is {len(src)} chars > max_source_chars={self.max_source_chars}; "
                   f"evidence beyond the cutoff is not checked — split the source into "
                   f"bounded calls for full coverage.")
            if self.raise_on_oversize:
                raise ValueError(f"verify-cascade: {msg}")
            print(f"verify-cascade: WARNING {msg}", file=sys.stderr)
            src = src[:self.max_source_chars]
        return src

    def verify(self, state: dict, questions: dict[str, dict]) -> dict[str, float]:
        source = self._source(state)
        items = list(questions.items())
        scores: dict[str, float] = {}
        for i in range(0, len(items), self.batch):  # every question is scored — no truncation
            chunk = dict(items[i:i + self.batch])
            prompt = (
                "You are a strict verifier. Each value was extracted from the SOURCE below. "
                "For each question return P(wrong): the probability its answer is TRUE (i.e. "
                "something is wrong). Return ONLY a JSON object mapping each id to a float 0..1.\n\n"
                f"SOURCE:\n{source}\n\n"
                f"QUESTIONS (id -> {{field, value, question}}):\n{json.dumps(chunk)}\n\n"
                "JSON only, e.g. {\"field::hallucinated\": 0.95, ...}"
            )
            scores.update(_parse_scores(self.judge(prompt)))
        return {qid: _clamp(scores.get(qid, 1.0)) for qid in questions}


def _parse_scores(text: str) -> dict[str, float]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
        return {k: float(v) for k, v in d.items() if isinstance(v, (int, float))}
    except (ValueError, json.JSONDecodeError):
        return {}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# --- TypeSafe verifier (opt-in; sends data to api.typesafe.ai) -------------

class TypeSafeVerifier:
    """TypeSafe's hosted jev verifier. OPT-IN. SENDS source+schema+extraction to a third party.

    Requires TYPESAFE_API_KEY and ``pip install typesafe_sdk``. Only construct this when
    you have consciously accepted that verified content leaves your machine.
    """

    def __init__(self, api_key: str | None = None, model: str = "jev-1.12"):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        if not self.api_key:
            raise RuntimeError("TypeSafeVerifier needs TYPESAFE_API_KEY (opt-in; sends data to api.typesafe.ai)")
        try:
            from typesafe_sdk import Noul, NoulCriteria, TypeSafeClient  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("TypeSafe opt-in requires: pip install typesafe_sdk") from e
        self._Noul, self._Crit = Noul, NoulCriteria
        self._client = TypeSafeClient(api_key=self.api_key, timeout=30.0)
        self.model = model

    def verify(self, state: dict, questions: dict[str, dict]) -> dict[str, float]:
        crit = self._Crit(true="something is wrong", false="the value is correct")
        nouls = {qid: self._Noul(instructions=q, criteria=crit) for qid, q in questions.items()}
        ans = self._client.system_one(state=state, questions=nouls, model=self.model).answers
        return {qid: float(a.noul) for qid, a in ans.items()}


def get_verifier(name: str = "local", **kw) -> Verifier:
    """Factory. Default 'local' (private). 'typesafe' is opt-in and sends data externally."""
    if name == "typesafe":
        return TypeSafeVerifier(**kw)
    if name == "local":
        return LocalVerifier(**kw)
    raise ValueError(f"unknown verifier {name!r}; use 'local' or 'typesafe'")


# --- the gate + cascade ---------------------------------------------------

def should_escalate(scores: dict[str, float], fire_t: float = FIRE_T) -> list[str]:
    """Return the fired question ids (any per-field P(wrong) > threshold). max-style gate."""
    return [qid for qid, p in scores.items()
            if not qid.startswith("__overall__") and p > fire_t]


def cascade(extract: Callable[[], dict], verify: Callable[[dict], dict[str, float]],
            escalate: Callable[[], dict], fire_t: float = FIRE_T) -> dict:
    """Extract cheap -> verify -> escalate only if a flag fires. Returns a result dict."""
    cheap = extract()
    scores = verify(cheap)
    fired = should_escalate(scores, fire_t)
    if fired:
        return {"record": escalate(), "escalated": True, "fired": fired, "scores": scores}
    return {"record": cheap, "escalated": False, "fired": [], "scores": scores}


if __name__ == "__main__":  # tiny self-test with a stubbed judge (no network, no model)
    record = {"registration_open_date": "", "description": "Registration opens for the fall semester"}
    qs = build_questions(record, {"properties": {"description": {"type": "string"}}})
    stub = lambda _p: json.dumps({"description::hallucinated": 0.95, "description::off_target": 0.85})
    scores = LocalVerifier(judge=stub).verify({"source_text": "NYU nav boilerplate, no dates"}, qs)
    fired = should_escalate(scores)
    print("questions:", len(qs), "| fired:", fired)
    print("verdict:", "ESCALATE" if fired else "accept cheap")
