"""The coupon scenario from the factory doc (§1 spec, §2 plan + test plan, §5 AC3 visual):
the ticket, the ONE clarifying question and its answer, the approved AC1-AC3, the T1-T3
plan, and the fake build agent that writes the planned tests and applies the real fix diff.

The fixture app lives in tests/fixtures/coupon_app: `repo/` is the buggy checkout (an
expired code clears the field and shows no error), `agent/` holds what the build agent
writes (test files as .txt so this suite never collects them) and `fix.diff`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "coupon_app"
TICKET = "Fix what happens when a coupon expires"
QUESTION = ("Should an expired code stay visible in the field so the shopper can correct it, "
            "with expiry judged in UTC rather than the shop's local time zone?")
ANSWER = ("Keep the entered code visible and editable. Expiry semantics stay as they are: "
          "UTC. Preserve the pricing rules and the API response contract.")
CRITERIA = {
    "AC1": ("Applying an expired coupon shows \"This coupon has expired\" next to the field "
            "and keeps the entered code available for editing. The cart total stays at $100."),
    "AC2": ("Applying a valid 10% coupon to the same $100 fixture updates the total to $90. "
            "Applying a valid code after an expired one clears the error."),
    "AC3": ("At 390 px and 1440 px, the message sits under the coupon field and leaves the "
            "Apply button and order total visible and usable."),
}
TESTS = {"AC1": "test_ac1_expired_coupon_keeps_code", "AC2": "test_ac2_valid_code_after_expired",
         "AC3": "test_ac3_expired_layout"}
ERROR, TOTAL = "[data-testid=coupon-error]", "[data-testid=order-total]"
AC3_VISUAL = {
    "route": "checkout.html",
    "viewports": [{"name": "mobile", "width": 390, "height": 844},
                  {"name": "desktop", "width": 1440, "height": 900}],
    "actions": [{"do": "fill", "selector": "#coupon", "value": "EXPIRED"},
                {"do": "click", "selector": "#apply"}],
    "assertions": [{"check": "text", "selector": ERROR, "value": "This coupon has expired"},
                   *({"check": "in_viewport", "selector": s} for s in (ERROR, "#apply", TOTAL)),
                   {"check": "below", "selector": ERROR, "other": "#coupon"},
                   {"check": "no_horizontal_scroll"}],
}


def spec_draft(approved: bool) -> dict:
    """The author's draft: a first rough pass, or AC1-AC3 from the doc after the answer."""
    if not approved:
        texts = {"AC1": "An expired coupon is handled gracefully."}
    else:
        texts = CRITERIA
    criteria = [{"id": cid, "text": text, "kind": "ui" if cid == "AC3" else "functional",
                 "testable": True} for cid, text in texts.items()]
    return {"acceptance_criteria": criteria, "open_questions": [] if approved else [QUESTION],
            "assumptions": ["Seeded $100 cart; codes EXPIRED and SAVE10."], "risk_paths": []}


def _task(key: str, title: str, shape: tuple[list[str], list[str]]) -> dict:
    files, deps = shape
    return {"key": key, "title": title, "files": files, "depends_on": deps,
            "description": f"{title}. Use the seeded $100 cart; keep pricing and the API."}


def _entry(cid: str, where: tuple[str, str], what: tuple[str, str]) -> dict:
    (task, evidence), (action, expected) = where, what
    entry = {"criterion_id": cid, "task": task, "evidence": evidence, "action": action,
             "fixture": "seeded $100 cart (api.js) with codes EXPIRED and SAVE10",
             "expected": expected, "regression_test_name": TESTS[cid]}
    return {**entry, "visual": AC3_VISUAL} if evidence == "visual" else entry


def coupon_plan() -> dict:
    """T1-T3 with the doc's test plan. Each child is built from the default branch, so a
    child owning a regression test carries the fix that test proves (verify merges them)."""
    tasks = [_task("T1", "Reproduce the expired coupon and fix the field error",
                   (["tests/conftest.py", "tests/test_coupon_ac1.py", "app.js"], [])),
             _task("T2", "Fix the recovery after an expired coupon",
                   (["tests/test_coupon_ac2.py", "app.js"], ["T1"])),
             _task("T3", "Verify the integrated checkout layout",
                   (["tests/test_coupon_ac3.py", "app.js"], ["T2"]))]
    plan = [_entry("AC1", ("T1", "e2e"), (
                "enter EXPIRED and submit",
                "exact error shown, input keeps EXPIRED, total $100")),
            _entry("AC2", ("T2", "e2e"), (
                "replace EXPIRED with SAVE10 in the same session",
                "the error disappears and the total becomes $90")),
            _entry("AC3", ("T3", "visual"), (
                "render the expired state at 390x844 and 1440x900",
                "message under the field; Apply and total in view"))]
    return {"tasks": tasks, "test_plan": plan}


BUILD_AGENT = """
import json, shutil, subprocess, sys
from pathlib import Path
agent, prompt = Path({agent!r}), sys.argv[-1]
with (Path(__file__).parent / "build-prompts.jsonl").open("a") as log:
    log.write(json.dumps(prompt) + "\\n")
subprocess.run(["git", "apply", str(agent / "fix.diff")], check=False)
Path("tests").mkdir(exist_ok=True)
shutil.copyfile(agent / "conftest.py.txt", "tests/conftest.py")
for cid, test in {tests!r}.items():
    if test in prompt:
        name = "test_coupon_" + cid.lower() + ".py"
        shutil.copyfile(agent / (name + ".txt"), Path("tests") / name)
print("applied the coupon fix")
"""


def build_agent_source() -> str:
    return BUILD_AGENT.format(agent=str(FIXTURE / "agent"), tests=TESTS)


def seed_app(repo: Path) -> None:
    """Copy the buggy checkout into `repo` (committing is the caller's)."""
    for source in (FIXTURE / "repo").iterdir():
        shutil.copyfile(source, repo / source.name)
