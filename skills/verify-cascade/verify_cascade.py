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


def build_questions(record: dict, schema: dict | None = None) -> dict[str, dict]:
    """Decompose a record into per-field ``field::metric`` yes/no questions (bad = true)."""
    props = (schema or {}).get("properties", {})
    qs: dict[str, dict] = {}
    for name, value in record.items():
        spec = {
            "path": name,
            "type": props.get(name, {}).get("type", "unknown"),
            "description": props.get(name, {}).get("description", ""),
        }
        if _is_empty(value):
            qs[f"{name}::absence_wrong"] = {"field": spec, "value": value, "question": ABSENCE}
            continue
        for metric, q in METRICS.items():
            qs[f"{name}::{metric}"] = {"field": spec, "value": value, "question": q}
    return qs


class Verifier(Protocol):
    def verify(self, state: dict, questions: dict[str, dict]) -> dict[str, float]: ...


# --- Local verifier (default; no external egress) -------------------------

def _default_judge(prompt: str) -> str:
    """Run the local judge command (default `deepseek --flash`) on a prompt."""
    cmd = os.environ.get("MAGGY_JUDGE_CMD", "deepseek --flash")
    proc = subprocess.run(
        [*cmd.split(), prompt], capture_output=True, text=True, timeout=120
    )
    if proc.returncode != 0:
        raise RuntimeError(f"judge command failed: {proc.stderr[:200]}")
    return proc.stdout


class LocalVerifier:
    """Decomposed verification through a cheap local/CLI model. Nothing leaves the box.

    ``judge`` is a callable(prompt)->text; the default shells to ``MAGGY_JUDGE_CMD``. One
    call scores every question (cheap), returning ``{qid: P(wrong)}``. A parse failure
    scores 1.0 (escalate) — the safe direction.
    """

    def __init__(self, judge: Callable[[str], str] | None = None):
        self.judge = judge or _default_judge

    def verify(self, state: dict, questions: dict[str, dict]) -> dict[str, float]:
        prompt = (
            "You are a strict verifier. For each question, the value was extracted from the "
            "SOURCE below. Answer each question with P(wrong): the probability the answer to "
            "the question is TRUE (i.e. something is wrong). Return ONLY a JSON object "
            "mapping each id to a float 0..1.\n\n"
            f"SOURCE:\n{str(state.get('source_text',''))[:12000]}\n\n"
            f"QUESTIONS (id -> {{field, value, question}}):\n{json.dumps(questions)[:8000]}\n\n"
            "JSON only, e.g. {\"field::hallucinated\": 0.95, ...}"
        )
        scores = _parse_scores(self.judge(prompt))
        # A missing/unparsable score defaults to 1.0 (escalate) — the safe direction.
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
