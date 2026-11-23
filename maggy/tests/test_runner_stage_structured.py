"""Structured stage output: one fenced json block, validated against a Pydantic schema."""

from __future__ import annotations

import pytest

from maggy.runner.stages.models import SpecDraft, SpecReview
from maggy.runner.stages.structured import StructuredError, ask_structured, parse_structured
from runner_spec_helpers import draft, fenced, review


def test_parses_the_single_fenced_block() -> None:
    parsed = parse_structured(fenced(draft("a", "b")), SpecDraft)
    assert [c.id for c in parsed.acceptance_criteria] == ["AC1", "AC2"]


@pytest.mark.parametrize("text", ["no block", "```json\n{oops\n```",
                                  fenced(draft("a")) + fenced(draft("b")),
                                  fenced({"acceptance_criteria": []})])
def test_rejects_missing_broken_duplicate_or_invalid(text: str) -> None:
    with pytest.raises(StructuredError):
        parse_structured(text, SpecDraft)


@pytest.mark.parametrize("question", [None, "", "CSV or JSON? Which columns?",
                                      ["CSV or JSON?", "Which columns?"]])
def test_clarification_needs_exactly_one_question(question: object) -> None:
    with pytest.raises(StructuredError):
        parse_structured(fenced(review("needs_clarification", question)), SpecReview)


def test_clarification_with_one_question_is_valid() -> None:
    parsed = parse_structured(fenced(review("needs_clarification", "CSV or JSON?")), SpecReview)
    assert parsed.question == "CSV or JSON?"


def test_ask_retries_once_with_the_error_then_raises() -> None:
    prompts: list[str] = []

    def agent(prompt: str) -> str:
        prompts.append(prompt)
        return "nothing structured"

    with pytest.raises(StructuredError):
        ask_structured(agent, "PROMPT", SpecDraft)
    assert len(prompts) == 2 and prompts[0] == "PROMPT"
    assert "rejected" in prompts[1] and "PROMPT" in prompts[1]
