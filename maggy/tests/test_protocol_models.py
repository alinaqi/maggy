"""Tests for protocol models."""
import pytest

from maggy.skills.protocol_models import Protocol, ProtocolStep


class TestProtocolStep:
    def test_basic_step(self):
        s = ProtocolStep(name="lint", label="Run linter", cmd="ruff check .")
        assert s.name == "lint"
        assert s.cmd == "ruff check ."
        assert not s.optional
        assert s.condition == ""
        assert s.requires == ""

    def test_optional_step(self):
        s = ProtocolStep(
            name="test", label="Tests", cmd="pytest",
            optional=True, condition="tests/",
        )
        assert s.optional
        assert s.condition == "tests/"


class TestProtocol:
    def test_basic_protocol(self):
        p = Protocol(
            name="git-push",
            description="Push changes",
            triggers=["push changes", "push to git"],
            steps=[
                ProtocolStep(name="status", label="Status", cmd="git status"),
            ],
        )
        assert p.name == "git-push"
        assert len(p.triggers) == 2
        assert len(p.steps) == 1

    def test_matches_trigger(self):
        p = Protocol(
            name="test",
            description="Run tests",
            triggers=["run tests", "test it"],
            steps=[],
        )
        assert p.matches("can you run tests please")
        assert p.matches("test it now")
        assert not p.matches("write documentation")

    def test_matches_case_insensitive(self):
        p = Protocol(
            name="test",
            description="",
            triggers=["push to git"],
            steps=[],
        )
        assert p.matches("Push To Git now")
        assert p.matches("PUSH TO GIT")
