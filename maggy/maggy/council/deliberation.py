"""Multi-round deliberation engine for Council of Experts."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from maggy.council.models import (
    ContextPackage,
    DeliberationResult,
    ReviewerVote,
)

QueryFn = Callable[[str, str], Awaitable[str]]

_MAX_ROUNDS = 3


def _check_consensus(votes: list[ReviewerVote]) -> bool:
    if not votes:
        return False
    first = votes[0].verdict
    return all(v.verdict == first for v in votes)


def _build_result(
    votes: list[ReviewerVote],
    rounds: int,
    log: list[dict],
    threshold: int,
) -> DeliberationResult:
    return DeliberationResult(
        final_votes=votes,
        rounds_needed=rounds,
        threshold=threshold,
        discussion_log=log,
    )


def _parse_vote(reviewer_id: str, round_num: int, raw: str) -> ReviewerVote:
    text = raw.strip()
    upper = text.upper()
    if upper.startswith("APPROVE"):
        verdict = "APPROVE"
    elif upper.startswith("REJECT"):
        verdict = "REJECT"
    else:
        verdict = "REJECT"
    reasoning = text.split("\n", 1)[1].strip() if "\n" in text else text
    return ReviewerVote(
        reviewer_id=reviewer_id,
        round_num=round_num,
        verdict=verdict,
        reasoning=reasoning,
    )


def _independent_prompt(ctx: ContextPackage) -> str:
    return (
        f"Goal: {ctx.goal}\n"
        f"Plan: {ctx.plan_text}\n"
        f"Diff: {ctx.code_diff[:500]}\n"
        f"Context: {ctx.issue_context[:300]}\n\n"
        "Reply APPROVE or REJECT on the first line, "
        "then reasoning."
    )


def _cross_examine_prompt(ctx: ContextPackage, prior: list[ReviewerVote]) -> str:
    feedback = "\n".join(
        f"- {v.reviewer_id}: {v.verdict} — {v.reasoning[:200]}"
        for v in prior
    )
    return (
        f"Goal: {ctx.goal}\n"
        f"Plan: {ctx.plan_text}\n\n"
        f"Round 1 feedback:\n{feedback}\n\n"
        "Revise your position. Reply APPROVE or REJECT, "
        "then reasoning."
    )


def _final_prompt(ctx: ContextPackage, all_votes: list[list[ReviewerVote]]) -> str:
    lines = []
    for rnd, votes in enumerate(all_votes, 1):
        for v in votes:
            lines.append(f"R{rnd} {v.reviewer_id}: {v.verdict}")
    summary = "\n".join(lines)
    return (
        f"Goal: {ctx.goal}\n\n"
        f"All positions:\n{summary}\n\n"
        "Final verdict. APPROVE or REJECT, then reasoning."
    )


class Deliberation:
    def __init__(self, query_fn: QueryFn):
        self._query = query_fn

    async def run(
        self,
        ctx: ContextPackage,
        reviewers: list[str],
        threshold: int,
    ) -> DeliberationResult:
        log: list[dict] = []
        all_rounds: list[list[ReviewerVote]] = []

        r1 = await self._round(reviewers, _independent_prompt(ctx), 1)
        all_rounds.append(r1)
        log.append({"round": 1, "votes": [v.to_dict() for v in r1]})
        if _check_consensus(r1):
            return _build_result(r1, 1, log, threshold)

        prompt2 = _cross_examine_prompt(ctx, r1)
        r2 = await self._round(reviewers, prompt2, 2)
        all_rounds.append(r2)
        log.append({"round": 2, "votes": [v.to_dict() for v in r2]})
        if _check_consensus(r2):
            return _build_result(r2, 2, log, threshold)

        prompt3 = _final_prompt(ctx, all_rounds)
        r3 = await self._round(reviewers, prompt3, 3)
        log.append({"round": 3, "votes": [v.to_dict() for v in r3]})
        return _build_result(r3, 3, log, threshold)

    async def _round(
        self,
        reviewers: list[str],
        prompt: str,
        round_num: int,
    ) -> list[ReviewerVote]:
        tasks = [self._query(rid, prompt) for rid in reviewers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        votes = []
        for rid, raw in zip(reviewers, results):
            if isinstance(raw, Exception):
                raw = f"REJECT\nError: {raw}"
            votes.append(_parse_vote(rid, round_num, raw))
        return votes
