"""Tests for intent matcher."""
import pytest

from maggy.skills.intent_matcher import match_protocol
from maggy.skills.protocol_models import Protocol, ProtocolStep


@pytest.fixture
def protocols():
    return [
        Protocol(
            name="git-push",
            description="Push changes",
            triggers=["push changes", "push to git", "push to github"],
            steps=[ProtocolStep(name="s", label="s", cmd="echo")],
        ),
        Protocol(
            name="run-tests",
            description="Run tests",
            triggers=["run tests", "run the tests", "test it"],
            steps=[ProtocolStep(name="s", label="s", cmd="echo")],
        ),
        Protocol(
            name="create-pr",
            description="Create pull request",
            triggers=["create a pr", "create pull request", "open a pr"],
            steps=[ProtocolStep(name="s", label="s", cmd="echo")],
        ),
    ]


class TestMatchProtocol:
    def test_matches_git_push(self, protocols):
        p = match_protocol("push changes to github", protocols)
        assert p is not None
        assert p.name == "git-push"

    def test_matches_run_tests(self, protocols):
        p = match_protocol("can you run tests?", protocols)
        assert p is not None
        assert p.name == "run-tests"

    def test_matches_create_pr(self, protocols):
        p = match_protocol("create a pr for this", protocols)
        assert p is not None
        assert p.name == "create-pr"

    def test_no_match(self, protocols):
        p = match_protocol("explain the code", protocols)
        assert p is None

    def test_case_insensitive(self, protocols):
        p = match_protocol("PUSH TO GIT now", protocols)
        assert p is not None
        assert p.name == "git-push"

    def test_empty_protocols(self):
        p = match_protocol("push changes", [])
        assert p is None

    def test_longest_trigger_wins(self, protocols):
        p = match_protocol("push to github please", protocols)
        assert p is not None
        assert p.name == "git-push"
