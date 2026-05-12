"""Tests for stakes classification — HIGH/MEDIUM/LOW from task metadata."""

from __future__ import annotations

from maggy.providers.base import Task
from maggy.routing_rules import StakesLevel, StakesPatterns
from maggy.services.stakes import classify_stakes


def _task(title: str, desc: str = "", raw: dict | None = None) -> Task:
    return Task(id="T-1", title=title, description=desc, raw=raw or {})


class TestHighStakes:
    def test_auth_file_in_title(self):
        result = classify_stakes(_task("Fix auth.py login bug"))
        assert result.level == "high"

    def test_billing_task_type(self):
        task = _task("Update billing", raw={"task_type": "billing"})
        result = classify_stakes(task)
        assert result.level == "high"

    def test_security_task_type(self):
        task = _task("Patch XSS", raw={"task_type": "security"})
        result = classify_stakes(task)
        assert result.level == "high"

    def test_production_keyword_in_desc(self):
        task = _task("Deploy fix", "Affects production data")
        result = classify_stakes(task)
        assert result.level == "high"

    def test_env_file_pattern(self):
        result = classify_stakes(_task("Update .env variables"))
        assert result.level == "high"

    def test_migration_in_title(self):
        result = classify_stakes(_task("Run database migration"))
        assert result.level == "high"


class TestMediumStakes:
    def test_api_route_file(self):
        result = classify_stakes(_task("Fix API routes handler"))
        assert result.level == "medium"

    def test_feature_task_type(self):
        task = _task("Add pagination", raw={"task_type": "feature"})
        result = classify_stakes(task)
        assert result.level == "medium"

    def test_database_schema_change(self):
        result = classify_stakes(_task("Update database schema"))
        assert result.level == "medium"


class TestLowStakes:
    def test_readme_update(self):
        result = classify_stakes(_task("Update README typo"))
        assert result.level == "low"

    def test_docs_task_type(self):
        task = _task("Fix docs", raw={"task_type": "docs"})
        result = classify_stakes(task)
        assert result.level == "low"

    def test_formatting_task(self):
        task = _task("Fix lint", raw={"task_type": "formatting"})
        result = classify_stakes(task)
        assert result.level == "low"


class TestStakesResult:
    def test_reasons_populated(self):
        result = classify_stakes(_task("Fix auth.py login"))
        assert len(result.reasons) > 0

    def test_custom_patterns(self):
        """classify_stakes with explicit patterns overrides defaults."""
        patterns = StakesPatterns(
            high=StakesLevel(
                file_patterns=["critical"],
                task_types=["emergency"],
                keywords=["urgent"],
            ),
            medium=StakesLevel(),
            low=StakesLevel(),
        )
        task = _task("Fix critical module", raw={})
        result = classify_stakes(task, patterns)
        assert result.level == "high"
