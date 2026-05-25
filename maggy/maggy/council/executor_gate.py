"""Executor gate — decision matrix for auto-execution vs human review."""

from __future__ import annotations

from datetime import datetime, timezone

from maggy.council.models import (
    BlastAnalysis,
    DeliberationResult,
    ExecutionDecision,
    ValidationClassification,
)

_COVERAGE_THRESHOLD = 0.8


def decide(
    deliberation: DeliberationResult,
    blast: BlastAnalysis,
    validation: ValidationClassification,
) -> ExecutionDecision:
    if not deliberation.approved:
        return ExecutionDecision(
            "HUMAN_REVIEW", "Council did not approve"
        )

    severity = blast.severity

    if severity == "critical":
        return ExecutionDecision(
            "HUMAN_REVIEW",
            f"Critical path change ({_critical_reason(blast)})",
        )

    if not validation.auto_executable:
        return ExecutionDecision(
            "HUMAN_REVIEW",
            f"Subjective: {', '.join(validation.subjective_reasons)}",
        )

    if severity == "low":
        return ExecutionDecision(
            "AUTO_EXECUTE",
            "Low blast, objective validation",
            validation_steps=validation.objective_checks,
        )

    if severity == "medium":
        if blast.test_coverage >= _COVERAGE_THRESHOLD:
            return ExecutionDecision(
                "AUTO_WITH_ROLLBACK",
                "Medium blast, good coverage",
                rollback_point=_rollback_tag(),
                validation_steps=validation.objective_checks,
            )
        return ExecutionDecision(
            "HUMAN_REVIEW", "Medium blast, insufficient coverage"
        )

    if blast.test_coverage >= _COVERAGE_THRESHOLD:
        return ExecutionDecision(
            "AUTO_WITH_NOTIFY",
            "High blast, notifying human",
            rollback_point=_rollback_tag(),
            validation_steps=validation.objective_checks,
        )

    return ExecutionDecision("HUMAN_REVIEW", "Default safe path")


def _critical_reason(blast: BlastAnalysis) -> str:
    reasons = []
    if blast.has_auth_changes:
        reasons.append("auth")
    if blast.has_public_api_changes:
        reasons.append("public API")
    return ", ".join(reasons) or "critical"


def _rollback_tag() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"council-rollback-{ts}"
