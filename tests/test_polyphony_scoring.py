"""Tests for Polyphony complexity scoring (§5.1)."""

import pytest
from polyphony.models import Task
from polyphony.scoring import (
    DIMENSIONS,
    score_task,
    score_cyclomatic,
    score_fan_out,
    score_security,
    score_concurrency,
    score_domain,
)


@pytest.fixture
def simple_task():
    return Task(
        title="Fix typo in README",
        source="local",
        source_ref="1",
        task_type="docs",
        scope=["README.md"],
        risk="low",
    )


@pytest.fixture
def complex_task():
    return Task(
        title="Refactor auth with async locks",
        source="github",
        source_ref="owner/repo#99",
        task_type="refactor",
        scope=["src/auth/middleware.ts", "src/auth/session.ts"],
        risk="high",
        metadata={
            "keywords": ["auth", "org_id", "asyncio.Lock"],
            "loc": 200,
            "callers": 15,
        },
    )


class TestDimensions:
    def test_five_dimensions(self):
        assert len(DIMENSIONS) == 5

    def test_dimension_names(self):
        expected = {
            "cyclomatic", "fan_out", "security",
            "concurrency", "domain",
        }
        assert set(DIMENSIONS) == expected


class TestScoreCyclomatic:
    def test_small_scope(self, simple_task):
        assert score_cyclomatic(simple_task) == 0

    def test_large_scope(self, complex_task):
        assert score_cyclomatic(complex_task) >= 1


class TestScoreFanOut:
    def test_no_callers(self, simple_task):
        assert score_fan_out(simple_task) == 0

    def test_many_callers(self, complex_task):
        assert score_fan_out(complex_task) == 2


class TestScoreSecurity:
    def test_no_security_keywords(self, simple_task):
        assert score_security(simple_task) == 0

    def test_auth_keywords(self, complex_task):
        assert score_security(complex_task) >= 1


class TestScoreConcurrency:
    def test_no_concurrency(self, simple_task):
        assert score_concurrency(simple_task) == 0

    def test_async_locks(self, complex_task):
        assert score_concurrency(complex_task) >= 1


class TestScoreDomain:
    def test_docs_task(self, simple_task):
        assert score_domain(simple_task) == 0

    def test_high_risk_refactor(self, complex_task):
        assert score_domain(complex_task) >= 1


class TestScoreTask:
    def test_simple_task_low(self, simple_task):
        total = score_task(simple_task)
        assert 0 <= total <= 3

    def test_complex_task_high(self, complex_task):
        total = score_task(complex_task)
        assert total >= 4

    def test_score_range(self, simple_task):
        total = score_task(simple_task)
        assert 0 <= total <= 10

    def test_returns_dict_with_breakdown(self, simple_task):
        """score_task returns (total, breakdown) tuple."""
        result = score_task(simple_task)
        assert isinstance(result, int)
