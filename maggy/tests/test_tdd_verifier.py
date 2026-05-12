"""Tests for TDD verification gates."""

from __future__ import annotations

import pytest

from maggy.services.tdd_verifier import (
    _count_collected,
    _count_failures,
    _parse_coverage,
)


class TestParsers:
    """Parse pytest and coverage output."""

    def test_count_collected_normal(self):
        assert _count_collected("12 tests collected") == 12

    def test_count_collected_singular(self):
        assert _count_collected("1 test collected") == 1

    def test_count_collected_missing(self):
        assert _count_collected("no tests ran") == 0

    def test_count_failures_normal(self):
        assert _count_failures("3 failed, 7 passed") == 3

    def test_count_failures_none(self):
        assert _count_failures("10 passed") == 0

    def test_parse_coverage_normal(self):
        out = "TOTAL    500    50    90%"
        assert _parse_coverage(out) == 90.0

    def test_parse_coverage_missing(self):
        assert _parse_coverage("no coverage data") == 0.0


class TestVerifyResult:
    """VerifyResult dataclass."""

    def test_passed_result(self):
        from maggy.services.tdd_verifier import VerifyResult
        r = VerifyResult(True, "ok", 5, 0)
        assert r.passed is True
        assert r.tests_found == 5

    def test_failed_result(self):
        from maggy.services.tdd_verifier import VerifyResult
        r = VerifyResult(False, "tests failing", 5, 3)
        assert r.passed is False
        assert r.tests_failed == 3


class TestVerifyFunctions:
    """Async verify functions with mocked subprocesses."""

    @pytest.mark.asyncio
    async def test_verify_tests_exist_passes(self, monkeypatch):
        from maggy.services import tdd_verifier

        async def mock_run(cmd, cwd):
            return 0, "5 tests collected"

        monkeypatch.setattr(tdd_verifier, "_run_cmd", mock_run)
        r = await tdd_verifier.verify_tests_exist("/tmp")
        assert r.passed is True
        assert r.tests_found == 5

    @pytest.mark.asyncio
    async def test_verify_tests_exist_fails(self, monkeypatch):
        from maggy.services import tdd_verifier

        async def mock_run(cmd, cwd):
            return 1, "error"

        monkeypatch.setattr(tdd_verifier, "_run_cmd", mock_run)
        r = await tdd_verifier.verify_tests_exist("/tmp")
        assert r.passed is False

    @pytest.mark.asyncio
    async def test_verify_tests_fail_red(self, monkeypatch):
        from maggy.services import tdd_verifier

        async def mock_run(cmd, cwd):
            return 1, "2 failed, 3 passed"

        monkeypatch.setattr(tdd_verifier, "_run_cmd", mock_run)
        r = await tdd_verifier.verify_tests_fail("/tmp")
        assert r.passed is True
        assert r.tests_failed == 2

    @pytest.mark.asyncio
    async def test_verify_tests_fail_rejects_pass(self, monkeypatch):
        from maggy.services import tdd_verifier

        async def mock_run(cmd, cwd):
            return 0, "5 passed"

        monkeypatch.setattr(tdd_verifier, "_run_cmd", mock_run)
        r = await tdd_verifier.verify_tests_fail("/tmp")
        assert r.passed is False
        assert "expected failures" in r.detail

    @pytest.mark.asyncio
    async def test_verify_tests_pass_green(self, monkeypatch):
        from maggy.services import tdd_verifier

        async def mock_run(cmd, cwd):
            return 0, "10 passed"

        monkeypatch.setattr(tdd_verifier, "_run_cmd", mock_run)
        r = await tdd_verifier.verify_tests_pass("/tmp")
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_verify_lint_clean(self, monkeypatch):
        from maggy.services import tdd_verifier

        async def mock_run(cmd, cwd):
            return 0, "All checks passed!"

        monkeypatch.setattr(tdd_verifier, "_run_cmd", mock_run)
        r = await tdd_verifier.verify_lint("/tmp")
        assert r.passed is True
