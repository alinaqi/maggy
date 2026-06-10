"""Pipeline post-send hooks — budget, outcome, review, blueprint."""

from __future__ import annotations

import logging

from maggy.pipeline.models import PipelineResult

logger = logging.getLogger(__name__)


def record_spend(budget, result: PipelineResult) -> None:
    if not budget:
        return
    if not (result.cost_usd or result.tokens_in or result.tokens_out):
        return
    budget.record_spend(
        "anthropic", result.model,
        result.cost_usd, result.tokens_in, result.tokens_out,
    )


def record_outcome(routing, result: PipelineResult) -> None:
    if not routing:
        return
    reward = 1.0 if result.success else 0.0
    routing.record_outcome(
        result.model, result.task_type, result.blast, reward,
    )


def record_review(
    reviewer_scores, engram, result: PipelineResult, content: str,
) -> None:
    if result.task_type != "review" or not content:
        return
    if reviewer_scores:
        try:
            from maggy.services.reviewer_eval import evaluate_review
            evaluate_review(result.model, content, "review", reviewer_scores)
        except Exception:
            pass
    if engram:
        try:
            from maggy.learn.review_learner import learn_from_review
            learn_from_review(engram, result.model, content)
        except Exception:
            pass


def capture_blueprint(
    bp_store, message: str, result: PipelineResult,
    tool_events: list[str], project_key: str,
) -> None:
    if not bp_store or not tool_events or not result.success:
        return
    try:
        from maggy.blueprint_extract import capture_blueprint as _cap
        _cap(
            message, result.task_type, tool_events,
            result.model, bp_store, project_key,
        )
    except Exception:
        pass
