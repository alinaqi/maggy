"""Tests for agent-first system prompts — Maggy acts, doesn't advise."""

from __future__ import annotations


class TestIdentitySection:
    def test_identity_says_autonomous(self):
        from maggy.prompt.sections import identity_section
        s = identity_section("myapp")
        assert "autonomous" in s.content.lower()

    def test_identity_says_execute(self):
        from maggy.prompt.sections import identity_section
        s = identity_section("myapp")
        assert "execut" in s.content.lower()

    def test_identity_not_help_with(self):
        from maggy.prompt.sections import identity_section
        s = identity_section("myapp")
        assert "you help with" not in s.content.lower()


class TestCapabilitiesSection:
    def test_capabilities_says_act(self):
        from maggy.prompt.sections import capabilities_section
        s = capabilities_section()
        content = s.content.lower()
        assert "do not explain" in content or "never explain" in content

    def test_capabilities_says_execute_directly(self):
        from maggy.prompt.sections import capabilities_section
        s = capabilities_section()
        assert "directly" in s.content.lower()


class TestPiContext:
    def test_pi_context_agent_identity(self):
        from maggy.pipeline.backend_pi import _build_context
        ctx = _build_context("/tmp/test", "myapp")
        lower = ctx.lower()
        assert "autonomous" in lower or "agent" in lower

    def test_pi_context_not_respond_helpfully(self):
        from maggy.pipeline.backend_pi import _build_context
        ctx = _build_context("/tmp/test", "myapp")
        assert "respond helpfully" not in ctx.lower()

    def test_pi_context_says_execute(self):
        from maggy.pipeline.backend_pi import _build_context
        ctx = _build_context("/tmp/test", "myapp")
        assert "execut" in ctx.lower()
