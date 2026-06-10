"""Tests for blast radius analyzer."""

import pytest

from maggy.council.models import BlastAnalysis, ValidationClassification


class TestClassifyValidation:
    def test_pure_objective(self):
        from maggy.council.blast_analyzer import classify_validation
        blast = BlastAnalysis(
            files_changed=2, functions_affected=5,
            subsystems_crossed=1, test_coverage=0.9,
        )
        vc = classify_validation(blast)
        assert vc.validation_type == "OBJECTIVE"
        assert vc.auto_executable
        assert "tests" in vc.objective_checks

    def test_ui_change_is_subjective(self):
        from maggy.council.blast_analyzer import classify_validation
        blast = BlastAnalysis(
            files_changed=3, functions_affected=8,
            subsystems_crossed=1, test_coverage=0.7,
            has_ui_changes=True
        )
        vc = classify_validation(blast)
        assert "UI change" in vc.subjective_reasons
        assert not vc.auto_executable

    def test_no_tests_not_auto_executable(self):
        from maggy.council.blast_analyzer import classify_validation
        blast = BlastAnalysis(
            files_changed=2, functions_affected=4,
            subsystems_crossed=1, test_coverage=0.0,
        )
        vc = classify_validation(blast)
        assert "no test coverage" in vc.subjective_reasons

    def test_auth_always_subjective(self):
        from maggy.council.blast_analyzer import classify_validation
        blast = BlastAnalysis(
            files_changed=1, functions_affected=2,
            subsystems_crossed=1, test_coverage=1.0,
            has_auth_changes=True
        )
        vc = classify_validation(blast)
        assert "security-critical path" in vc.subjective_reasons


class TestComputeSeverity:
    def test_low(self):
        b = BlastAnalysis(
            files_changed=2, functions_affected=4,
            subsystems_crossed=1, test_coverage=0.8
        )
        assert b.severity == "low"

    def test_medium(self):
        b = BlastAnalysis(
            files_changed=7, functions_affected=20,
            subsystems_crossed=2, test_coverage=0.6
        )
        assert b.severity == "medium"

    def test_high(self):
        b = BlastAnalysis(
            files_changed=15, functions_affected=50,
            subsystems_crossed=4, test_coverage=0.3
        )
        assert b.severity == "high"

    def test_critical_overrides_low_count(self):
        b = BlastAnalysis(
            files_changed=1, functions_affected=1,
            subsystems_crossed=1, test_coverage=1.0,
            has_public_api_changes=True
        )
        assert b.severity == "critical"


class TestBlastFromFiles:
    def test_empty_files(self):
        from maggy.council.blast_analyzer import blast_from_files
        b = blast_from_files([], subsystems=[])
        assert b.files_changed == 0
        assert b.severity == "low"

    def test_counts_files(self):
        from maggy.council.blast_analyzer import blast_from_files
        files = ["a.py", "b.py", "c.py"]
        b = blast_from_files(files, subsystems=["api"])
        assert b.files_changed == 3
        assert b.subsystems_crossed == 1

    def test_detects_auth_files(self):
        from maggy.council.blast_analyzer import blast_from_files
        files = ["auth.py", "middleware.py"]
        b = blast_from_files(files, subsystems=["auth"])
        assert b.has_auth_changes
