"""Spec-stage prompts: runner instructions first, then ONE delimited block of untrusted data.

The ticket, the item's comments (human answers), earlier drafts, the draft under review and
the repo context (AGENTS.md, file list) all go inside the single `<untrusted_ticket>` block
(RFC §2.6.6), so nothing in them can pose as runner instructions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from maggy.runner.awg_types import Claim
from maggy.runner.stages.models import SpecDraft
from maggy.worker.git_ops import run_git
from maggy.worker.prompt import assemble_prompt

MAX_AGENTS_MD, MAX_FILES, MAX_COMMENTS = 4000, 200, 20
READ_ONLY = "You may read the repository but must not change any file. "
REPLY = "End your reply with exactly one fenced ```json block of this shape:\n"
AUTHOR = (READ_ONLY + "Write the specification for the work item described in the data below: "
          "precise, testable acceptance criteria (ids AC1, AC2, ...; kind functional, ui or "
          "nonfunctional), open questions, assumptions and risky paths. Use the human answers "
          "in the comments. " + REPLY +
          '{"acceptance_criteria": [{"id": "AC1", "text": "...", "kind": "functional", '
          '"testable": true}], "open_questions": [], "assumptions": [], "risk_paths": []}')
REVIEWER = (READ_ONLY + "You independently review a draft specification (in the data below) "
            "for the work item. verdict is ready when every criterion is precise and "
            "testable; needs_clarification when a human must answer exactly ONE precise "
            "question first (put only that one question in `question`); blocked when the work "
            "cannot be specified (say why in `issues`). " + REPLY +
            '{"verdict": "ready|needs_clarification|blocked", "question": null, "issues": []}')


@dataclass(frozen=True)
class SpecContext:
    claim: Claim
    shown: dict
    repo: Path


def author_prompt(ctx: SpecContext) -> str:
    return assemble_prompt(AUTHOR, ticket_data(ctx, _section("Earlier drafts", _drafts(ctx.shown))))


def review_prompt(ctx: SpecContext, draft: SpecDraft) -> str:
    under_review = _section("Draft under review", draft.model_dump_json(indent=2))
    return assemble_prompt(REVIEWER, ticket_data(ctx, under_review))


def ticket_data(ctx: SpecContext, extra: str) -> str:
    claim = ctx.claim
    criteria = "\n".join(f"- {line}" for line in claim.acceptance_criteria) or "- (none yet)"
    return "\n\n".join([f"Title: {claim.title}", f"Description:\n{claim.description}",
                        f"Current acceptance criteria:\n{criteria}",
                        _section("Comments (oldest first)", _comments(ctx.shown)), extra,
                        _section("AGENTS.md", _agents_md(ctx.repo)),
                        _section("Repository files", _files(ctx.repo))])


def _section(name: str, body: str) -> str:
    return f"{name}:\n{body or '(none)'}"


def _comments(shown: dict) -> str:
    comments = (shown.get("comments") or [])[-MAX_COMMENTS:]
    return "\n".join(f"- {c.get('author', 'someone')}: {c.get('body', '')}" for c in comments)


def _drafts(shown: dict) -> str:
    drafts = [a.get("data") for a in shown.get("annotations") or []
              if str(a.get("key", "")).startswith("spec-draft")]
    return "\n".join(json.dumps(d) for d in drafts[-2:])


def _agents_md(repo: Path) -> str:
    path = repo / "AGENTS.md"
    return path.read_text(errors="replace")[:MAX_AGENTS_MD] if path.is_file() else ""


def _files(repo: Path) -> str:
    listed = run_git(repo, ["ls-files"]).splitlines()
    more = f"\n... and {len(listed) - MAX_FILES} more" if len(listed) > MAX_FILES else ""
    return "\n".join(listed[:MAX_FILES]) + more
