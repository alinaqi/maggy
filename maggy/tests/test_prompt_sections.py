"""Tests for prompt sections — composable named blocks."""

from __future__ import annotations

import pytest


class TestPromptSection:
    def test_section_has_required_fields(self):
        from maggy.prompt.sections import PromptSection
        s = PromptSection(id="test", layer="stable", content="hello")
        assert s.id == "test"
        assert s.layer == "stable"
        assert s.content == "hello"
        assert s.priority == 0


class TestStableSections:
    def test_identity_includes_project_name(self):
        from maggy.prompt.sections import identity_section
        s = identity_section("my-app")
        assert "my-app" in s.content
        assert s.layer == "stable"

    def test_capabilities_mentions_shell(self):
        from maggy.prompt.sections import capabilities_section
        s = capabilities_section()
        assert "shell" in s.content.lower()

    def test_rules_covers_code_and_non_code(self):
        from maggy.prompt.sections import rules_section
        s = rules_section()
        lower = s.content.lower()
        assert "verify" in lower or "read" in lower
        assert "research" in lower or "discuss" in lower or "plan" in lower

    def test_mode_semantics_lists_all_modes(self):
        from maggy.prompt.sections import mode_semantics_section
        s = mode_semantics_section()
        assert "project" in s.content.lower()
        assert "workspace" in s.content.lower()
        assert "bootstrap" in s.content.lower()

    def test_safety_section_exists(self):
        from maggy.prompt.sections import safety_section
        s = safety_section()
        assert s.layer == "stable"
        assert len(s.content) > 0


class TestRenderSections:
    def test_renders_in_priority_order(self):
        from maggy.prompt.sections import PromptSection, render_sections
        sections = [
            PromptSection(id="b", layer="stable", content="second", priority=1),
            PromptSection(id="a", layer="stable", content="first", priority=0),
        ]
        result = render_sections(sections)
        assert result.index("first") < result.index("second")

    def test_joins_with_newlines(self):
        from maggy.prompt.sections import PromptSection, render_sections
        sections = [
            PromptSection(id="a", layer="stable", content="AAA"),
            PromptSection(id="b", layer="stable", content="BBB"),
        ]
        result = render_sections(sections)
        assert "AAA" in result
        assert "BBB" in result
