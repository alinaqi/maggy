"""Blast radius analysis — file/function/subsystem impact scoring."""

from __future__ import annotations

from maggy.council.models import BlastAnalysis, ValidationClassification

_AUTH_MARKERS = {"auth", "login", "session", "token", "password", "jwt", "oauth"}
_UI_EXTENSIONS = {".html", ".css", ".jsx", ".tsx", ".vue", ".svelte"}


def blast_from_files(
    files: list[str],
    subsystems: list[str],
) -> BlastAnalysis:
    has_auth = any(
        any(m in f.lower() for m in _AUTH_MARKERS) for f in files
    )
    has_ui = any(
        any(f.endswith(ext) for ext in _UI_EXTENSIONS) for f in files
    )
    return BlastAnalysis(
        files_changed=len(files),
        functions_affected=len(files) * 3,
        subsystems_crossed=max(len(subsystems), 1) if files else 0,
        test_coverage=0.0,
        has_auth_changes=has_auth,
        has_ui_changes=has_ui,
    )


def classify_validation(blast: BlastAnalysis) -> ValidationClassification:
    objective: list[str] = []
    subjective: list[str] = []

    if blast.test_coverage >= 0.5:
        objective.append("tests")
    elif blast.test_coverage <= 0.0 and blast.files_changed > 0:
        subjective.append("no test coverage")

    if blast.has_ui_changes:
        subjective.append("UI change")
    if blast.has_auth_changes:
        subjective.append("security-critical path")
    if not subjective and not blast.has_ui_changes:
        objective.append("types")
        objective.append("lint")

    return ValidationClassification(
        objective_checks=objective,
        subjective_reasons=subjective,
    )
