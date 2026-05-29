"""Prompt assembly — combines stable, context, and volatile layers."""

from __future__ import annotations

from maggy.prompt.context_layer import (
    claude_md_section,
    file_tree_section,
    git_state_section,
    mode_section,
    tech_stack_section,
)
from maggy.prompt.modes import Mode, detect_mode
from maggy.prompt.sections import (
    PromptSection,
    capabilities_section,
    identity_section,
    mode_semantics_section,
    render_sections,
    rules_section,
    safety_section,
)
from maggy.prompt.skill_index import skill_index_section
from maggy.skills.selective import build_skill_index

_FALLBACK = (
    "You are Maggy, an autonomous AI engineering agent.\n"
    "Execute tasks directly — edit files, run commands, run tests. "
    "Never tell the user what to do; do it yourself and report the result.\n"
    "Be concise. Read code before making changes."
)


class PromptAssemblyService:
    def assemble(
        self, working_dir: str, project_key: str,
    ) -> str:
        try:
            sections = self._stable_sections(project_key)
            sections += self._context_sections(working_dir)
            sections += self._tooling_section()
            sections += self._skill_sections(
                working_dir, project_key,
            )
            return render_sections(sections)
        except Exception:
            return _FALLBACK

    def _stable_sections(
        self, project_key: str,
    ) -> list[PromptSection]:
        return [
            identity_section(project_key),
            capabilities_section(),
            rules_section(),
            mode_semantics_section(),
            safety_section(),
        ]

    def _context_sections(
        self, working_dir: str,
    ) -> list[PromptSection]:
        detected = detect_mode(working_dir)
        sections = [mode_section(detected)]
        if detected.mode == Mode.BOOTSTRAP:
            sections.append(self._bootstrap_hint(working_dir))
            return sections
        sections.append(file_tree_section(working_dir))
        sections.append(git_state_section(working_dir))
        sections.append(tech_stack_section(working_dir))
        sections.append(claude_md_section(working_dir))
        sections.append(self._working_dir_section(working_dir))
        return sections

    def _bootstrap_hint(
        self, working_dir: str,
    ) -> PromptSection:
        return PromptSection(
            id="bootstrap_hint",
            layer="context",
            content=(
                "## Bootstrap Mode\n"
                "No project detected. Help the user scaffold, "
                "clone, or research before coding."
            ),
            priority=14,
        )

    def _tooling_section(self) -> list[PromptSection]:
        try:
            from maggy.services.project_bootstrap import (
                detect_cli_inventory,
                detect_dev_tools,
            )
            ai = [c.name for c in detect_cli_inventory() if c.installed]
            dev = [c.name for c in detect_dev_tools() if c.installed]
            if not ai and not dev:
                return []
            parts: list[str] = []
            if ai:
                parts.append("AI models: " + ", ".join(ai))
            if dev:
                parts.append("Dev tools: " + ", ".join(dev))
            content = "## Available Tooling\n" + "\n".join(parts)
            return [PromptSection(
                id="tooling", layer="context",
                content=content, priority=7,
            )]
        except Exception:
            return []

    def _skill_sections(
        self, working_dir: str, project_key: str,
    ) -> list[PromptSection]:
        try:
            from maggy.skills.injector import match_skills
            from maggy.skills.registry import SkillRegistry
            reg = SkillRegistry()
            reg.load_global()
            if project_key:
                reg.load_project(project_key, working_dir)
            skills = reg.resolve(project_key or None)
            matched = match_skills(skills, working_dir)
            index = build_skill_index(matched)
            if not index:
                return []
            return [PromptSection(
                id="skill_index", layer="context",
                content=index, priority=8,
            )]
        except Exception:
            return []

    def _working_dir_section(
        self, working_dir: str,
    ) -> PromptSection:
        return PromptSection(
            id="working_dir",
            layer="context",
            content=f"Working directory: `{working_dir}`",
            priority=15,
        )
